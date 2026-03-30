import json
from param_recommand import (
    build_index, build_bm25_index, retrieve_faiss, retrieve_bm25,
    generate_bm25_keywords, split_performance_report_to_queries
)
from initialization import recommend_params

# ============================
# Main Execution
# ============================
if __name__ == "__main__":

    # ---------------- Example Performance Report ----------------
    perf_report = """
The MySQL system is experiencing high disk I/O utilization and frequent lock waits under sysbench OLTP workload. 
Observed latency spikes in transaction commits and occasional deadlocks under concurrent sessions. 
Memory buffer pool is underutilized, while network utilization is moderate.
"""

    # ---------------- Path to JSONL knowledge DB ----------------
    data_path = "mysql"  # JSONL files: 0*.jsonl, 1*.jsonl, etc.

    # ---------------- Step 1: Split performance report ----------------
    query_list = split_performance_report_to_queries(perf_report)
    print("Performance report queries:", query_list)

    # ---------------- Step 2: Build/load FAISS and BM25 indices ----------------
    index, docs = build_index(data_path)
    bm25, tokenized_corpus = build_bm25_index(docs)

    # ---------------- Step 3: Retrieve candidate parameters ----------------
    retrieved_faiss = retrieve_faiss(index, docs, query_list)

    kws_q = " ; ".join(query_list)
    bm25_keywords = generate_bm25_keywords(kws_q)
    print("LLM-generated BM25 keywords:", bm25_keywords)

    retrieved_bm25 = retrieve_bm25(bm25, tokenized_corpus, docs, bm25_keywords)

    # ---------------- Step 4: Merge results ----------------
    # For simplicity, just merge and remove duplicates
    unique_names = set()
    merged_params = []
    for param in retrieved_faiss + retrieved_bm25:
        if param["name"] not in unique_names:
            merged_params.append(param)
            unique_names.add(param["name"])

    # Save intermediate merged params
    with open("param_range.json", "w", encoding="utf-8") as f:
        json.dump(merged_params, f, ensure_ascii=False, indent=4)
    print("Merged parameter list saved to param_range.json")

    # ---------------- Step 5: Prepare environment and knowledge ----------------
    param_knowledge = {p["name"]: {"related": p.get("related_params", [])} for p in merged_params}
    environment = """
- Workload: OLTP, sysbench mixed read/write, 50% read/write, 18 threads
- Data: 2GB across 10 tables, 50,000 rows each
- DB Kernel: MySQL 8.0.40
- Hardware: 8 vCPU, 32GB RAM
- OS: Linux Ubuntu 22.04
"""

    # ---------------- Step 6: Multi-Perspective Parameter Recommendation ----------------
    result = recommend_params(param_knowledge, merged_params, perf_report, environment)

    print("------------------------------------")
    print("Generated multiple candidate configurations:\n", json.dumps(result, indent=4, ensure_ascii=False))

    # Save final candidate configurations
    with open("param_candidate.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    print("Candidate configurations saved to param_candidate.json")
