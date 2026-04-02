# src/runner/nginx_runner.py
import paramiko
import time
import os
import csv
import re

class NginxRunner:
    """
    A standalone runner for remote Nginx configuration testing and benchmarking.
    Handles SSH connection, Nginx config update, service reload, httpress pressure test,
    and performance metric (RPS) parsing.
    """

    def __init__(
        self,
        remote_host: str = "",
        remote_user: str = "root",
        remote_pwd: str = "",
        nginx_conf: str = "/usr/local/nginx/conf/nginx.conf",
        nginx_backup: str = "/usr/local/nginx/conf/nginx.conf.back",
        target_host: str = "127.0.0.1",
        target_port: str = "10000",
        csv_log: str = "./nginx_rps_log.csv"
    ):
        """
        Initialize Nginx runner with remote server and configuration paths.
        
        Args:
            remote_host: SSH IP address of the target server
            remote_user: SSH login username
            remote_pwd: SSH login password
            nginx_conf: Path to Nginx main configuration file
            nginx_backup: Backup path of the original Nginx configuration
            target_host: Target host for httpress benchmark
            target_port: Target port for httpress benchmark
            csv_log: Path to CSV log file for RPS results
        """
        # SSH remote server basic info
        self.REMOTE_HOST = remote_host
        self.REMOTE_USER = remote_user
        self.REMOTE_PWD = remote_pwd

        # Nginx configuration file paths
        self.NGINX_CONF = nginx_conf
        self.NGINX_BACKUP = nginx_backup

        # Benchmark target info
        self.TARGET_HOST = target_host
        self.TARGET_PORT = target_port

        # Logging
        self.CSV_LOG = csv_log

    def _exec_ssh(self, ssh_client: paramiko.SSHClient, cmd: str) -> tuple[str, str]:
        """
        Private helper: Execute a shell command via SSH and return output/error.
        
        Args:
            ssh_client: Active paramiko SSH client
            cmd: Shell command string to execute
        
        Returns:
            stdout and stderr decoded as strings
        """
        stdin, stdout, stderr = ssh_client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        return out, err

    def test_config(self, cfg: dict) -> dict:
        """
        Test a given Nginx parameter configuration remotely:
        1. Restore default Nginx config
        2. Apply new parameters
        3. Reload Nginx service
        4. Run httpress benchmark
        5. Parse RPS (Requests Per Second)
        6. Return performance results
        
        Args:
            cfg: Dictionary of Nginx parameters {param_name: value}
        
        Returns:
            Dict containing config and RPS performance metric
        """
        # Establish SSH connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=self.REMOTE_HOST,
            username=self.REMOTE_USER,
            password=self.REMOTE_PWD
        )

        try:
            # 1. Restore default Nginx configuration
            restore_command = f'cp {self.NGINX_BACKUP} {self.NGINX_CONF}'
            self._exec_ssh(ssh, restore_command)
            print("Default configuration restored")
            time.sleep(2)

            # 2. Update configuration parameters
            for key, value in cfg.items():
                # If the parameter exists, replace it; otherwise insert inside http {...}
                update_cmd = (
                    f'grep -q "^\\s*{key}\\s\\+" "{self.NGINX_CONF}" && '
                    f'sed -i "s|^\\s*{key}\\s\\+.*|    {key} {value};|" "{self.NGINX_CONF}" || '
                    f'sed -i "/http\\s*{{/a\\    {key} {value};" "{self.NGINX_CONF}"'
                )
                self._exec_ssh(ssh, update_cmd)
            print("Parameters updated successfully")
            time.sleep(2)

            # 3. Reload Nginx
            reload_cmd = "/usr/local/nginx/sbin/nginx -s reload"
            _, err = self._exec_ssh(ssh, reload_cmd)
            if err:
                print("Nginx reload failed")
                return {"config": cfg, "rps": 50000}
            print("Nginx reloaded successfully")
            time.sleep(2)

            # 4. Run httpress benchmark
            remote_log_file = f"/tmp/nginx/{int(time.time())}.log"
            httpress_cmd = (
                f"mkdir -p /tmp/nginx && "
                f"httpress -n 2000000 -c 512 -t 7 -k http://{self.TARGET_HOST}:{self.TARGET_PORT} "
                f"> {remote_log_file} 2>&1"
            )
            self._exec_ssh(ssh, httpress_cmd)
            print("Benchmark completed")
            time.sleep(2)

            # 5. Extract RPS from log
            cat_cmd = f"cat {remote_log_file}"
            output, _ = self._exec_ssh(ssh, cat_cmd)

            final_rps = None
            for line in output.splitlines():
                if "TIMING:" in line:
                    match = re.search(r'TIMING:.*?(\d+)\s+rps,\s+(\d+)\s+kbps', line)
                    if match:
                        final_rps = int(match.group(1))
                        break

            if final_rps is None:
                print("Failed to parse RPS from log")
                final_rps = 0

            # 6. Save RPS to CSV log
            os.makedirs(os.path.dirname(self.CSV_LOG), exist_ok=True)
            file_exists = os.path.isfile(self.CSV_LOG)
            with open(self.CSV_LOG, mode='a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['config', 'rps'])
                writer.writerow([cfg, final_rps])

            return {"config": cfg, "rps": final_rps}

        finally:
            ssh.close()