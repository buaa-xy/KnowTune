import json
from openai import OpenAI
import httpx
from retrieval_and_generation import get_messages
import re

# ---------------- OpenAI client ----------------
client = OpenAI(
    api_key="",
    base_url="",
    http_client=httpx.Client(verify=False)
)

# ---------------- Multi-Perspective Parameter Recommendation ----------------
def recommend_params(parameter_knowledge, parameter_ranges, performance_report, environment):
    """
    Generate multiple candidate parameter configurations from different optimization perspectives.

    Args:
        parameter_knowledge (dict or str): Existing knowledge of system parameters, including dependencies, categories, historical ranges, and criticality
        parameter_ranges (dict): Recommended parameter ranges for each parameter
        performance_report (str): Current system performance report or bottleneck description
        environment (str): System environment information, including CPU, memory, storage, OS, MySQL version, etc.

    Returns:
        dict: Multi-perspective candidate configurations and weights
        Example:
        {
            "HighThroughput": {"params": {"param1": value1, "param2": value2}, "weight": 1.0},
            "LowLatency": {"params": {"param1": value3, "param2": value4}, "weight": 1.0},
            ...
        }
    """

    role_prompt = (
        "You are a senior operating system and database tuning expert, with extensive experience in MySQL "
        "and Linux system performance optimization. You are highly skilled in generating multiple candidate "
        "parameter configurations based on different optimization perspectives, considering parameter dependencies, "
        "system environment, workload characteristics, and historical tuning knowledge."
    )

    prompt = f"""
Task: Generate multiple candidate parameter configurations for a MySQL system from multiple optimization perspectives.

Input:
1. Parameter knowledge (including dependencies, categories, historical tuning ranges, criticality):
{json.dumps(parameter_knowledge, ensure_ascii=False, indent=2)}

2. Single-parameter recommended ranges (from previous recommendation step):
{json.dumps(parameter_ranges, ensure_ascii=False, indent=2)}

3. System performance report:
{performance_report}

4. System environment:
{environment}

Optimization perspectives and descriptions:

1. High Throughput:
   - Maximize queries per second (QPS)
   - Prioritize configurations that improve disk I/O throughput and buffer utilization
   - Optimize parallelism and concurrency handling
   - Balance CPU and memory usage to avoid bottlenecks

2. Low Latency:
   - Minimize response time and tail latency
   - Focus on reducing locks, contention, and wait times
   - Prioritize configurations that improve cache hit rates and I/O scheduling
   - Ensure that latency-sensitive operations are optimized

3. High Concurrency:
   - Support a high number of simultaneous connections or transactions
   - Optimize thread handling, connection pooling, and resource allocation
   - Avoid deadlocks and reduce transaction wait times
   - Ensure fairness across queries and sessions

4. Cache & Memory Efficiency:
   - Maximize the effectiveness of caches and memory buffers
   - Optimize buffer pool sizes, query caches, and memory allocation
   - Prevent memory thrashing and swapping
   - Balance between memory footprint and performance gains

5. Network Adaptability:
   - Optimize for network latency and bandwidth utilization
   - Prioritize configurations that reduce network overhead for distributed transactions
   - Consider TCP/IP tuning, network buffers, and packet handling
   - Maintain stability under variable network loads

6. Global Balanced:
   - Provide a balanced configuration that considers all objectives simultaneously
   - Weight parameters to achieve an overall optimal trade-off
   - Avoid extreme settings that favor one perspective at the cost of others
   - Ensure system stability and reliability under diverse workloads

Requirements:
- For each perspective, select relevant parameters from the candidate list
- All parameter values must strictly fall within the provided ranges
- Enumerated/discrete parameters should list all allowed options
- Time-related parameters must use seconds; size-related parameters must use bytes
- Include related parameters if needed to maintain performance or stability
- Assign a weight to each perspective if applicable
- Return strictly as JSON without any explanations or additional text

Output JSON format example:
{{
  "HighThroughput": {{
      "params": {{
          "innodb_buffer_pool_size": 536870912,
          "innodb_log_file_size": 134217728
      }},
      "weight": 1.0
  }},
  "LowLatency": {{
      "params": {{
          "innodb_buffer_pool_size": 268435456,
          "innodb_log_file_size": 67108864
      }},
      "weight": 1.0
  }},
  "HighConcurrency": {{
      "params": {{
          "max_connections": 500,
          "innodb_thread_concurrency": 32
      }},
      "weight": 1.0
  }},
  "CacheMemoryEfficiency": {{
      "params": {{
          "query_cache_size": 67108864,
          "innodb_buffer_pool_instances": 8
      }},
      "weight": 1.0
  }},
  "NetworkAdaptability": {{
      "params": {{
          "net_read_timeout": 30,
          "net_write_timeout": 30
      }},
      "weight": 1.0
  }},
  "GlobalBalanced": {{
      "params": {{
          "innodb_buffer_pool_size": 429496729,
          "max_connections": 400
      }},
      "weight": 1.0
  }}
}}

Please strictly follow the JSON format and do not include any text outside the JSON.
"""

    messages = get_messages(role_prompt, history="", usr_prompt=prompt)

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
