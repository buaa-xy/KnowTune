import os
import json
import pickle
from tqdm import tqdm
import numpy as np
from sklearn.preprocessing import normalize
import faiss
import jieba
from rank_bm25 import BM25Okapi
import re
from py2neo import Graph
from openai import OpenAI
import httpx

# ---------------- OpenAI client ----------------
client = OpenAI(api_key="", base_url="", http_client=httpx.Client(verify=False))
embedding_client = OpenAI(api_key="", base_url="", http_client=httpx.Client(verify=False))

# ---------------- Neo4j ----------------
graph = Graph("bolt://localhost:7687", auth=("neo4j", "12345678"))

# ---------------- Utility Functions ----------------
def generate_embeddings(text, model="text-embedding-ada-002"):
    response = embedding_client.embeddings.create(input=text, model=model)
    return response.data[0].embedding

def build_index(file_name):
    docs = []
    with open(f"{file_name}.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            docs.append(json.loads(line))
    index_path = f"{file_name}_index.pkl"
    if os.path.exists(index_path):
        with open(index_path, "rb") as f:
            index = pickle.load(f)
        return index, docs

    embeddings = [generate_embeddings(d["info"]["desc"]) for d in tqdm(docs)]
    normalized_embeddings = normalize(np.array(embeddings).astype('float32'))
    d = normalized_embeddings.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(normalized_embeddings)
    with open(index_path, "wb") as f:
        pickle.dump(index, f)
    return index, docs

def build_bm25_index(docs):
    corpus = [doc["info"]["desc"] for doc in docs]
    tokenized_corpus = [list(jieba.cut(text)) for text in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    return bm25, tokenized_corpus

def retrieve_faiss(index, docs, queries, topk=15, threshold=0.7):
    results = {}
    for q in queries:
        emb = generate_embeddings(q)
        D, I = index.search(normalize(np.array(emb).astype('float32').reshape(1, -1)), topk)
        for idx, score in zip(I[0], D[0]):
            if score > threshold:
                results[idx] = max(results.get(idx, 0), score)
    sorted_idx = sorted(results, key=lambda x: results[x], reverse=True)
    return [docs[i] for i in sorted_idx][:topk]

def retrieve_bm25(bm25, tokenized_corpus, docs, queries, topk=15):
    scores = {}
    for q in queries:
        tokenized_q = list(jieba.cut(q))
        sc = bm25.get_scores(tokenized_q)
        for idx, s in enumerate(sc):
            scores[idx] = scores.get(idx, 0) + s
    sorted_idx = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [docs[i] for i in sorted_idx][:topk]

def get_related_parameter_names(param_name):
    query = """
    MATCH (p:Parameter_mysql {name: $name})
    OPTIONAL MATCH (p)-[:STRONG_RELATED_TO_mysql*1..3]->(strong:Parameter_mysql)
    OPTIONAL MATCH (p)-[:WEAK_RELATED_TO_mysql]->(weak:Parameter_mysql)
    RETURN DISTINCT collect(DISTINCT strong.name)+collect(DISTINCT weak.name) AS related_names
    """
    result = graph.run(query, name=param_name).data()
    return result[0]["related_names"] if result else []

def get_messages(role_prompt: str, history: str, usr_prompt: str):
    messages = []
    if role_prompt: messages.append({"role": "system", "content": role_prompt})
    if history: messages.append({"role": "assistant", "content": history})
    if usr_prompt: messages.append({"role": "user", "content": usr_prompt})
    return messages

# ---------------- LLM Single Parameter Recommendation ----------------
def generate_answer(query, static_profile, retrieved_faiss, retrieved_bm25):
    unique_names = set()
    combined = []
    for param in retrieved_faiss + retrieved_bm25:
        if param["name"] not in unique_names:
            param["related_params"] = get_related_parameter_names(param["name"])
            combined.append(param)
            unique_names.add(param["name"])

    context = "\n".join([
        f"{p['name']} | Related: {', '.join(p['related_params'])}" if p['related_params'] else p['name']
        for p in combined
    ])

    role_prompt = "You are a senior OS tuning expert with extensive parameter optimization experience."
    prompt = f"""
Assume you are an experienced MySQL database tuning expert.
Task:
1. Select up to 10 most important parameters.
2. Provide tuning ranges.
Candidate parameters:
{context}
System bottleneck: {query}
Database: MySQL 8.0.40
Environment: {static_profile}
Return strictly as JSON:
{{"parameter_name": {{"range": [...]}}}}
"""
    messages = get_messages(role_prompt, "", prompt)
    chat_completion = client.chat.completions.create(
        messages=messages,
        model="gpt-4o-mini",
        temperature=0.1
    )
    ans = chat_completion.choices[0].message.content
    match = re.search(r'\{.*\}', ans, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return ans
    return ans

def split_performance_report_to_queries(report_text: str):
    role_prompt = "You are an OS performance expert. Extract key bottleneck sentences per subsystem."
    user_prompt = f"Extract up to 8 short query sentences from the performance report representing system bottlenecks:\n{report_text}"
    messages = get_messages(role_prompt, "", user_prompt)
    resp = client.chat.completions.create(messages=messages, model="deepseek-chat", temperature=0.1)
    content = resp.choices[0].message.content.strip()
    return [q.strip() for q in content.strip("[]").split(",") if q.strip()]

def generate_bm25_keywords(report_text: str, max_keywords=5):
    role_prompt = "You are a performance tuning expert. Extract critical keywords."
    user_prompt = f"Extract up to {max_keywords} keywords from the report:\n{report_text}"
    messages = get_messages(role_prompt, "", user_prompt)
    resp = client.chat.completions.create(messages=messages, model="deepseek-chat", temperature=0.0)
    content = resp.choices[0].message.content.strip()
    return [kw.strip() for kw in content.strip("[]").split(",") if kw.strip()]
