#!/usr/bin/env python3
"""
mysql_tuning_with_history_paramiko.py
Tune MySQL parameters using SMAC, modify MySQL configuration remotely via Paramiko, and run sysbench benchmarks.
Parameter ranges and historical results are loaded from JSON files.
"""

import os
import json
import time
import re
import csv
import paramiko
from smac import HyperparameterOptimizationFacade as HPO
from smac import Scenario, initial_design
from smac.runhistory.runhistory import RunHistory
from ConfigSpace import ConfigurationSpace, UniformIntegerHyperparameter, UniformFloatHyperparameter, CategoricalHyperparameter, Configuration


# ========== Global Configuration ==========
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
    f"--tables=10 --table-size=50000 --threads=18 --time=100 run"
)

SYSBENCH_BASE = (
    f"sysbench oltp_read_write "
    f"--mysql-host={DB_HOST} --mysql-port={DB_PORT} "
    f"--mysql-user={DB_USER} --mysql-password={DB_PASS} --mysql-db={DB_NAME} "
    f"--tables=10 --table-size=50000 "
)

CSV_LOG = './mysql_p95_tps_log.csv'

UNSUPPORTED_PARAMS = [
    "query_cache_size",
    "query_cache_type",
    "query_cache_limit",
    "innodb_latch_spin_wait_delay",  # Deprecated parameter
]

# ========== Helper Functions ==========
def exec_ssh(ssh_client: paramiko.SSHClient, cmd: str):
    stdin, stdout, stderr = ssh_client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

# ========== Test a Single MySQL Configuration Remotely ==========
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
        reload_cmd = "systemctl restart mysqld && sleep 5"
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
        remote_log_file = f"/home/knowtune/log/mysql_GPTuner_{int(time.time())}.log"
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
        in_latency_section = False  # Flag indicating "Latency (ms):" section

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

            # Extract avg latency
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
                writer.writerow(['config', 'qps', 'tps', 'avg', 'p95'])
            writer.writerow([cfg, final_qps, final_tps, avg_latency, p95])

        return {"config": cfg, "qps": final_qps, "tps": final_tps, "avg": avg_latency, "p95": p95}

    finally:
        ssh.close()

# ========== SMAC Objective Function ==========
def evaluate_mysql(cfg: dict, seed: int) -> float:
    print("----------------------------")
    print(cfg)
    res = test_mysql_remote(cfg)
    qps = res['qps']
    print(f"[evaluate_mysql] cfg={cfg}  QPS={qps:.4f}")
    return -qps  # SMAC minimizes, return negative QPS to maximize

# ========== Build Search Space from JSON ==========
def build_mysql_space_from_json(range_file: str) -> ConfigurationSpace:
    """
    Build SMAC search space from a JSON file.
    Each parameter in JSON can be:
        - Continuous integer range: [low, high] (int)
        - Continuous float range: [low, high] (float)
        - Discrete list of values: [v1, v2, v3,...] (numbers or strings)
    """
    cs = ConfigurationSpace()
    with open(range_file, 'r') as f:
        param_ranges = json.load(f)

    for name, info in param_ranges.items():
        rng = info['range']

        # If multiple discrete values
        if isinstance(rng, list):
            # Check if continuous range [low, high]
            if len(rng) == 2 and all(isinstance(x, (int, float)) for x in rng):
                low, high = rng
                if isinstance(low, int) and isinstance(high, int):
                    cs.add(UniformIntegerHyperparameter(name, lower=low, upper=high))
                else:
                    cs.add(UniformFloatHyperparameter(name, lower=low, upper=high))
            else:
                # Multiple discrete values (numbers or strings)
                cs.add(CategoricalHyperparameter(name, choices=rng))
        else:
            # Single value, treat as discrete
            cs.add(CategoricalHyperparameter(name, choices=[rng]))
    print(cs)
    return cs

# ========== Warm-start SMAC with Weighted History ==========
def load_history_to_smac(history_file: str, cs: ConfigurationSpace, smac_instance, topk: int = 10):
    """
    Load historical configurations into SMAC for warm-start.
    Each configuration is added multiple times proportionally to its weight.
    
    JSON format for each entry:
    {
        "config": {...},
        "qps": float,
        "weight": float  # optional, default=1.0
    }
    """
    import os
    import json
    from smac.configspace import Configuration

    if not os.path.exists(history_file):
        print(f"No history file found at {history_file}")
        return

    with open(history_file, 'r') as f:
        history = json.load(f)

    if not history:
        print("History is empty.")
        return

    # Get weights, default to 1.0 if missing
    weights = [entry.get("weight", 1.0) for entry in history]
    total_weight = sum(weights)

    # Compute proportional number of additions for each entry
    # Scale so that total additions ≈ topk
    n_additions = [max(1, int(round(w / total_weight * topk))) for w in weights]

    print(f"Adding historical configurations to SMAC based on weight, total entries: {len(history)}")

    for entry, count in zip(history, n_additions):
        cfg_dict = entry['config']
        cost = -entry['qps']  # SMAC minimizes cost
        cfg = Configuration(cs, values=cfg_dict)
        for _ in range(count):
            smac_instance.runhistory.add(cfg, cost, seed=42)
        print(f"Added cfg={cfg_dict} with cost={cost}, repeated {count} times")

    print("Warm-start completed.")

# ========== Run SMAC Optimization ==========
def run_mysql_with_history(range_file: str, history_file: str, trials: int = 50, topk: int = 10):
    cs = build_mysql_space_from_json(range_file)
    scenario = Scenario(configspace=cs, n_trials=trials, deterministic=True, seed=42)
    init_design = initial_design.LatinHypercubeInitialDesign(scenario, n_configs=0)  # Disable Latin Hypercube
    smac = HPO(scenario=scenario, initial_design=init_design, target_function=evaluate_mysql, overwrite=True)

    # Warm-start with historical records
    load_history_to_smac(history_file, cs, smac, topk=topk)

    # Optimization
    print("[run_mysql_with_history] Starting optimization ...")
    incumbent = smac.optimize()
    print("[run_mysql_with_history] Optimization finished, best configuration:", dict(incumbent))

    rh_path = f"mysql_history.json"
    smac.runhistory.save(rh_path)
    print(f"RunHistory saved to {rh_path}")
    return incumbent, rh_path

# ========== Main Process ==========
if __name__ == "__main__":
    RANGE_FILE = "param_range.json"
    HISTORY_FILE = "smac_history.json"

    print("MySQL parameter tuning started (Paramiko + historical warm start)")
    best_cfg, rh_path = run_mysql_with_history(RANGE_FILE, HISTORY_FILE, trials=100, topk=10)
    print("\nBest configuration:", dict(best_cfg))
    print("Estimated max QPS:", -evaluate_mysql(best_cfg, seed=42))
