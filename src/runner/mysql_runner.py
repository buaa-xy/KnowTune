import paramiko
import time
import re
import os
import csv

class MySQLRunner:
    """
    A standalone runner for remote MySQL configuration testing and benchmarking.
    Handles SSH connection, MySQL configuration update, service restart, sysbench pressure test,
    and performance metric parsing.
    """

    def __init__(
        self,
        remote_host="",
        remote_user="root",
        remote_pwd="",
        mysql_conf="/etc/my.cnf",
        mysql_backup="/etc/my.cnf.back",
        db_host="localhost",
        db_port=3306,
        db_user="root",
        db_pass="123456",
        db_name="sbtest",
        threads=18,
        time=60,
        tables=10,
        table_size=50000
    ):
        """
        Initialize MySQL runner with remote server and database configuration.
        
        Args:
            remote_host: SSH IP address of the target server
            remote_user: SSH login username
            remote_pwd: SSH login password
            mysql_conf: Path to MySQL main configuration file
            mysql_backup: Backup path of the original MySQL configuration
            db_host: MySQL host address (usually localhost)
            db_port: MySQL port
            db_user: MySQL username
            db_pass: MySQL password
            db_name: Database name for sysbench test
            threads: Number of concurrent threads for sysbench
            time: Duration of pressure test in seconds
            tables: Number of test tables
            table_size: Number of rows per test table
        """
        # SSH remote server basic info
        self.REMOTE_HOST = remote_host
        self.REMOTE_USER = remote_user
        self.REMOTE_PWD = remote_pwd

        # MySQL configuration file paths
        self.MYSQL_CONF = mysql_conf
        self.MYSQL_BACKUP = mysql_backup

        # MySQL database connection info
        self.DB_HOST = db_host
        self.DB_PORT = db_port
        self.DB_USER = db_user
        self.DB_PASS = db_pass
        self.DB_NAME = db_name

        # Sysbench pressure test parameters
        self.threads = threads
        self.time = time
        self.tables = tables
        self.table_size = table_size

        # Unsupported or deprecated MySQL parameters that should be skipped
        self.UNSUPPORTED_PARAMS = [
            "query_cache_size",
            "query_cache_type",
            "query_cache_limit",
            "innodb_latch_spin_wait_delay",
        ]

        # Base sysbench command for prepare/cleanup
        self.sysbench_base = (
            f"sysbench oltp_read_write "
            f"--mysql-host={db_host} --mysql-port={db_port} "
            f"--mysql-user={db_user} --mysql-password={db_pass} --mysql-db={db_name} "
            f"--tables={tables} --table-size={table_size} "
        )

        # Full sysbench run command with threads and duration
        self.sysbench_run = (
            f"{self.sysbench_base.strip()} --threads={threads} --time={time} run"
        )

    def _exec_ssh(self, ssh_client, cmd):
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

    def test_config(self, cfg):
        """
        Test a given MySQL parameter configuration remotely:
        1. Restore default MySQL config
        2. Apply new parameters
        3. Restart MySQL service
        4. Run sysbench prepare/run/cleanup
        5. Parse QPS, TPS, avg latency, P95 latency
        6. Return performance results
        
        Args:
            cfg: Dictionary of MySQL parameters {param_name: value}
        
        Returns:
            Dict containing config and performance metrics
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
            # Step 1: Restore original MySQL configuration
            restore_cmd = f'cp {self.MYSQL_BACKUP} {self.MYSQL_CONF}'
            self._exec_ssh(ssh, restore_cmd)
            time.sleep(1)

            # Step 2: Update each parameter in my.cnf
            for key, value in cfg.items():
                if key in self.UNSUPPORTED_PARAMS:
                    print(f"[MySQLRunner] Skip unsupported: {key}")
                    continue
                # Update existing param or append new one under [mysqld]
                update_cmd = (
                    f'grep -q "^{key}\\s*=" "{self.MYSQL_CONF}" && '
                    f'sed -i "s|^{key}\\s*=.*|{key} = {value}|" "{self.MYSQL_CONF}" || '
                    f'sed -i "/\\[mysqld\\]/a {key} = {value}" "{self.MYSQL_CONF}"'
                )
                self._exec_ssh(ssh, update_cmd)
            time.sleep(1)

            # Step 3: Restart MySQL service to apply changes
            restart_cmd = "systemctl restart mysqld && sleep 10"
            _, err = self._exec_ssh(ssh, restart_cmd)
            if err:
                print(f"[MySQLRunner] Restart failed: {err}")
                return {"config": cfg, "qps": 0, "tps": 0, "avg": 0, "p95": 0}

            # Step 4: Prepare test data
            prepare_cmd = self.sysbench_base + " prepare"
            self._exec_ssh(ssh, prepare_cmd)
            time.sleep(1)

            # Step 5: Run sysbench benchmark and save log
            log_file = f"/home/knowtune/log/mysql_tuner_{int(time.time())}.log"
            bench_cmd = f"{self.sysbench_run} > {log_file} 2>&1"
            self._exec_ssh(ssh, bench_cmd)

            # Step 6: Clean up test data
            cleanup_cmd = self.sysbench_base + " cleanup"
            self._exec_ssh(ssh, cleanup_cmd)
            time.sleep(1)

            # Step 7: Read and parse benchmark log
            output, _ = self._exec_ssh(ssh, f"cat {log_file}")

            # Initialize performance metrics
            qps, tps, avg_lat, p95 = 0, 0, 0, 0
            in_latency = False

            # Parse key metrics from sysbench output
            for line in output.splitlines():
                if "queries:" in line:
                    m = re.search(r"\(([\d.]+) per sec", line)
                    if m:
                        qps = float(m.group(1))
                elif "transactions:" in line:
                    m = re.search(r"\(([\d.]+) per sec", line)
                    if m:
                        tps = float(m.group(1))
                elif "Latency (ms):" in line:
                    in_latency = True
                elif in_latency and "avg:" in line:
                    try:
                        avg_lat = float(line.split()[1])
                    except:
                        pass
                elif in_latency and not line.strip():
                    in_latency = False
                elif "95th percentile:" in line:
                    try:
                        p95 = float(line.split(":")[-1].strip())
                    except:
                        pass

            # Return final test result
            return {
                "config": cfg,
                "qps": qps,
                "tps": tps,
                "avg": avg_lat,
                "p95": p95
            }

        finally:
            # Ensure SSH connection is closed
            ssh.close()