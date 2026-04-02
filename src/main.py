#!/usr/bin/env python3
"""
Main pipeline for full-stack automated database tuning system.
Pipeline:
1. Performance Analysis -> performance_report.json
2. Parameter Recommendation & Initialization -> param_range.json + param_candidate.json
3. Phase One: Benchmark all candidates -> phase_one_results.json
4. Phase Two: SMAC Bayesian optimization -> best configuration
"""

import json
import os

# =======================
# Import all modules
# =======================
from performance_analyzer import PerformanceAnalyzer  # 性能分析
from parameter_recommender import ParameterRecommender  # 参数推荐
from parameter_initializer import ParameterInitializer  # 多维度候选生成
from BO_phase_one import PhaseOne                          # 批量压测
from BO_phase_two import PhaseTwo                      # SMAC 自动调优
from runner.mysql_runner import MySQLRunner             # 统一运行器


# =======================
# Configuration (ONE STOP SETUP)
# =======================
class TuningConfig:
    # ---------------------------
    # Step 1: Performance Analyzer Config
    # ---------------------------
    PERF_ANALYZER_CONFIG = {
        "servers": [
            {
                "ip": "127.0.0.1",
                "port": 22,
                "host_user": "",
                "password": "",
                "max_retries": 3,
                "delay": 2,
                "app": "mysql",
                "target_process_name": "mysqld"
            }
        ],
        "feature": [
            {
                "pressure_test_mode": "sysbench",
                "microDep_collector": False
            }
        ],
        "benchmark_cmd": "sysbench oltp_read_write run"
    }

    # ---------------------------
    # Step 2: LLM / Retrieval Config
    # ---------------------------
    OPENAI_BASE_URL = ""
    OPENAI_API_KEY = ""
    EMBEDDING_BASE_URL = ""
    EMBEDDING_API_KEY = ""
    NEO4J_PASSWORD = ""

    # ---------------------------
    # MySQL Runner Config
    # ---------------------------
    MYSQL_RUNNER_CONFIG = {
        "remote_host": "",
        "remote_user": "root",
        "remote_pwd": "",
        "db_user": "root",
        "db_pass": "123456",
        "db_name": "sbtest"
    }

    # ---------------------------
    # File Paths
    # ---------------------------
    PERF_REPORT_PATH = "performance_report.json"
    PARAM_RANGE_PATH = "param_range.json"
    PARAM_CANDIDATE_PATH = "param_candidate.json"
    PHASE_ONE_RESULT = "phase_one_results.json"
    PHASE_TWO_HISTORY = "phase_two_smac_history.json"

    # ---------------------------
    # Environment Description
    # ---------------------------
    ENVIRONMENT_INFO = """
    - Workload: OLTP, sysbench mixed read/write, 50% read/write, 18 threads
    - Data: 2GB across 10 tables, 50,000 rows each
    - DB Kernel: MySQL 8.0.40
    - Hardware: 1288 vCPU, 256GB RAM
    - OS: Linux Ubuntu 22.04
    """


# =======================
# Main Tuning Pipeline
# =======================
def run_full_tuning_pipeline():
    cfg = TuningConfig()
    print("=" * 80)
    print(" Starting FULL AUTOMATED TUNING PIPELINE ".center(80, '='))
    print("=" * 80)

    # -------------------------------------------------------------------------
    # Step 1: Run Performance Analysis
    # -------------------------------------------------------------------------
    print("\n[1/4] Running Performance Analyzer...")
    profiler = PerformanceAnalyzer(cfg.PERF_ANALYZER_CONFIG)
    profiler.run()
    print(f"✅ Performance report saved to {cfg.PERF_REPORT_PATH}")

    # -------------------------------------------------------------------------
    # Step 2: Parameter Recommendation + Multi-perspective Initialization
    # -------------------------------------------------------------------------
    print("\n[2/4] Running Parameter Recommendation & Initialization...")

    # Load report
    with open(cfg.PERF_REPORT_PATH, "r", encoding="utf-8") as f:
        perf_json = json.load(f)
    perf_report = perf_json.get("report", "")
    if not perf_report:
        raise ValueError("Empty performance report")

    # Initialize recommender
    recommender = ParameterRecommender(
        openai_base_url=cfg.OPENAI_BASE_URL,
        openai_api_key=cfg.OPENAI_API_KEY,
        embedding_base_url=cfg.EMBEDDING_BASE_URL,
        embedding_api_key=cfg.EMBEDDING_API_KEY,
        neo4j_password=cfg.NEO4J_PASSWORD
    )

    # Retrieve parameters
    query_list = recommender.split_performance_report_to_queries(perf_report)
    index, docs = recommender.build_index(data_path="mysql")
    bm25, tokenized_corpus = recommender.build_bm25_index()
    retrieved_faiss = recommender.retrieve_faiss(query_list)

    # Generate keywords & retrieve
    kws_q = " ; ".join(query_list)
    bm25_keywords = recommender.generate_bm25_keywords(kws_q)
    retrieved_bm25 = recommender.retrieve_bm25(bm25_keywords)

    # Merge & save param_range.json
    unique_names = set()
    merged_params = []
    for p in retrieved_faiss + retrieved_bm25:
        if p["name"] not in unique_names:
            merged_params.append(p)
            unique_names.add(p["name"])

    with open(cfg.PARAM_RANGE_PATH, "w", encoding="utf-8") as f:
        json.dump(merged_params, f, indent=4, ensure_ascii=False)

    # Multi-perspective candidate generation
    initializer = ParameterInitializer(api_key=cfg.OPENAI_API_KEY, base_url=cfg.OPENAI_BASE_URL)
    param_knowledge = {p["name"]: {"related": p.get("related_params", [])} for p in merged_params}
    candidates = initializer.recommend_params(
        param_knowledge, merged_params, perf_report, cfg.ENVIRONMENT_INFO
    )

    with open(cfg.PARAM_CANDIDATE_PATH, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=4, ensure_ascii=False)

    print(f"✅ Parameter range saved: {cfg.PARAM_RANGE_PATH}")
    print(f"✅ Parameter candidates saved: {cfg.PARAM_CANDIDATE_PATH}")

    # -------------------------------------------------------------------------
    # Step 3: Phase One - Benchmark All Candidates
    # -------------------------------------------------------------------------
    print("\n[3/4] Running Phase One: Benchmark all parameter candidates...")

    runner = MySQLRunner(**cfg.MYSQL_RUNNER_CONFIG)
    phase1 = PhaseOne(runner=runner)
    phase1.run(
        json_config_path=cfg.PARAM_CANDIDATE_PATH,
        output_json=cfg.PHASE_ONE_RESULT
    )

    print(f"✅ Phase One results saved: {cfg.PHASE_ONE_RESULT}")

    # -------------------------------------------------------------------------
    # Step 4: Phase Two - SMAC Bayesian Optimization
    # -------------------------------------------------------------------------
    print("\n[4/4] Running Phase Two: SMAC Automated Tuning...")

    phase2 = PhaseTwo(runner=runner)
    best_config, history_path = phase2.run_mysql_with_history(
        range_file=cfg.PARAM_RANGE_PATH,
        history_file=cfg.PHASE_ONE_RESULT,
        trials=100,
        topk=10
    )

    print("\n" + "=" * 80)
    print(" FINAL BEST CONFIGURATION ".center(80, '='))
    print(json.dumps(best_config, indent=4, ensure_ascii=False))
    print("=" * 80)

    print("\n✅ All pipeline completed successfully!")


# =======================
# Run
# =======================
if __name__ == "__main__":
    run_full_tuning_pipeline()