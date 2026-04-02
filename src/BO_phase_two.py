#!/usr/bin/env python3
"""
phase_two.py
Tune MySQL parameters using SMAC, modify MySQL configuration remotely via Paramiko, and run sysbench benchmarks.
Parameter ranges and historical results are loaded from JSON files.
This is Phase Two: SMAC Bayesian Optimization (reuses MySQLRunner for testing)
"""

import os
import json
from smac import HyperparameterOptimizationFacade as HPO
from smac import Scenario, initial_design
from smac.runhistory.runhistory import RunHistory
from ConfigSpace import ConfigurationSpace, UniformIntegerHyperparameter, UniformFloatHyperparameter, CategoricalHyperparameter, Configuration

# Reuse the existing MySQL runner (NO duplicate code)
from runner.mysql_runner import MySQLRunner


class PhaseTwo:
    """
    Phase Two: SMAC-based Automated MySQL Tuning
    Uses external MySQLRunner for remote configuration and benchmarking
    """

    def __init__(self, runner: MySQLRunner):
        self.runner = runner

    # ========== SMAC Objective Function ==========
    def evaluate_mysql(self, cfg: dict, seed: int) -> float:
        """
        SMAC objective function: maximize QPS, so return negative QPS for minimization
        """
        print("----------------------------")
        print(cfg)
        res = self.runner.test_config(cfg)
        qps = res['qps']
        print(f"[evaluate_mysql] cfg={cfg}  QPS={qps:.4f}")
        return -qps  # SMAC minimizes, return negative QPS to maximize

    # ========== Build Search Space from JSON ==========
    def build_mysql_space_from_json(self, range_file: str) -> ConfigurationSpace:
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
    def load_history_to_smac(self, history_file: str, cs: ConfigurationSpace, smac_instance, topk: int = 10):
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
    def run_mysql_with_history(self, range_file: str, history_file: str, trials: int = 50, topk: int = 10):
        cs = self.build_mysql_space_from_json(range_file)
        scenario = Scenario(configspace=cs, n_trials=trials, deterministic=True, seed=42)
        init_design = initial_design.LatinHypercubeInitialDesign(scenario, n_configs=0)  # Disable Latin Hypercube
        smac = HPO(scenario=scenario, initial_design=init_design, target_function=self.evaluate_mysql, overwrite=True)

        # Warm-start with historical records
        self.load_history_to_smac(history_file, cs, smac, topk=topk)

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
    # Initialize reused MySQL runner
    runner = MySQLRunner(
        remote_host="",
        remote_user="root",
        remote_pwd="",
        db_user="root",
        db_pass="123456",
        db_name="sbtest"
    )

    phase_two = PhaseTwo(runner)

    RANGE_FILE = "../param_range.json"
    HISTORY_FILE = "../phase_one_results.json"

    print("MySQL parameter tuning started (Paramiko + historical warm start)")
    best_cfg, rh_path = phase_two.run_mysql_with_history(RANGE_FILE, HISTORY_FILE, trials=100, topk=10)
    print("\nBest configuration:", dict(best_cfg))
    print("Estimated max QPS:", -phase_two.evaluate_mysql(best_cfg, seed=42))