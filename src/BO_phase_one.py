import json
import os
import csv
from runner.mysql_runner import MySQLRunner

class PhaseOne:
    """
    Phase One: Automated batch testing for multiple candidate parameter configurations.
    Loads JSON parameter plans, runs benchmark via a given runner, records CSV logs,
    and outputs final JSON results.
    Runner can be replaced (MySQL/PostgreSQL/Redis/OS etc.) without changing logic.
    """

    def __init__(self, runner, csv_log="./mysql_qps_tps_avg_p95_log.csv"):
        """
        Initialize Phase One with a test runner and log path.
        
        Args:
            runner: Test runner instance (e.g., MySQLRunner)
            csv_log: Path to CSV file for recording test history
        """
        self.runner = runner
        self.csv_log = csv_log
        # Create log directory if not exists
        os.makedirs(os.path.dirname(csv_log), exist_ok=True)

    def load_configs(self, json_path):
        """
        Load multiple parameter configurations from JSON file.
        
        Args:
            json_path: Path to input JSON config file
        
        Returns:
            List of configuration dicts with name, params, weight
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        config_list = []
        for name, item in data.items():
            config_list.append({
                "name": name,
                "params": item["params"],
                "weight": item.get("weight", 1.0)
            })
        return config_list

    def write_csv(self, row):
        """
        Write a single test result to CSV log file.
        Creates header if file does not exist.
        
        Args:
            row: List containing [config, qps, tps, avg_lat, p95]
        """
        file_exists = os.path.isfile(self.csv_log)
        with open(self.csv_log, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["config", "qps", "tps", "avg", "p95"])
            writer.writerow(row)

    def run(self, json_config_path, output_json="phase_one_results.json"):
        """
        Main entry for batch testing all configurations:
        1. Load all candidate configs
        2. Test each one using the runner
        3. Write results to CSV
        4. Save all history to JSON
        5. Return full test history
        
        Args:
            json_config_path: Path to candidate parameter JSON
            output_json: Path to save final test results
        
        Returns:
            List of result dicts for all configurations
        """
        # Load all parameter sets
        configs = self.load_configs(json_config_path)
        param_sets = [c["params"] for c in configs]
        history = []

        # Test each configuration in sequence
        for i, cfg in enumerate(param_sets, 1):
            print(f"\n=== Testing config {i}/{len(param_sets)} ===")
            res = self.runner.test_config(cfg)
            history.append(res)
            self.write_csv([res["config"], res["qps"], res["tps"], res["avg"], res["p95"]])
            print(f"Result: QPS={res['qps']:.2f} | TPS={res['tps']:.2f} | P95={res['p95']:.2f}")

        # Save full history to JSON file
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
        print(f"\n✅ Results saved to {output_json}")
        return history


if __name__ == "__main__":
    """
    Main execution: Initialize MySQL runner and start Phase One batch tuning.
    Modify remote info and run to start automatic testing.
    """
    # Initialize MySQL runner with remote server info
    runner = MySQLRunner(
        remote_host="",
        remote_user="root",
        remote_pwd="",
        db_user="root",
        db_pass="123456",
        db_name="sbtest"
    )

    # Initialize Phase One tuning framework
    phase = PhaseOne(
        runner=runner,
        csv_log="./mysql_qps_tps_avg_p95_log.csv"
    )

    # Run batch testing
    history = phase.run(
        json_config_path="../param_candidate.json",
        output_json="phase_one_results.json"
    )

    print("\n=== Phase One Tuning Finished ===")