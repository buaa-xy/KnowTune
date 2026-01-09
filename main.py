# -*- coding: utf-8 -*-
"""Agent entry point for system tuning skill (OpenAI-compatible model)."""
import asyncio
import os
import httpx

from agentscope.agent import ReActAgent, UserAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel
from agentscope.tool import (
    Toolkit,
    execute_shell_command,
    execute_python_code,
    view_text_file,
)


async def main() -> None:
    """Interactive entry point for the AutoTuner agent."""
    toolkit = Toolkit()

    # ===== 基础工具（skill 执行必需） =====
    toolkit.register_tool_function(execute_shell_command)
    toolkit.register_tool_function(execute_python_code)
    toolkit.register_tool_function(view_text_file)

    # ===== 注册系统调优 skill =====
    toolkit.register_agent_skill("./skill/euler-copilot-tune")

    # ===== Async HTTP client（关闭 SSL 校验） =====
    async_http_client = httpx.AsyncClient(verify=False)

    # ===== 创建智能体 =====
    agent = ReActAgent(
        name="AutoTuner",
        sys_prompt="You are a helpful assistant named AutoTuner.",
        model=OpenAIChatModel(
            api_key="",  # 填入你的 API key
            model_name="deepseek-chat",
            stream=True,
            client_kwargs={
                "base_url": "https://api.deepseek.com",
                "http_client": async_http_client,
            },
        ),
        formatter=OpenAIChatFormatter(),
        toolkit=toolkit,
        memory=InMemoryMemory(),
    )

    # ===== 创建用户交互端 =====
    user = UserAgent("User")
    msg = None

    print("\033[1;32mInteractive AutoTuner started. Type 'exit' to quit.\033[0m")

    # ===== 交互循环 =====
    while True:
        # 等待用户输入
        msg = await user(msg)

        # 退出条件
        if msg.get_text_content().strip().lower() in ["exit", "quit", "bye"]:
            print("\033[1;32mGoodbye!\033[0m")
            break

        # 将用户输入发送给 agent 并获取回复
        msg = await agent(msg)

    # ===== 关闭 async_http_client =====
    await async_http_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
