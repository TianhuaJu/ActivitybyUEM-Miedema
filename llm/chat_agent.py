# -*- coding: utf-8 -*-
"""
Chat Agent - 对话式热力学计算代理
=================================
协调LLM与工具调用，实现自然语言交互式计算

作者: Claude
日期: 2026-02-12
"""

import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.llm_backend import (
    LLMBackend, Message, LLMResponse, ToolDefinition,
    create_backend, BACKEND_CONFIGS
)
from llm.tools import ThermodynamicTools


SYSTEM_PROMPT = """你是一个专业的热力学计算助手，基于UEM-Miedema模型框架，可以帮助用户进行合金热力学性质的全面计算。

你可以使用以下工具进行计算：

=== 基础热力学性质 ===

1. **calculate_activity** - 计算活度 a = γ × x
2. **calculate_activity_coefficient** - 计算活度系数 γ
3. **calculate_mixing_enthalpy** - 计算混合焓（过剩焓），基于Miedema模型
4. **calculate_gibbs_energy** - 计算摩尔Gibbs自由能
5. **calculate_chemical_potential** - 计算化学势 μ_i = μ°_i(T) + RT·ln(a_i)
6. **calculate_entropy** - 计算摩尔熵 S = (H - G) / T
7. **calculate_all_properties** - 一次性计算所有热力学性质（活度、活度系数、化学势、焓、Gibbs能、熵）

=== 活度相互作用系数（核心参数） ===

8. **get_interaction_coefficient** - 计算一阶活度相互作用系数 ε_i^j
   - 参数: solvent(溶剂), solute_i(溶质i), solute_j(溶质j), temperature(温度K)
   - Wagner模型核心: ln(γ_i) = ln(γ°_i) + Σ ε_i^j · x_j
   - 用于评估溶质间的相互影响

9. **get_second_order_interaction_coefficient** - 计算二阶活度相互作用系数 ρ
   - 支持: rho_ii(自相互作用), rho_jj(混合), rho_ij(交叉)
   - 用于Darken/Elliott高阶活度模型

10. **get_infinite_dilution_activity_coefficient** - 计算无限稀释活度系数 ln(γ°_i)
    - 基于Miedema模型的化学相互作用能

=== 相图与析出 ===

11. **calculate_liquidus_temperature** - 计算液相线温度（开始凝固温度）
12. **calculate_precipitation_temperature** - 计算析出温度
13. **calculate_melting_point_depression** - 计算溶质对溶剂的熔点降低

=== 辅助工具 ===

14. **get_element_properties** - 获取元素基本性质（熔点、原子半径、电负性等）
15. **plot_chart** - 绘制图表（折线图/散点图/柱状图），将计算结果可视化

使用指南：
- 用户可能使用中文或英文描述问题
- 成分可以用摩尔分数或质量百分比表示，需要正确解析
- 温度单位可能是K（开尔文）或°C（摄氏度），注意转换
- 如果用户没有指定参数，使用默认值
- 计算结果要清晰解释物理意义
- 遇到错误时，提供有用的调试建议
- 当用户问到"活度相互作用系数"、"ε"、"epsilon"时，调用 get_interaction_coefficient
- 当用户问到"无限稀释活度系数"、"γ°"时，调用 get_infinite_dilution_activity_coefficient
- 当用户想一次性了解合金的全部性质时，使用 calculate_all_properties

回答格式：
- 使用中文回答
- 先解释计算目标
- 调用工具获取结果
- 解释结果的物理意义
- 如有必要，提供进一步分析建议
"""


@dataclass
class ChatSession:
    """对话会话"""
    messages: List[Message] = field(default_factory=list)
    max_history: int = 50  # 最大历史消息数

    def add_message(self, role: str, content: str, tool_calls: List[Dict] = None,
                   tool_call_id: str = None):
        """添加消息"""
        msg = Message(
            role=role,
            content=content,
            tool_calls=tool_calls or [],
            tool_call_id=tool_call_id
        )
        self.messages.append(msg)

        # 限制历史长度，保留system消息
        if len(self.messages) > self.max_history:
            system_msgs = [m for m in self.messages if m.role == "system"]
            other_msgs = [m for m in self.messages if m.role != "system"]
            self.messages = system_msgs + other_msgs[-(self.max_history - len(system_msgs)):]

    def get_messages(self) -> List[Message]:
        """获取所有消息"""
        return self.messages.copy()

    def clear(self):
        """清空会话（保留system消息）"""
        self.messages = [m for m in self.messages if m.role == "system"]


