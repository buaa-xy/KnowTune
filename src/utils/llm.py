from openai import OpenAI
import httpx
import sys
import os
# 获取项目根目录的绝对路径
project_root = (os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# 将项目根目录添加到 sys.path
sys.path.append(project_root)


#获取llm配置

model_name = ""
api_key = ""
base_url = ""

client = OpenAI(
    base_url= base_url,
    api_key= api_key,
    http_client=httpx.Client(verify=False)
)

def get_llm_response(prompt: str) -> str:
    response = client.chat.completions.create(
        model = model_name, #"gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096
    )
    return response.choices[0].message.content