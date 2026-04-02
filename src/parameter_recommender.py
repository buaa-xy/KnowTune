import json
import os
import pickle
from tqdm import tqdm
import numpy as np
from sklearn.preprocessing import normalize
import faiss
import jieba
from rank_bm25 import BM25Okapi
import re

from openai import OpenAI
import httpx
from py2neo import Graph


class ParameterRecommender:
    """
    A recommender class for MySQL parameter tuning based on retrieval-augmented generation (RAG)
    Supports Faiss vector search, BM25 keyword search, Neo4j knowledge graph, and LLM generation
    """

    def __init__(self,
                 openai_base_url="",
                 openai_api_key="",
                 embedding_base_url="",
                 embedding_api_key="",
                 neo4j_uri="bolt://localhost:7687",
                 neo4j_user="neo4j",
                 neo4j_password=""):
        """
        Initialize clients for OpenAI, embedding, and Neo4j knowledge graph
        """
        # ============================
        # OpenAI Client Initialization
        # ============================
        self.client = OpenAI(
            base_url=openai_base_url,
            api_key=openai_api_key,
            http_client=httpx.Client(verify=False)
        )

        self.embedding_client = OpenAI(
            base_url=embedding_base_url,
            api_key=embedding_api_key,
            http_client=httpx.Client(verify=False)
        )

        # ============================
        # Neo4j Knowledge Graph
        # ============================
        self.graph = Graph(neo4j_uri, auth=(neo4j_user, neo4j_password))

        # Lazy-loaded indexes (built after loading document file)
        self.faiss_index = None
        self.bm25_index = None
        self.tokenized_corpus = None
        self.docs = None

    # ============================
    # Utility Functions
    # ============================

    def get_messages(self, role_prompt: str, history: str, usr_prompt: str) -> list:
        """
        Construct chat messages for LLM input
        """
        messages = []
        if role_prompt != "":
            messages.append({"role": "system", "content": role_prompt})
        if len(history) > 0:
            messages.append({"role": "assistant", "content": history})
        if usr_prompt != "":
            messages.append({"role": "user", "content": usr_prompt})
        return messages

    def generate_embeddings(self, text, model="text-embedding-ada-002"):
        """
        Generate vector embeddings for a given text
        """
        response = self.embedding_client.embeddings.create(input=text, model=model)
        embedding = response.data[0].embedding
        # print("Embedding completed, dimension:", len(embedding))
        return embedding

    def build_index(self, file_name):
        """
        Build or load Faiss vector index from JSONL file
        """
        docs = []
        with open(f"{file_name}.jsonl", "r", encoding="utf-8") as f:
            for line in f.readlines():
                docs.append(json.loads(line))

        index_path = f"{file_name}_index.pkl"
        if os.path.exists(index_path):
            print(f"Cached index detected, loading from {index_path}...")
            with open(index_path, 'rb') as file:
                index = pickle.load(file)
            self.faiss_index = index
            self.docs = docs
            return index, docs

        embeddings = []
        for doc in tqdm(docs, desc=f"Building index for {file_name}..."):
            query_embedding = self.generate_embeddings(doc["info"]["desc"])
            embeddings.append(query_embedding)
        normalized_embeddings = normalize(np.array(embeddings).astype('float32'))
        d = len(embeddings[0])
        index = faiss.IndexFlatIP(d)
        index.add(normalized_embeddings)

        with open(index_path, 'wb') as file:
            pickle.dump(index, file)

        self.faiss_index = index
        self.docs = docs
        return index, docs

    def build_bm25_index(self, docs=None):
        """
        Build BM25 text index
        """
        if docs is None:
            docs = self.docs
        corpus = [doc["info"]["desc"] for doc in docs]
        tokenized_corpus = [list(jieba.cut(text)) for text in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        self.bm25_index = bm25
        self.tokenized_corpus = tokenized_corpus
        return bm25, tokenized_corpus

    def retrieve_faiss(self, query_list, topk=15, threshold=0.7):
        """
        Retrieve top-K relevant documents via Faiss vector search
        """
        index = self.faiss_index
        docs = self.docs

        result = {}
        unique = set()
        for query_data in query_list:
            query_embedding = self.generate_embeddings(query_data)
            D, I = index.search(normalize(np.array(query_embedding).astype('float32').reshape(1, -1)), topk)
            for idx, score in zip(I[0], D[0]):
                if score > threshold:
                    if idx not in unique:
                        result[idx] = score
                    result[idx] = max(result[idx], score)

        sorted_items = sorted(result.items(), key=lambda x: x[1], reverse=True)
        result_with_score = [(docs[idx], score) for idx, score in sorted_items]
        print("\n【Top-K Faiss Results with Scores】")
        for doc, score in result_with_score[:topk]:
            print(f"{doc['name']}: {score:.4f}")

        return [docs[idx] for idx, _ in sorted_items][:topk]

    def retrieve_bm25(self, query_list, topk=15):
        """
        Retrieve top-K documents using BM25 keyword search
        """
        bm25 = self.bm25_index
        tokenized_corpus = self.tokenized_corpus
        docs = self.docs

        result_scores = {}
        for query in query_list:
            tokenized_query = list(jieba.cut(query))
            scores = bm25.get_scores(tokenized_query)
            for idx, score in enumerate(scores):
                result_scores[idx] = result_scores.get(idx, 0) + score

        sorted_items = sorted(result_scores.items(), key=lambda x: x[1], reverse=True)
        result_with_score = [(docs[idx], score) for idx, score in sorted_items]

        print("\n【Top-K BM25 Results with Scores】")
        for doc, score in result_with_score[:topk]:
            print(f"{doc['name']}: {score:.4f}")

        return [docs[idx] for idx, _ in sorted_items][:topk]

    def get_related_parameter_names(self, param_name):
        """
        Retrieve related parameter names from Neo4j knowledge graph:
        - STRONG_RELATED_TO within 3 hops
        - WEAK_RELATED_TO within 1 hop
        Returns: ["param1", "param2", ...]
        """
        query = """
        MATCH (p:Parameter_mysql {name: $name})
        OPTIONAL MATCH (p)-[:STRONG_RELATED_TO_mysql*1..3]->(strong:Parameter_mysql)
        OPTIONAL MATCH (p)-[:WEAK_RELATED_TO_mysql]->(weak:Parameter_mysql)
        RETURN DISTINCT 
            collect(DISTINCT strong.name) + collect(DISTINCT weak.name) AS related_names
        """
        result = self.graph.run(query, name=param_name).data()
        if result and "related_names" in result[0]:
            return result[0]["related_names"]
        return []

    # ============================
    # LLM Generation Functions
    # ============================

    def generate_answer(self, query, static_profile, retrieved_parameters_faiss, retrieved_parameters_bm25):
        """
        Generate MySQL tuning suggestions using LLM, given retrieved parameters from Faiss and BM25
        """
        unique_names = set()
        combined_params = []
        for param in retrieved_parameters_faiss + retrieved_parameters_bm25:
            if param["name"] not in unique_names:
                related_names = self.get_related_parameter_names(param["name"])
                param["related_params"] = related_names
                combined_params.append(param)
                unique_names.add(param["name"])

        context_lines = []
        for param in combined_params:
            line = f"{param['name']}"
            if param.get("related_params"):
                related_text = ", ".join(param["related_params"])
                line += f" | Related: {related_text}"
            context_lines.append(line)

        context = "\n".join(context_lines)
        print("Parameter list for LLM generation:\n", context)
        print("------------------------------------------")

        role_prompt = "You are a senior OS tuning expert with extensive parameter optimization experience."

        prompt = f'''
        Assume you are an experienced MySQL database tuning expert.

        Task:
        1. Select up to 10 most important parameters from the candidate list.
        2. Provide recommended tuning ranges for each parameter:
        - Continuous parameters: [min, max]
        - Discrete or enumerated: list all options
        - Storage parameters (buffer, cache, size) in Bytes
        - Time parameters (timeout, delay) in seconds
        3. Include related parameters if necessary

        Candidate parameters and their relations:
        {context}

        System bottleneck: {query}
        Database: MySQL 8.0.40
        Environment info: {static_profile}

        Return strictly as JSON:
        {{
            "parameter_name": {{"range": [...]}}
        }}
        '''

        messages = self.get_messages(role_prompt, [], prompt)
        chat_completion = self.client.chat.completions.create(
            messages=messages,
            model="gpt-4o-mini",
            temperature=0.1
        )
        ans = chat_completion.choices[0].message.content

        match = re.search(r'\{.*\}', ans, re.DOTALL)
        if match:
            json_str = match.group(0)
            try:
                param_dict = json.loads(json_str)
                print("Parsed result as JSON")
                return param_dict
            except json.JSONDecodeError as e:
                print("JSON parse error:", e)
        else:
            print("No JSON found")
        return ans

    # ============================
    # LLM Generation Functions
    # ============================

    def generate_bm25_keywords(self, performance_report_text: str, max_keywords=5):
        """
        Use LLM to generate short keywords from performance report for BM25 search
        """
        role_prompt = "You are a performance tuning expert. Extract the top critical keywords from a report."
        user_prompt = f"""
        Extract up to {max_keywords} short keywords from the following performance report for parameter search:

        {performance_report_text}

        Return only an array of keywords, e.g., ["CPU bottleneck","IO latency","Memory pressure"]
        """
        messages = self.get_messages(role_prompt, "", user_prompt)
        response = self.client.chat.completions.create(
            messages=messages,
            model="deepseek-chat",
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        keywords = [kw.strip() for kw in content.strip("[]").split(",") if kw.strip()]
        print(keywords)
        return keywords

    def split_performance_report_to_queries(self, report_text: str) -> list:
        """
        Split a performance report into multiple concise query sentences for parameter retrieval
        """
        role_prompt = "You are an OS performance expert. Extract key bottleneck sentences per subsystem."
        user_prompt = f"""
        Extract up to 8 short query sentences from the performance report, each representing a system bottleneck (CPU, disk, memory, network, etc.)
        Report text:
        {report_text}
        Return directly as an array:
        ["query1","query2",...]
        """
        messages = self.get_messages(role_prompt, "", user_prompt)
        response = self.client.chat.completions.create(
            messages=messages,
            model="deepseek-chat",
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        queries = [q.strip() for q in content.strip("[]").split(",") if q.strip()]
        print(queries)
        return queries