class ChatAgent:
    """
    对话代理

    协调LLM后端与工具调用，实现自然语言交互式计算。

    使用示例:
    ```python
    agent = ChatAgent(provider="ollama", model="qwen2.5:7b")
    response = agent.chat("计算Al-5%Cu合金的液相线温度")
    print(response)
    ```
    """

    def __init__(
        self,
        provider: str = "ollama",
        api_key: str = None,
        model: str = None,
        system_prompt: str = None,
        max_tool_iterations: int = 5,
        on_tool_call: Callable[[str, Dict], None] = None,
        on_response: Callable[[str], None] = None
    ):
        """
        初始化对话代理

        参数:
        -----
        provider : str
            LLM提供商: 'openai', 'claude', 'gemini', 'deepseek', 'kimichat', 'ollama'
        api_key : str, optional
            API密钥（ollama不需要）
        model : str, optional
            模型名称
        system_prompt : str, optional
            系统提示词（默认使用内置提示词）
        max_tool_iterations : int
            单次对话最大工具调用次数
        on_tool_call : callable, optional
            工具调用回调 fn(tool_name, arguments)
        on_response : callable, optional
            响应回调 fn(content)
        """
        self.backend = create_backend(provider, api_key, model)
        self.tools = ThermodynamicTools()
        self.session = ChatSession()
        self.max_tool_iterations = max_tool_iterations
        self.on_tool_call = on_tool_call
        self.on_response = on_response

        # 初始化系统消息
        prompt = system_prompt or SYSTEM_PROMPT
        self.session.add_message("system", prompt)

    def get_available_providers(self) -> List[str]:
        """获取可用的LLM提供商列表"""
        return list(BACKEND_CONFIGS.keys())

    def switch_provider(self, provider: str, api_key: str = None, model: str = None):
        """切换LLM提供商"""
        self.backend = create_backend(provider, api_key, model)

    def get_available_models(self) -> List[str]:
        """获取当前后端的可用模型列表"""
        return self.backend.get_available_models()

    def chat(self, user_message: str) -> str:
        """
        发送消息并获取回复

        参数:
        -----
        user_message : str
            用户消息

        返回:
        -----
        str : 助手回复
        """
        # 添加用户消息
        self.session.add_message("user", user_message)

        # 获取工具定义
        tool_defs = self.tools.get_tool_definitions()

        # 迭代处理工具调用
        for iteration in range(self.max_tool_iterations):
            try:
                response = self.backend.chat(
                    messages=self.session.get_messages(),
                    tools=tool_defs
                )
            except Exception as e:
                error_msg = f"LLM调用失败: {str(e)}"
                self.session.add_message("assistant", error_msg)
                return error_msg

            # 如果有工具调用
            if response.tool_calls:
                # 添加助手消息（包含工具调用）
                self.session.add_message(
                    "assistant",
                    response.content,
                    tool_calls=response.tool_calls
                )

                # 执行每个工具调用
                for tool_call in response.tool_calls:
                    tool_name = tool_call["function"]["name"]
                    try:
                        arguments = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}

                    # 回调通知
                    if self.on_tool_call:
                        self.on_tool_call(tool_name, arguments)

                    # 执行工具
                    result = self.tools.execute_tool(tool_name, arguments)

                    # 添加工具结果消息
                    self.session.add_message(
                        "tool",
                        result,
                        tool_call_id=tool_call["id"]
                    )
            else:
                # 没有工具调用，返回最终回复
                self.session.add_message("assistant", response.content)

                if self.on_response:
                    self.on_response(response.content)

                return response.content

        # 达到最大迭代次数
        final_msg = "已达到最大工具调用次数限制。"
        self.session.add_message("assistant", final_msg)
        return final_msg

    def reset(self):
        """重置会话"""
        self.session.clear()

    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史（不含system消息）"""
        return [
            {"role": m.role, "content": m.content}
            for m in self.session.messages
            if m.role != "system"
        ]


class StreamingChatAgent(ChatAgent):
    """
    流式对话代理

    支持流式输出，适用于GUI界面实时显示。
    """

    def __init__(self, *args, on_stream: Callable[[str], None] = None, **kwargs):
        """
        参数:
        -----
        on_stream : callable
            流式输出回调 fn(chunk)，接收每个文本片段
        """
        super().__init__(*args, **kwargs)
        self.on_stream = on_stream

    # 注意：流式输出需要后端支持，这里预留接口
    # 实际实现需要根据不同后端的流式API进行适配


# ============= 便捷函数 =============

def quick_calculate(query: str, provider: str = "ollama", model: str = None) -> str:
    """
    快速计算

    一次性对话，不保留历史。

    示例:
    ```python
    result = quick_calculate("计算Al-5%Cu的液相线温度")
    print(result)
    ```
    """
    agent = ChatAgent(provider=provider, model=model)
    return agent.chat(query)


# ============= 命令行交互 =============

def interactive_cli(provider: str = "ollama", model: str = None):
    """命令行交互模式"""
    print("=" * 60)
    print("AlloyThermoCal Pro - 对话式热力学计算")
    print("=" * 60)
    print(f"后端: {provider}, 模型: {model or '默认'}")
    print("输入 'quit' 或 'exit' 退出")
    print("输入 'reset' 重置对话")
    print("=" * 60)
    print()

    def on_tool_call(name, args):
        print(f"\n[调用工具: {name}]")
        print(f"参数: {json.dumps(args, ensure_ascii=False)}")

    agent = ChatAgent(
        provider=provider,
        model=model,
        on_tool_call=on_tool_call
    )

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("再见!")
            break

        if user_input.lower() == "reset":
            agent.reset()
            print("对话已重置。")
            continue

        print("\n助手: ", end="", flush=True)
        response = agent.chat(user_input)
        print(response)


# ============= 测试代码 =============

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="对话式热力学计算")
    parser.add_argument("--provider", "-p", default="ollama",
                       choices=list(BACKEND_CONFIGS.keys()),
                       help="LLM提供商")
    parser.add_argument("--model", "-m", default=None, help="模型名称")
    parser.add_argument("--query", "-q", default=None, help="单次查询（非交互模式）")

    args = parser.parse_args()

    if args.query:
        # 单次查询模式
        result = quick_calculate(args.query, args.provider, args.model)
        print(result)
    else:
        # 交互模式
        interactive_cli(args.provider, args.model)
