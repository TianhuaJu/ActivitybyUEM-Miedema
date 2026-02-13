# -*- coding: utf-8 -*-
"""
LLM Module - 大语言模型集成
===========================
提供多后端LLM支持和热力学计算工具调用

组件:
-----
- llm_backend: 多后端统一接口 (OpenAI, Claude, Gemini, DeepSeek, Kimichat, Ollama)
- tools: 热力学计算函数的工具定义
- chat_agent: 对话代理，协调LLM与工具调用

使用示例:
---------
```python
from llm import ChatAgent, quick_calculate

# 方式1: 创建代理进行多轮对话
agent = ChatAgent(provider="ollama", model="qwen2.5:7b")
response = agent.chat("计算Al-5%Cu合金的液相线温度")
print(response)

# 方式2: 快速单次计算
result = quick_calculate("Al中1%Cu会使熔点降低多少?")
print(result)
```

作者: Claude
日期: 2026-02-12
"""

from llm.llm_backend import (
    LLMBackend,
    Message,
    ToolDefinition,
    LLMResponse,
    OpenAICompatibleBackend,
    ClaudeBackend,
    GeminiBackend,
    create_backend,
    BACKEND_CONFIGS
)

from llm.tools import (
    ThermodynamicTools,
    TOOL_SCHEMAS,
    TOOL_DESCRIPTIONS
)

from llm.knowledge import KnowledgeStore

from llm.chat_agent import (
    ChatAgent,
    ChatSession,
    StreamingChatAgent,
    quick_calculate,
    interactive_cli,
    SYSTEM_PROMPT
)

__all__ = [
    # Backend classes
    "LLMBackend",
    "OpenAICompatibleBackend",
    "ClaudeBackend",
    "GeminiBackend",
    "create_backend",
    "BACKEND_CONFIGS",

    # Data classes
    "Message",
    "ToolDefinition",
    "LLMResponse",

    # Tools
    "ThermodynamicTools",
    "TOOL_SCHEMAS",
    "TOOL_DESCRIPTIONS",

    # Knowledge
    "KnowledgeStore",

    # Agent
    "ChatAgent",
    "ChatSession",
    "StreamingChatAgent",
    "quick_calculate",
    "interactive_cli",
    "SYSTEM_PROMPT"
]
