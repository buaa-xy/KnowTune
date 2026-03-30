import paramiko
import time
import re
import os
import csv
import json
from typing import List, Dict

# ========== Basic Configuration ==========
REMOTE_HOST = ""
REMOTE_USER = "root"
REMOTE_PWD = ""

MYSQL_CONF = "/etc/my.cnf"
MYSQL_BACK = "/etc/my.cnf.back"

DB_NAME = "sbtest"
DB_USER = "root"
DB_PASS = "123456"
DB_HOST = "localhost"
DB_PORT = 3306

SYSBENCH_CMD = (
    f"sysbench oltp_read_write --mysql-host={DB_HOST} --mysql-port={DB_PORT} "
    f"--mysql-user={DB_USER} --mysql-password={DB_PASS} --mysql-db={DB_NAME} "
    f"--tables=10 --table-size=50000 --threads=18 --time=60 run"
)

SYSBENCH_BASE = (
    f"sysbench oltp_read_write "
    f"--mysql-host={DB_HOST} --mysql-port={DB_PORT} "
    f"--mysql-user={DB_USER} --mysql-password={DB_PASS} --mysql-db={DB_NAME} "
    f"--tables=10 --table-size=50000 "
)

UNSUPPORTED_PARAMS = [
    "query_cache_size",
    "query_cache_type",
    "query_cache_limit",
    "innodb_latch_spin_wait_delay",  # Deprecated parameter
]

CSV_LOG = './mysql_qps_tps_avg_p95_log.csv'

# ========== SSH Execution Helper ==========
def exec_ssh(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out, err = stdout.read().decode(), stderr.read().decode()
    return out, err

# ========== Test a Single Configuration ==========
def test_mysql_remote(cfg):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PWD)

    try:
        # 1. Restore default configuration
        restore_cmd = f'cp {MYSQL_BACK} {MYSQL_CONF}'
        exec_ssh(ssh, restore_cmd)
        print("Configuration restored successfully")
        time.sleep(2)
        
        # 2. Update parameters
        for key, value in cfg.items():
            if key in UNSUPPORTED_PARAMS:
                print(f"Skipping unsupported parameter: {key}")
                continue
            update_cmd = (
                f'grep -q "^{key}\\s*=" "{MYSQL_CONF}" && '
                f'sed -i "s|^{key}\\s*=.*|{key} = {value}|" "{MYSQL_CONF}" || '
                f'sed -i "/\\[mysqld\\]/a {key} = {value}" "{MYSQL_CONF}"'
            )
            print(update_cmd)
            exec_ssh(ssh, update_cmd)
        print(f"Parameters updated successfully: {cfg}")
        time.sleep(2)
        
        # 3. Restart MySQL
        reload_cmd = "systemctl restart mysqld && sleep 10"
        _, err = exec_ssh(ssh, reload_cmd)
        if err:
            print("MySQL restart failed:", err)
            return {"config": cfg, "qps": 0, "tps": 0}
        print("MySQL restarted successfully")
        time.sleep(2)
        
        # 4.1 sysbench prepare
        prepare_cmd = SYSBENCH_BASE + " prepare"
        exec_ssh(ssh, prepare_cmd)
        print(prepare_cmd)
        print("✅ sysbench prepare done")
        
        # 4.2 Run sysbench benchmark
        remote_log_file = f"/home/xuyi/knowtune/log/mysql_GPTuner_{int(time.time())}.log"
        bench_cmd = f"{SYSBENCH_CMD} > {remote_log_file} 2>&1"
        exec_ssh(ssh, bench_cmd)
        print("Benchmark completed")
        time.sleep(2)

        # 4.3 sysbench cleanup
        cleanup_cmd = SYSBENCH_BASE + " cleanup"
        exec_ssh(ssh, cleanup_cmd)
        print("✅ sysbench cleanup done")

        # 5. Parse the log
        cat_cmd = f"cat {remote_log_file}"
        output, _ = exec_ssh(ssh, cat_cmd)

        final_qps, final_tps, avg_latency, p95 = None, None, None, None
        in_latency_section = False  # Flag to indicate we are in "Latency (ms):" section

        for line in output.splitlines():
            # QPS
            if "queries:" in line:
                match = re.search(r'\(([\d.]+) per sec', line)
                if match:
                    final_qps = float(match.group(1))

            # TPS
            elif "transactions:" in line:
                match = re.search(r'\(([\d.]+) per sec', line)
                if match:
                    final_tps = float(match.group(1))

            # Enter latency section
            elif "Latency (ms):" in line:
                in_latency_section = True
                continue

            # Extract average latency
            elif in_latency_section and "avg:" in line:
                try:
                    avg_latency = float(line.split()[1])
                except (ValueError, IndexError):
                    pass

            # Exit latency section
            elif in_latency_section and line.strip() == "":
                in_latency_section = False

            # 95th percentile
            elif "95th percentile:" in line:
                try:
                    p95 = float(line.split(":")[-1].strip())
                except ValueError:
                    pass

        if final_qps is None or final_tps is None or p95 is None:
            print("Failed to parse log")
            final_qps, final_tps, p95 = 0, 0, 0

        # 6. Save results to CSV
        os.makedirs(os.path.dirname(CSV_LOG), exist_ok=True)
        file_exists = os.path.isfile(CSV_LOG)
        with open(CSV_LOG, mode='a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['config', 'qps', 'tps', 'avg','p95'])
            writer.writerow([cfg, final_qps, final_tps, avg_latency, p95])

        return {"config": cfg, "qps": final_qps, "tps": final_tps, "avg": avg_latency, "p95": p95}

    finally:
        ssh.close()

def load_configs_from_json(json_file: str) -> List[Dict]:
    """
    Load parameter configurations from a JSON file and extract params and weight
    Returns [{'name': 'xxx', 'params': {...}, 'weight': w}, ...]
    """
    with open(json_file, "r") as f:
        data = json.load(f)

    configs = []
    for name, item in data.items():
        cfg = {
            "name": name,
            "params": item["params"],
            "weight": item["weight"]
        }
        configs.append(cfg)
    return configs

# ========== Batch Testing Entry ==========
def run_multiple_configs(json_file: str):
    configs = load_configs_from_json(json_file)
    param_list = [c["params"] for c in configs]
    history = []
    for cfg in param_list:
        result = test_mysql_remote(cfg)
        history.append(result)
        print(f"Completed config: {cfg}, Result: QPS={result['qps']}, P95={result['p95']}")
    return history

# ========== Example Run ==========
if __name__ == "__main__":
    configs = [
        {"innodb_buffer_pool_size": "2G", "innodb_log_file_size": "256M"},
        {"innodb_buffer_pool_size": "4G", "innodb_log_file_size": "512M"},
    ]

    smac_history = run_multiple_configs("param_candidate.json")
    print("\n=== Final History ===")
    print(smac_history)

    # Save as JSON file
    with open("smac_history2.json", "w", encoding="utf-8") as f:
        json.dump(smac_history, f, ensure_ascii=False, indent=4)

    print("✅ Saved as tuning_results.json")
