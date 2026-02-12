# -*- coding: utf-8 -*-
"""
LLM Backend - 多模型后端统一接口
================================
支持 OpenAI、Claude、Gemini、DeepSeek、Kimichat 及本地模型

作者: Claude
日期: 2026-02-12
"""

import json
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field


def _ensure_package(import_name: str, pip_name: str):
    """尝试导入包，若不存在则自动pip安装"""
    try:
        __import__(import_name)
    except ImportError:
        print(f"[自动安装] 正在安装 {pip_name} ...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pip_name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print(f"[自动安装] {pip_name} 安装完成")


@dataclass
class Message:
    """对话消息"""
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: str
    tool_calls: List[Dict] = field(default_factory=list)
    tool_call_id: str = None


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    tool_calls: List[Dict] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Dict[str, int] = field(default_factory=dict)


class LLMBackend(ABC):
    """LLM后端抽象基类"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @abstractmethod
    def chat(self, messages: List[Message], tools: List[ToolDefinition] = None) -> LLMResponse:
        """发送对话请求"""
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """获取可用模型列表"""
        pass


class OpenAICompatibleBackend(LLMBackend):
    """OpenAI兼容API后端（支持DeepSeek、Kimichat、Ollama等）"""

    def __init__(self, api_key: str = None, base_url: str = "https://api.openai.com/v1",
                 model: str = "gpt-4o"):
        super().__init__(api_key, base_url, model)
        self._client = None

    def _get_client(self):
        if self._client is None:
            _ensure_package("openai", "openai")
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def chat(self, messages: List[Message], tools: List[ToolDefinition] = None) -> LLMResponse:
        client = self._get_client()

        # 转换消息格式
        api_messages = []
        for msg in messages:
            api_msg = {"role": msg.role, "content": msg.content}
            if msg.tool_call_id:
                api_msg["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                api_msg["tool_calls"] = msg.tool_calls
            api_messages.append(api_msg)

        # 转换工具格式
        api_tools = None
        if tools:
            api_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters
                    }
                }
                for tool in tools
            ]

        # 调用API
        kwargs = {"model": self.model, "messages": api_messages}
        if api_tools:
            kwargs["tools"] = api_tools
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        # 解析响应
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens
            }
        )

    def get_available_models(self) -> List[str]:
        client = self._get_client()
        try:
            models = client.models.list()
            return [m.id for m in models.data]
        except Exception:
            return [self.model]


class ClaudeBackend(LLMBackend):
    """Claude (Anthropic) 后端"""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        super().__init__(api_key, model=model)
        self._client = None

    def _get_client(self):
        if self._client is None:
            _ensure_package("anthropic", "anthropic")
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def chat(self, messages: List[Message], tools: List[ToolDefinition] = None) -> LLMResponse:
        client = self._get_client()

        # 分离system消息
        system_msg = ""
        api_messages = []
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            elif msg.role == "tool":
                api_messages.append({
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": msg.tool_call_id, "content": msg.content}]
                })
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        # 转换工具格式
        api_tools = None
        if tools:
            api_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters
                }
                for tool in tools
            ]

        # 调用API
        kwargs = {"model": self.model, "max_tokens": 4096, "messages": api_messages}
        if system_msg:
            kwargs["system"] = system_msg
        if api_tools:
            kwargs["tools"] = api_tools

        response = client.messages.create(**kwargs)

        # 解析响应
        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input)
                    }
                })

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens
            }
        )

    def get_available_models(self) -> List[str]:
        return [
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-6",
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022"
        ]


class GeminiBackend(LLMBackend):
    """Google Gemini 后端"""

    def __init__(self, api_key: str = None, model: str = "gemini-2.0-flash"):
        super().__init__(api_key, model=model)
        self._client = None

    def _get_client(self):
        if self._client is None:
            _ensure_package("google.generativeai", "google-generativeai")
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai
        return self._client

    @staticmethod
    def _clean_schema_for_gemini(schema: dict) -> dict:
        """清理JSON Schema中Gemini不支持的字段（additionalProperties, default等）"""
        if not isinstance(schema, dict):
            return schema

        # Gemini支持的字段
        supported_keys = {
            "type", "description", "properties", "required",
            "enum", "items", "format", "nullable"
        }

        cleaned = {}
        for key, value in schema.items():
            if key not in supported_keys:
                continue
            if key == "properties" and isinstance(value, dict):
                cleaned[key] = {
                    k: GeminiBackend._clean_schema_for_gemini(v)
                    for k, v in value.items()
                }
            elif key == "items" and isinstance(value, dict):
                cleaned[key] = GeminiBackend._clean_schema_for_gemini(value)
            else:
                cleaned[key] = value

        return cleaned

    def chat(self, messages: List[Message], tools: List[ToolDefinition] = None) -> LLMResponse:
        genai = self._get_client()

        # 转换工具为Gemini格式，清理不支持的schema字段
        gemini_tools = None
        if tools:
            from google.generativeai.types import Tool, FunctionDeclaration
            declarations = []
            for tool in tools:
                cleaned_params = self._clean_schema_for_gemini(tool.parameters)
                declarations.append(FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=cleaned_params
                ))
            gemini_tools = [Tool(function_declarations=declarations)]

        # 创建模型
        model = genai.GenerativeModel(self.model, tools=gemini_tools)

        # 构建对话历史
        history = []
        system_instruction = None
        for msg in messages[:-1]:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                history.append({"role": "user", "parts": [msg.content]})
            elif msg.role == "assistant":
                history.append({"role": "model", "parts": [msg.content]})

        chat = model.start_chat(history=history)
        response = chat.send_message(messages[-1].content if messages else "")

        # 解析响应
        content = ""
        tool_calls = []
        for part in response.parts:
            if hasattr(part, 'text'):
                content += part.text
            elif hasattr(part, 'function_call'):
                fc = part.function_call
                tool_calls.append({
                    "id": f"call_{fc.name}",
                    "type": "function",
                    "function": {
                        "name": fc.name,
                        "arguments": json.dumps(dict(fc.args))
                    }
                })

        return LLMResponse(content=content, tool_calls=tool_calls)

    def get_available_models(self) -> List[str]:
        return [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite"
        ]


# ============= 预配置的后端工厂 =============

BACKEND_CONFIGS = {
    "openai": {
        "class": OpenAICompatibleBackend,
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "env_key": "OPENAI_API_KEY"
    },
    "deepseek": {
        "class": OpenAICompatibleBackend,
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY"
    },
    "kimichat": {
        "class": OpenAICompatibleBackend,
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "env_key": "KIMI_API_KEY"
    },
    "ollama": {
        "class": OpenAICompatibleBackend,
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5:7b",
        "env_key": None  # 本地无需API key
    },
    "claude": {
        "class": ClaudeBackend,
        "default_model": "claude-sonnet-4-5-20250929",
        "env_key": "ANTHROPIC_API_KEY"
    },
    "gemini": {
        "class": GeminiBackend,
        "default_model": "gemini-2.5-flash",
        "env_key": "GOOGLE_API_KEY"
    }
}


def create_backend(provider: str, api_key: str = None, model: str = None) -> LLMBackend:
    """
    创建LLM后端实例

    参数:
    -----
    provider : str
        提供商名称: 'openai', 'claude', 'gemini', 'deepseek', 'kimichat', 'ollama'
    api_key : str, optional
        API密钥，如果为None则从环境变量读取
    model : str, optional
        模型名称，如果为None则使用默认模型

    返回:
    -----
    LLMBackend: 后端实例
    """
    if provider not in BACKEND_CONFIGS:
        raise ValueError(f"不支持的提供商: {provider}。支持: {list(BACKEND_CONFIGS.keys())}")

    config = BACKEND_CONFIGS[provider]

    # 获取API key
    if api_key is None and config.get("env_key"):
        api_key = os.environ.get(config["env_key"])

    # 对于不需要API key的本地服务（如Ollama），设置占位符以满足OpenAI SDK要求
    if api_key is None and config.get("env_key") is None:
        api_key = "not-needed"

    # 获取模型
    if model is None:
        model = config["default_model"]

    # 创建实例
    backend_class = config["class"]
    kwargs = {"api_key": api_key, "model": model}

    if "base_url" in config:
        kwargs["base_url"] = config["base_url"]

    return backend_class(**kwargs)


# ============= 测试代码 =============

if __name__ == "__main__":
    print("=== LLM Backend 测试 ===")
    print(f"支持的后端: {list(BACKEND_CONFIGS.keys())}")

    # 测试Ollama（本地）
    try:
        backend = create_backend("ollama", model="qwen2.5:7b")
        print(f"\nOllama后端创建成功，模型: {backend.model}")
    except Exception as e:
        print(f"Ollama测试失败: {e}")
