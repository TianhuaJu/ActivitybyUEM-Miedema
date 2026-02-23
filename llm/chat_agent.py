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
from llm.memory import MemoryStore
from llm.knowledge import KnowledgeStore
from llm.rag_engine import RAGEngine
from llm.skill_registry import SkillRegistry


# ============= 系统提示词（分层设计） =============

# 核心提示词：紧凑、明确，适用于所有模型（包括小模型如qwen3:8b）
SYSTEM_PROMPT_CORE = """你是合金热力学计算软件的AI助手。你的唯一职责是：接收用户的计算需求，调用工具执行计算，返回结果。

核心规则（必须严格遵守）：
1. 收到计算请求后，必须立即调用对应的工具函数。绝对不要用文字解释怎么算、用什么公式、分几步——直接调用工具！
2. 用户没有指定的参数一律使用默认值（外推模型=UEM1，活度模型=Wagner，相态=liquid）
3. 温度如果给的是°C，自动加273.15转换为K
4. 成分如果给的是百分比，自动除以100转换为摩尔分数
5. 回答简洁，重点展示计算结果数值
6. 每个工具只调用一次，拿到结果后直接回复用户
7. 必须使用中文回答

成分解析：
- "Fe-5%Cu合金" → {"Fe": 0.95, "Cu": 0.05}
- "Al-4%Cu-1%Mg" → {"Al": 0.95, "Cu": 0.04, "Mg": 0.01}
- 百分比默认为摩尔分数，余量补给基体元素

结果输出格式：
拿到工具返回结果后，用自然语言总结核心数值，不要罗列JSON字段。
- 温度结果同时给出K和°C
- 数值保留4位有效数字
- 上下标用花括号：ε_{Si}^{C}、γ_{Fe}

你拥有以下计算工具：

【活度相互作用系数】
- get_interaction_coefficient → 一阶活度相互作用系数 ε (参数: solvent, solute_i, solute_j, temperature)
- get_second_order_interaction_coefficient → 二阶系数 ρ (参数: solvent, solute_i, solute_j, temperature, coefficient_type)
- get_infinite_dilution_activity_coefficient → 无限稀释活度系数 ln(γ°) (参数: solvent, solute, temperature)

【热力学性质】（支持 activity_model 参数: Wagner/Darken/Elliott）
- calculate_activity → 活度 (参数: composition, component, temperature)
- calculate_activity_coefficient → 活度系数 (参数: composition, component, temperature)
- calculate_chemical_potential → 化学势 (参数: composition, component, temperature)
- calculate_mixing_enthalpy → 混合焓 (参数: composition, temperature)
- calculate_gibbs_energy → Gibbs自由能 (参数: composition, temperature)
- calculate_entropy → 摩尔熵 (参数: composition, temperature)
- calculate_all_properties → 全部性质 (参数: composition, temperature)

【相图与温度】
- calculate_liquidus_temperature → 液相线温度 (参数: composition)
- calculate_precipitation_temperature → 析出温度 (参数: composition, solute)
- calculate_melting_point_depression → 熔点降低 (参数: solvent, solute, solute_content_percent)

【溶解度积与析出】
- calculate_solubility_product → 溶解度积Ksp (参数: compound, temperature, phase, method)
- calculate_precipitation_temperature_sp → 析出温度(溶解度积法) (参数: compound, metal_content, nonmetal_content, phase)
- calculate_equilibrium_solubility → 平衡溶解度 (参数: compound, temperature, fixed_element, fixed_content, phase)
- get_precipitation_sequence → 析出顺序 (参数: composition, phase)
注意: compound参数可以是化合物名称(如"TiN")或反应方程式(如"TiN=[Ti]+[N]")。metal_content和nonmetal_content为质量百分数(wt%)。phase默认AUSTENITE。

【辅助】
- get_element_properties → 元素性质 (参数: element)
- get_contribution_coefficients → 贡献系数 (参数: solvent, solute_i, solute_j)
- screen_elements_liquidus_effect → 元素筛选 (参数: solvent, candidate_elements, addition_percent)
- plot_chart → 绘图 (参数: title, x_label, y_label, data_series)

关键词→工具映射：
- "活度"→ calculate_activity, "活度系数"→ calculate_activity_coefficient
- "液相线"→ calculate_liquidus_temperature, "析出温度"→ calculate_precipitation_temperature
- "混合焓"→ calculate_mixing_enthalpy, "自由能"→ calculate_gibbs_energy
- "相互作用系数"/"ε" → get_interaction_coefficient
- "二阶"/"ρ" → get_second_order_interaction_coefficient
- "溶解度积"/"Ksp" → calculate_solubility_product
- "平衡溶解度"/"平衡含量" → calculate_equilibrium_solubility
- "析出顺序"/"析出序列" → get_precipitation_sequence

活度模型：Wagner(默认,一阶) / Darken(二阶) / Elliott(二阶交叉)
外推模型：UEM1(默认) / UEM2 / Muggianu / Toop_Muggianu / Toop_Kohler

用中文回答，直接给出计算结果。"""


# 扩展提示词：高级功能描述，仅附加给大模型
SYSTEM_PROMPT_EXTENDED = """

========== 记忆功能 ==========
- save_memory → 保存信息到长期记忆 (参数: content, category)
- recall_memories → 回忆已保存的信息 (参数: keyword)
- delete_memory → 删除记忆 (参数: content)
当用户指定偏好（如"以后默认用Elliott模型"）时，主动调用save_memory保存。

========== 知识学习 ==========
- learn_knowledge → 学习领域知识 (参数: topic, content, category, confidence, tags)
- search_knowledge → 搜索知识 (参数: keyword, category)
- optimize_knowledge → 优化知识库，自动检测相似条目并合并去重 (参数: similarity_threshold)
对话中出现有价值的热力学知识时，主动调用learn_knowledge保存。
当用户要求整理知识库或条目较多时，调用optimize_knowledge进行去重和优化。

========== 实验数据更新 ==========
- update_experimental_value → 保存实验数据 (参数: data_type, solvent, solute_i, solute_j, value, value_type, temperature, reference)
- list_user_data → 列出已保存数据 (参数: solvent, data_type)
当用户告诉你实验测量值时，主动调用update_experimental_value保存。

========== 动态技能 ==========
- create_custom_tool → 创建自定义计算工具
- list_custom_tools / remove_custom_tool → 管理自定义工具
- list_skill_libraries / load_skill_library / unload_skill_library → 技能库管理
技能代码中可使用 call_tool(tool_name, **kwargs) 调用内置计算工具。

========== 详细输出格式 ==========
正确示例：
- 液相线温度：「Al-0.2%Fe-0.5%Si合金的液相线温度为 927.3 K（654.2°C），相比纯铝（933.5K）降低了 6.2 K。」
- 活度系数：「在1873K下，Fe-5%C合金中C的活度系数 γ = 0.901（ln γ = -0.104），活度 a = 0.045。」

错误示例（绝对不要这样做）：
- status: success
- component: C
这种逐行罗列JSON字段的方式对用户没有帮助。

========== 成分解析详细规则 ==========
- "铁碳合金，碳含量0.8%" → {"Fe": 0.992, "C": 0.008}
- "铜锌合金，锌30%" → {"Cu": 0.70, "Zn": 0.30}
- "Fe中加入少量Ti和C" → 推测典型含量如 {"Fe": 0.98, "Ti": 0.01, "C": 0.01}
- 百分比默认为摩尔分数，用户说"wt%"时为质量百分比
- 描述模糊时先向用户确认

========== 活度模型详细说明 ==========
1. Wagner（一阶，默认）: ln(γ_i) = ln(γ°_i) + Σ ε_i^j × x_j
2. Darken（二阶）: 在Wagner基础上加入二阶修正项
3. Elliott（二阶交叉）: 使用交叉相互作用系数ρ
模型选择：稀溶液→Wagner，高浓度→Elliott，用户说"对比三种模型"→各算一次

========== 贡献系数说明 ==========
贡献系数是从二元子体系外推到三元体系的权重因子。
用 get_contribution_coefficients 查询，如：solvent="Fe", solute_i="C", solute_j="Si"

========== 合金设计工作流 ==========
用 screen_elements_liquidus_effect 一次筛选多种元素的液相线影响，用表格展示排名结果。"""


# 完整提示词：核心+扩展（用于大模型）
SYSTEM_PROMPT = SYSTEM_PROMPT_CORE + SYSTEM_PROMPT_EXTENDED

# 核心工具集（适用于所有模型，包括小模型）
_CORE_TOOLS = {
    "calculate_liquidus_temperature",
    "calculate_precipitation_temperature",
    "calculate_activity",
    "calculate_activity_coefficient",
    "calculate_mixing_enthalpy",
    "calculate_gibbs_energy",
    "calculate_chemical_potential",
    "calculate_entropy",
    "calculate_all_properties",
    "calculate_melting_point_depression",
    "get_interaction_coefficient",
    "get_second_order_interaction_coefficient",
    "get_infinite_dilution_activity_coefficient",
    "get_contribution_coefficients",
    "get_element_properties",
    "screen_elements_liquidus_effect",
    "plot_chart",
    "calculate_solubility_product",
    "calculate_precipitation_temperature_sp",
    "calculate_equilibrium_solubility",
    "get_precipitation_sequence",
}

# 判断模型是否为小模型（需要精简工具和提示词）
def _is_small_model(model_name: str) -> bool:
    """判断是否为小模型（参数量 ≤ 14B 的本地模型）"""
    if not model_name:
        return False
    name = model_name.lower()
    # 这些都是大模型/API模型，不需要精简
    for prefix in ("gpt-", "claude-", "gemini-", "deepseek-", "moonshot-"):
        if name.startswith(prefix):
            return False
    # Ollama模型：检查参数量标签
    # 格式如 "qwen3:8b", "llama3.1:70b"
    import re
    m = re.search(r':(\d+)b', name)
    if m:
        param_b = int(m.group(1))
        return param_b <= 14
    # 无法判断参数量的Ollama模型，保守地认为是小模型
    return True


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
        base_url: str = None,
        system_prompt: str = None,
        max_tool_iterations: int = 10,
        on_tool_call: Callable[[str, Dict], None] = None,
        on_tool_result: Callable[[str, str], None] = None,
        on_response: Callable[[str], None] = None,
        restore_history: bool = True
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
        base_url : str, optional
            自定义API地址，用于局域网Ollama等场景
        system_prompt : str, optional
            系统提示词（默认使用内置提示词）
        max_tool_iterations : int
            单次对话最大工具调用次数
        on_tool_call : callable, optional
            工具调用回调 fn(tool_name, arguments)
        on_tool_result : callable, optional
            工具结果回调 fn(tool_name, result_json)
        on_response : callable, optional
            响应回调 fn(content)
        restore_history : bool
            是否恢复上次对话历史到当前会话（默认True）
        """
        self.backend = create_backend(provider, api_key, model, base_url=base_url)
        self.provider = provider
        self.model_name = model or ""
        self._use_compact_mode = _is_small_model(self.model_name)
        self.memory = MemoryStore()
        self.knowledge = KnowledgeStore()
        self.skill_registry = SkillRegistry()
        self.rag_engine = RAGEngine(self.knowledge)

        # 初始化插件注册表（自动发现扩展插件）
        self.plugin_registry = None
        try:
            from extensions.registry import PluginRegistry
            self.plugin_registry = PluginRegistry()
            self.plugin_registry.discover()
        except Exception:
            pass  # 插件系统加载失败不影响核心功能

        self.tools = ThermodynamicTools(
            memory_store=self.memory, knowledge_store=self.knowledge,
            skill_registry=self.skill_registry,
            plugin_registry=self.plugin_registry
        )
        # 绑定工具桥接：让动态技能可以调用内置计算工具
        self.skill_registry.bind_tools(self.tools)
        # 自动发现并加载技能库（auto_load=true 的库）
        try:
            self.skill_registry.discover_libraries()
            self.skill_registry.auto_load_libraries()
            self.skill_registry.bind_tools(self.tools)
        except Exception:
            pass  # 技能库加载失败不影响核心功能
        self.session = ChatSession()
        self.max_tool_iterations = max_tool_iterations
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_response = on_response

        # 构建系统消息：根据模型能力选择提示词
        if system_prompt:
            prompt = system_prompt
        elif self._use_compact_mode:
            # 小模型：仅使用核心提示词，避免过长的上下文干扰工具调用
            prompt = SYSTEM_PROMPT_CORE
        else:
            # 大模型：完整提示词（核心+扩展）
            prompt = SYSTEM_PROMPT

        # 大模型附加额外上下文（记忆、知识库、技能、插件等）
        if not self._use_compact_mode:
            memory_context = self.memory.format_for_prompt()
            knowledge_context = self.knowledge.format_knowledge_for_prompt()
            user_data_context = self.knowledge.format_user_data_for_prompt()
            history_context = self.memory.get_recent_summary(max_sessions=3)
            if memory_context:
                prompt += "\n" + memory_context
            if knowledge_context:
                prompt += "\n" + knowledge_context
            if user_data_context:
                prompt += "\n" + user_data_context
            # 已加载的技能库
            libraries = self.skill_registry.list_libraries()
            loaded_libs = [lb for lb in libraries if lb.get("loaded")]
            if loaded_libs:
                lib_lines = ["\n========== 已加载的技能库 =========="]
                for lb in loaded_libs:
                    lib_lines.append(
                        f"  [{lb['display_name']}] ({lb['library_name']}) "
                        f"- {lb['loaded_skills']}个技能"
                    )
                prompt += "\n".join(lib_lines)
            # 已注册的自定义技能
            skill_count = self.skill_registry.get_skill_count()
            if skill_count > 0:
                skills = self.skill_registry.list_skills()
                skill_lines = [f"\n========== 已注册的技能（{skill_count}个） =========="]
                for s in skills:
                    if s["enabled"]:
                        skill_lines.append(f"  - skill_{s['name']}: {s['description']}")
                prompt += "\n".join(skill_lines)
            # 扩展插件工具描述
            if self.plugin_registry:
                try:
                    plugin_prompt = self.plugin_registry.format_tools_for_prompt()
                    if plugin_prompt:
                        prompt += plugin_prompt
                except Exception:
                    pass
            if history_context:
                prompt += "\n" + history_context
        self.session.add_message("system", prompt)

        # 恢复上一次对话历史
        self._restored_messages: List[Dict[str, str]] = []
        if restore_history:
            self._restore_last_session()

    def get_available_providers(self) -> List[str]:
        """获取可用的LLM提供商列表"""
        return list(BACKEND_CONFIGS.keys())

    def switch_provider(self, provider: str, api_key: str = None, model: str = None):
        """切换LLM提供商"""
        self.backend = create_backend(provider, api_key, model)

    def get_available_models(self) -> List[str]:
        """获取当前后端的可用模型列表"""
        return self.backend.get_available_models()

    def _restore_last_session(self):
        """恢复上一次对话的历史消息到当前会话（仅user和assistant消息）"""
        previous = self.memory.load_latest_session()
        if not previous:
            return
        restored = []
        for msg in previous:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content.strip():
                self.session.add_message(role, content)
                restored.append({"role": role, "content": content})
        self._restored_messages = restored

    def get_restored_messages(self) -> List[Dict[str, str]]:
        """获取本次恢复的历史消息列表"""
        return self._restored_messages

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

        # RAG 检索（仅大模型启用，避免小模型上下文过长）
        rag_context = ""
        if self.rag_engine and not self._use_compact_mode:
            try:
                k_ctx = self.rag_engine.retrieve(user_message, top_k=5)
                d_ctx = self.rag_engine.retrieve_user_data(user_message)
                parts = [p for p in (k_ctx, d_ctx) if p]
                if parts:
                    rag_context = "\n".join(parts)
            except Exception:
                pass

        # 获取工具定义：小模型仅核心工具，大模型全部工具
        tool_defs = self.tools.get_tool_definitions()
        if not self._use_compact_mode and self.skill_registry:
            try:
                tool_defs.extend(self.skill_registry.get_tool_definitions())
            except Exception:
                pass
        if self._use_compact_mode:
            tool_defs = [t for t in tool_defs if t.name in _CORE_TOOLS]

        # 迭代处理工具调用
        last_tool_results = []  # 记录最近一轮工具结果，用于空回复兜底

        for iteration in range(self.max_tool_iterations):
            # 构建消息列表
            messages = self.session.get_messages()

            # 首轮注入RAG上下文到system消息
            if rag_context and iteration == 0 and messages:
                messages = list(messages)
                if messages[0].role == "system":
                    augmented = (messages[0].content
                                 + "\n\n" + rag_context)
                    messages[0] = Message(role="system", content=augmented)

            try:
                response = self.backend.chat(
                    messages=messages,
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
                last_tool_results = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call["function"]["name"]
                    try:
                        arguments = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}

                    # 回调通知
                    if self.on_tool_call:
                        self.on_tool_call(tool_name, arguments)

                    # 执行工具：区分动态技能和内置工具
                    try:
                        if tool_name.startswith("skill_"):
                            skill_name = tool_name[6:]
                            skill_result = self.skill_registry.execute_skill(
                                skill_name, arguments
                            )
                            result = json.dumps(
                                skill_result, ensure_ascii=False, indent=2
                            )
                        else:
                            result = self.tools.execute_tool(tool_name, arguments)
                    except Exception as e:
                        result = json.dumps(
                            {"status": "error",
                             "message": f"工具执行异常: {e}"},
                            ensure_ascii=False
                        )
                    last_tool_results.append((tool_name, result))

                    # 工具结果回调
                    if self.on_tool_result:
                        self.on_tool_result(tool_name, result)

                    # 添加工具结果消息
                    self.session.add_message(
                        "tool",
                        result,
                        tool_call_id=tool_call["id"]
                    )
            else:
                # 没有工具调用
                final_content = response.content

                # 小模型重试：如果首轮就返回文字而没调用工具，追加提醒再试一次
                if (self._use_compact_mode and iteration == 0
                        and not last_tool_results and final_content.strip()):
                    # 将模型的文字回复丢弃，追加一条强制提醒
                    self.session.add_message("assistant", final_content)
                    self.session.add_message(
                        "user",
                        "请直接调用工具函数来计算，不要用文字解释。请现在调用工具。"
                    )
                    continue

                # 如果LLM回复为空但之前有工具结果，用工具结果兜底
                if not final_content.strip() and last_tool_results:
                    final_content = self._format_tool_results_fallback(last_tool_results)

                self.session.add_message("assistant", final_content)

                if self.on_response:
                    self.on_response(final_content)

                return final_content

        # 达到最大迭代次数，如果有工具结果则展示
        if last_tool_results:
            final_msg = self._format_tool_results_fallback(last_tool_results)
        else:
            final_msg = "已达到最大工具调用次数限制。"
        self.session.add_message("assistant", final_msg)
        return final_msg

    # 工具名→中文名 映射
    _TOOL_NAMES_ZH = {
        "calculate_liquidus_temperature": "液相线温度",
        "calculate_precipitation_temperature": "析出温度",
        "calculate_activity": "活度",
        "calculate_activity_coefficient": "活度系数",
        "calculate_mixing_enthalpy": "混合焓",
        "calculate_gibbs_energy": "Gibbs自由能",
        "calculate_melting_point_depression": "熔点降低",
        "calculate_chemical_potential": "化学势",
        "calculate_entropy": "摩尔熵",
        "calculate_all_properties": "热力学性质",
        "get_interaction_coefficient": "活度相互作用系数",
        "get_second_order_interaction_coefficient": "二阶相互作用系数",
        "get_contribution_coefficients": "贡献系数",
        "get_infinite_dilution_activity_coefficient": "无限稀释活度系数",
        "get_element_properties": "元素性质",
        "screen_elements_liquidus_effect": "元素筛选",
        "learn_knowledge": "知识学习",
        "search_knowledge": "知识检索",
        "optimize_knowledge": "知识库优化",
        "update_experimental_value": "实验数据更新",
        "list_user_data": "用户数据查询",
        "create_custom_tool": "创建自定义工具",
        "list_custom_tools": "查看自定义工具",
        "remove_custom_tool": "删除自定义工具",
        "list_skill_libraries": "查看技能库",
        "load_skill_library": "加载技能库",
        "unload_skill_library": "卸载技能库",
        "store_dft_compound_energy": "存储DFT化合物能量",
        "calculate_liquidus_dft_calibrated": "DFT校准液相线温度",
        "calculate_precipitation_dft_calibrated": "DFT校准析出温度",
        "compare_mixing_enthalpy": "混合焓对比",
        "get_dft_data_summary": "DFT数据摘要",
        "import_dft_result": "导入DFT结果",
        "calculate_solubility_product": "溶解度积",
        "calculate_precipitation_temperature_sp": "析出温度(溶解度积)",
        "calculate_equilibrium_solubility": "平衡溶解度",
        "get_precipitation_sequence": "析出顺序",
    }

    # 需要隐藏的内部字段（不展示给用户）
    _SKIP_KEYS = {
        "status", "message", "iterations", "type", "chart_type",
        "phase", "unit", "description", "meaning", "coefficient_type",
        "label", "missing_data",
    }

    # 字段名→中文标签映射（通用兜底时使用）
    _FIELD_LABELS = {
        "temperature": ("温度", "K"),
        "liquidus_temperature": ("液相线温度", "K"),
        "liquidus_temperature_celsius": ("液相线温度", "°C"),
        "melting_point_depression": ("熔点降低", "K"),
        "pure_melting_point": ("纯溶剂熔点", "K"),
        "enthalpy_of_fusion": ("熔化焓", "J/mol"),
        "solvent_activity": ("溶剂活度", ""),
        "interaction_correction": ("相互作用修正", ""),
        "molar_enthalpy": ("混合焓", "J/mol"),
        "gibbs_energy": ("Gibbs自由能", "J/mol"),
        "entropy": ("熵", "J/(mol·K)"),
        "chemical_potential": ("化学势", "J/mol"),
        "gamma": ("活度系数 γ", ""),
        "ln_gamma": ("ln γ", ""),
        "activity": ("活度 a", ""),
        "epsilon_i_j": ("ε", ""),
        "ln_gamma_0": ("ln γ°", ""),
        "gamma_0": ("γ°", ""),
        "rho": ("ρ", ""),
        "depression_per_percent": ("每百分比熔点降低", "K/%"),
        "solute_content_percent": ("溶质含量", "%"),
        "pure_melting_point_K": ("纯溶剂熔点", "K"),
        "liquidus_temperature_K": ("液相线温度", "K"),
        "liquidus_temperature_C": ("液相线温度", "°C"),
        "melting_point_depression_K": ("熔点降低", "K"),
        "precipitation_temperature_K": ("析出温度", "K"),
        "molar_enthalpy_J_per_mol": ("混合焓", "J/mol"),
        "gibbs_energy_J_per_mol": ("Gibbs自由能", "J/mol"),
        "entropy_J_per_mol_K": ("熵", "J/(mol·K)"),
        "chemical_potential_J_per_mol": ("化学势", "J/mol"),
        "log_Ksp": ("log(Ksp)", ""),
        "Ksp": ("溶解度积 Ksp", ""),
        "expression": ("溶解度积表达式", ""),
        "metal_content_wt_pct": ("金属元素含量", "wt%"),
        "nonmetal_content_wt_pct": ("非金属元素含量", "wt%"),
        "equilibrium_content_wt_pct": ("平衡含量", "wt%"),
        "equilibrium_content_ppm": ("平衡含量", "ppm"),
        "precipitation_temperature_C": ("析出温度", "°C"),
        "delta_G_dissolution": ("溶解Gibbs能变", "J/mol"),
    }

    @classmethod
    def _format_tool_results_fallback(cls, tool_results: list) -> str:
        """当LLM回复为空时，将工具结果格式化为人类可读的自然语言"""

        # 按工具名分组：同一个工具被多次调用时合并为表格
        from collections import OrderedDict
        grouped = OrderedDict()
        errors = []
        for tool_name, result_json in tool_results:
            try:
                data = json.loads(result_json) if isinstance(result_json, str) else result_json
            except (json.JSONDecodeError, TypeError):
                data = {"result": result_json}

            if isinstance(data, dict) and data.get("status") == "error":
                errors.append(f"计算失败: {data.get('message', '未知错误')}")
                continue

            grouped.setdefault(tool_name, []).append(data)

        parts = list(errors)
        for tool_name, results_list in grouped.items():
            tool_zh = cls._TOOL_NAMES_ZH.get(tool_name, tool_name)
            if len(results_list) == 1:
                formatted = cls._format_single_result(tool_name, tool_zh, results_list[0])
            else:
                formatted = cls._format_batch_results(tool_name, tool_zh, results_list)
            if formatted:
                parts.append(formatted)

        return "\n\n".join(parts) if parts else "计算完成，但未返回结果。"

    @classmethod
    def _format_single_result(cls, tool_name: str, tool_zh: str, data: dict) -> str:
        """将单个工具结果格式化为自然语言"""
        if not isinstance(data, dict):
            return str(data)

        # ---------- 液相线温度 ----------
        if tool_name == "calculate_liquidus_temperature":
            t_k = data.get("liquidus_temperature")
            t_c = data.get("liquidus_temperature_celsius")
            depression = data.get("melting_point_depression")
            if t_k is not None:
                if t_c is None:
                    t_c = t_k - 273.15
                text = f"**液相线温度**: {t_k:.1f} K ({t_c:.1f}°C)"
                if depression is not None:
                    text += f"，熔点降低 {depression:.1f} K"
                return text

        # ---------- 活度 ----------
        if tool_name == "calculate_activity":
            comp = data.get("component", "?")
            temp = data.get("temperature", "?")
            activity = data.get("activity")
            if activity is not None:
                return f"**{comp}** 在 {temp}K 下的活度 a = {activity:.4g}"

        # ---------- 活度系数 ----------
        if tool_name == "calculate_activity_coefficient":
            comp = data.get("component", "?")
            temp = data.get("temperature", "?")
            gamma = data.get("gamma")
            ln_gamma = data.get("ln_gamma")
            parts = [f"**{comp}** 在 {temp}K 下"]
            if gamma is not None:
                parts.append(f"活度系数 γ = {gamma:.4g}")
            if ln_gamma is not None:
                parts.append(f"(ln γ = {ln_gamma:.4g})")
            return " ".join(parts)

        # ---------- 一阶相互作用系数 ----------
        if tool_name == "get_interaction_coefficient":
            eps = data.get("epsilon_i_j")
            solute_i = data.get("solute_i", "?")
            solute_j = data.get("solute_j", "?")
            solvent = data.get("solvent", "?")
            temp = data.get("temperature", "?")
            if eps is not None:
                return f"在 {temp}K 的液态{solvent}中，**ε_{{{solute_i}}}^{{{solute_j}}} = {eps:.4g}**"

        # ---------- 二阶相互作用系数 ----------
        if tool_name == "get_second_order_interaction_coefficient":
            rho = data.get("rho")
            solute_i = data.get("solute_i", "?")
            solute_j = data.get("solute_j", "?")
            solvent = data.get("solvent", "?")
            temp = data.get("temperature", "?")
            if rho is not None:
                return f"在 {temp}K 的液态{solvent}中，**ρ_{{{solute_i}}}^{{{solute_j}}} = {rho:.4g}**"

        # ---------- 贡献系数 ----------
        if tool_name == "get_contribution_coefficients":
            solvent = data.get("solvent", "?")
            solute_i = data.get("solute_i", "?")
            solute_j = data.get("solute_j", "?")
            temp = data.get("temperature", "?")
            model = data.get("extrapolation_model", "UEM1")
            coeffs = data.get("coefficients", {})
            if coeffs:
                k, i, j = solvent, solute_i, solute_j
                lines = [f"**{k}-{i}-{j}体系贡献系数**（{temp}K，{model}模型）:\n"]
                lines.append(f"| 二元子体系 | 贡献系数 | 值 |")
                lines.append(f"|-----------|---------|-----|")
                for label, val in coeffs.items():
                    lines.append(f"| {label} | | {val:.4g} |")
                return "\n".join(lines)

        # ---------- 无限稀释活度系数 ----------
        if tool_name == "get_infinite_dilution_activity_coefficient":
            ln_gamma = data.get("ln_gamma_0")
            gamma_0 = data.get("gamma_0")
            solute = data.get("solute", "?")
            solvent = data.get("solvent", "?")
            temp = data.get("temperature", "?")
            if ln_gamma is not None:
                if gamma_0 is None:
                    import math
                    gamma_0 = math.exp(ln_gamma)
                return f"在 {temp}K 的{solvent}中，{solute}的**无限稀释活度系数 ln(γ°) = {ln_gamma:.4g}**（γ° = {gamma_0:.4g}）"

        # ---------- 混合焓 ----------
        if tool_name == "calculate_mixing_enthalpy":
            val = data.get("molar_enthalpy")
            temp = data.get("temperature", "?")
            if val is not None:
                return f"**混合焓**: {val:.4g} J/mol（{temp}K）"

        # ---------- Gibbs自由能 ----------
        if tool_name == "calculate_gibbs_energy":
            val = data.get("gibbs_energy")
            temp = data.get("temperature", "?")
            if val is not None:
                return f"**Gibbs自由能**: {val:.4g} J/mol（{temp}K）"

        # ---------- 化学势 ----------
        if tool_name == "calculate_chemical_potential":
            mu = data.get("chemical_potential")
            comp = data.get("component", "?")
            temp = data.get("temperature", "?")
            if mu is not None:
                return f"**{comp}** 在 {temp}K 下的化学势 μ = {mu:.4g} J/mol"

        # ---------- 熔点降低 ----------
        if tool_name == "calculate_melting_point_depression":
            t_liq = data.get("liquidus_temperature_K")
            t_liq_c = data.get("liquidus_temperature_C")
            depression = data.get("melting_point_depression_K")
            solute = data.get("solute", "")
            pct = data.get("solute_content_percent", "")
            text_parts = []
            if depression is not None:
                text_parts.append(f"**熔点降低**: {depression:.2f} K")
            if t_liq is not None:
                c = t_liq_c if t_liq_c is not None else t_liq - 273.15
                text_parts.append(f"液相线温度 {t_liq:.1f} K ({c:.1f}°C)")
            return "，".join(text_parts) if text_parts else ""

        # ---------- 全部性质 ----------
        if tool_name == "calculate_all_properties":
            return cls._format_all_properties(data)

        # ---------- 元素筛选 ----------
        if tool_name == "screen_elements_liquidus_effect":
            return cls._format_screening_result(data)

        # ---------- 溶解度积 ----------
        if tool_name == "calculate_solubility_product":
            compound = data.get("compound", "?")
            temp = data.get("temperature", "?")
            temp_c = data.get("temperature_celsius", "?")
            phase = data.get("phase", "?")
            log_ksp = data.get("log_Ksp")
            expr = data.get("expression", "")
            ref = data.get("reference", "")
            if log_ksp is not None:
                text = f"**{compound}** 在 {temp}K ({temp_c}°C) {phase} 中的溶解度积:\n"
                text += f"  log(Ksp) = **{log_ksp:.4g}**"
                ksp = data.get("Ksp")
                if ksp is not None:
                    text += f"，Ksp = {ksp:.4g}"
                if expr:
                    text += f"\n  表达式: {expr}"
                if ref:
                    text += f"\n  参考文献: {ref}"
                # 热力学对比
                thermo_log = data.get("thermo_log_Ksp")
                if thermo_log is not None:
                    text += f"\n  热力学法 log(Ksp) = {thermo_log:.4g}"
                return text

        # ---------- 析出温度(溶解度积) ----------
        if tool_name == "calculate_precipitation_temperature_sp":
            compound = data.get("compound", "?")
            t_k = data.get("precipitation_temperature_K")
            t_c = data.get("precipitation_temperature_C")
            metal = data.get("metal", "?")
            nonmetal = data.get("nonmetal", "?")
            m_wt = data.get("metal_content_wt_pct", "?")
            nm_wt = data.get("nonmetal_content_wt_pct", "?")
            if t_k is not None:
                text = f"**{compound}** 的析出温度: **{t_k:.1f} K ({t_c:.1f}°C)**\n"
                text += f"  [{metal}] = {m_wt} wt%, [{nonmetal}] = {nm_wt} wt%"
                expr = data.get("expression", "")
                if expr:
                    text += f"\n  表达式: {expr}"
                return text

        # ---------- 平衡溶解度 ----------
        if tool_name == "calculate_equilibrium_solubility":
            compound = data.get("compound", "?")
            temp = data.get("temperature", "?")
            temp_c = data.get("temperature_celsius", "?")
            fixed_el = data.get("fixed_element", "?")
            fixed_wt = data.get("fixed_content_wt_pct", "?")
            eq_el = data.get("equilibrium_element", "?")
            eq_wt = data.get("equilibrium_content_wt_pct")
            eq_ppm = data.get("equilibrium_content_ppm")
            if eq_wt is not None:
                text = f"在 {temp}K ({temp_c}°C) 下，[{fixed_el}] = {fixed_wt} wt% 时，"
                text += f"**{compound}** 中 **[{eq_el}]** 的平衡含量 = **{eq_wt:.4g} wt%**"
                if eq_ppm is not None:
                    text += f" ({eq_ppm:.1f} ppm)"
                return text

        # ---------- 析出顺序 ----------
        if tool_name == "get_precipitation_sequence":
            sequence = data.get("sequence", [])
            if sequence:
                lines = ["**析出顺序**（从高温到低温）:\n"]
                lines.append("| 序号 | 化合物 | 析出温度 (K) | 析出温度 (°C) |")
                lines.append("|------|--------|-------------|--------------|")
                for i, item in enumerate(sequence, 1):
                    c = item.get("compound", "?")
                    tk = item.get("precipitation_temperature_K", 0)
                    tc = item.get("precipitation_temperature_C", tk - 273.15)
                    lines.append(f"| {i} | {c} | {tk:.1f} | {tc:.1f} |")
                return "\n".join(lines)

        # ---------- 通用兜底：用中文标签替代英文字段名 ----------
        lines = [f"**{tool_zh}**:"]
        for key, value in data.items():
            if key in cls._SKIP_KEYS:
                continue
            if key == "solvent":
                lines.append(f"  溶剂: {value}")
                continue
            label_info = cls._FIELD_LABELS.get(key)
            if label_info:
                label, unit = label_info
            else:
                label, unit = key, ""
            if isinstance(value, float):
                val_str = f"{value:.4g}"
                if unit:
                    val_str += f" {unit}"
                lines.append(f"  {label}: {val_str}")
            elif isinstance(value, (int, str, bool)):
                lines.append(f"  {label}: {value}")
        return "\n".join(lines) if len(lines) > 1 else ""

    @classmethod
    def _format_batch_results(cls, tool_name: str, tool_zh: str, results: list) -> str:
        """将同一个工具的多次调用结果合并为表格"""

        if tool_name == "calculate_liquidus_temperature":
            lines = [f"**{tool_zh}计算结果**:\n"]
            lines.append("| 序号 | 液相线温度 (K) | 液相线温度 (°C) | 熔点降低 (K) |")
            lines.append("|------|---------------|----------------|-------------|")
            for i, d in enumerate(results, 1):
                t_k = d.get("liquidus_temperature", 0)
                t_c = d.get("liquidus_temperature_celsius", t_k - 273.15)
                dep = d.get("melting_point_depression", 0)
                lines.append(f"| {i} | {t_k:.1f} | {t_c:.1f} | {dep:.2f} |")
            return "\n".join(lines)

        if tool_name in ("calculate_activity", "calculate_activity_coefficient"):
            lines = [f"**{tool_zh}计算结果**:\n"]
            has_gamma = any("gamma" in d for d in results)
            has_activity = any("activity" in d for d in results)
            header = "| 组元 | 温度 (K) |"
            sep = "|------|---------|"
            if has_gamma:
                header += " γ (活度系数) | ln γ |"
                sep += "-------------|------|"
            if has_activity:
                header += " a (活度) |"
                sep += "---------|"
            lines.append(header)
            lines.append(sep)
            for d in results:
                comp = d.get("component", "?")
                temp = d.get("temperature", "?")
                row = f"| {comp} | {temp} |"
                if has_gamma:
                    g = d.get("gamma")
                    lg = d.get("ln_gamma")
                    row += f" {g:.4g} |" if g is not None else " — |"
                    row += f" {lg:.4g} |" if lg is not None else " — |"
                if has_activity:
                    a = d.get("activity")
                    row += f" {a:.4g} |" if a is not None else " — |"
                lines.append(row)
            return "\n".join(lines)

        if tool_name == "get_interaction_coefficient":
            lines = [f"**{tool_zh}计算结果**:\n"]
            lines.append("| 溶剂 | i | j | 温度 (K) | ε_i^j |")
            lines.append("|------|---|---|---------|-------|")
            for d in results:
                sv = d.get("solvent", "?")
                si = d.get("solute_i", "?")
                sj = d.get("solute_j", "?")
                t = d.get("temperature", "?")
                e = d.get("epsilon_i_j")
                e_str = f"{e:.4g}" if e is not None else "—"
                lines.append(f"| {sv} | {si} | {sj} | {t} | {e_str} |")
            return "\n".join(lines)

        if tool_name == "calculate_melting_point_depression":
            lines = [f"**{tool_zh}计算结果**:\n"]
            lines.append("| 溶质 | 含量 (%) | 液相线温度 (K) | 液相线温度 (°C) | 熔点降低 (K) |")
            lines.append("|------|---------|---------------|----------------|-------------|")
            for d in results:
                solute = d.get("solute", "?")
                pct = d.get("solute_content_percent", "?")
                t_k = d.get("liquidus_temperature_K", 0)
                t_c = d.get("liquidus_temperature_C", t_k - 273.15 if isinstance(t_k, (int, float)) else "?")
                dep = d.get("melting_point_depression_K", 0)
                lines.append(f"| {solute} | {pct} | {t_k:.1f} | {t_c:.1f} | {dep:.2f} |")
            return "\n".join(lines)

        # 通用批量：逐条格式化
        parts = [f"**{tool_zh}** — 共 {len(results)} 条结果:\n"]
        for i, d in enumerate(results, 1):
            single = cls._format_single_result(tool_name, f"第{i}条", d)
            if single:
                parts.append(f"{i}. {single}")
        return "\n".join(parts)

    @staticmethod
    def _format_all_properties(data: dict) -> str:
        """格式化 calculate_all_properties 结果"""
        temp = data.get("temperature", "?")
        lines = [f"**热力学性质**（{temp}K）:\n"]

        # 整体性质 (alloy子字典)
        alloy = data.get("alloy", {})
        for key, label in [("molar_enthalpy_J_per_mol", "混合焓"),
                           ("gibbs_energy_J_per_mol", "Gibbs自由能"),
                           ("entropy_J_per_mol_K", "摩尔熵")]:
            val = alloy.get(key) or data.get(key)
            if val is not None:
                lines.append(f"  {label}: {val:.4g} J/mol")

        # 各组元性质
        components = data.get("components", {})
        if components:
            lines.append("")
            lines.append("| 组元 | 摩尔分数 | γ (活度系数) | a (活度) | μ (化学势, J/mol) |")
            lines.append("|------|---------|-------------|---------|------------------|")
            for comp, props in components.items():
                xf = props.get("mole_fraction", "—")
                gamma = props.get("gamma", "—")
                activity = props.get("activity", "—")
                mu = props.get("chemical_potential_J_per_mol", "—")
                x = f"{xf:.4g}" if isinstance(xf, float) else str(xf)
                g = f"{gamma:.4g}" if isinstance(gamma, float) else str(gamma)
                a = f"{activity:.4g}" if isinstance(activity, float) else str(activity)
                m = f"{mu:.4g}" if isinstance(mu, float) else str(mu)
                lines.append(f"| {comp} | {x} | {g} | {a} | {m} |")

        return "\n".join(lines)

    @staticmethod
    def _format_screening_result(data: dict) -> str:
        """格式化 screen_elements_liquidus_effect 结果"""
        base_k = data.get("base_liquidus_K", "?")
        base_c = data.get("base_liquidus_C", "?")
        pct = data.get("addition_percent", "?")
        base_desc = data.get("base_composition", "?")
        results = data.get("results", [])
        summary = data.get("summary", {})

        lines = [f"**元素对液相线温度影响筛选**（基础合金: {base_desc}）"]
        lines.append(f"基础液相线温度: {base_k} K ({base_c}°C)，添加量: {pct}%\n")
        lines.append("| 排名 | 元素 | 液相线温度 (K) | 液相线温度 (°C) | ΔT (K) |")
        lines.append("|------|------|---------------|----------------|--------|")
        for i, r in enumerate(results, 1):
            elem = r.get("element", "?")
            t_k = r.get("liquidus_temperature_K", "?")
            t_c = r.get("liquidus_temperature_C", "?")
            dt = r.get("delta_T_K", "?")
            dt_str = f"{dt:+.2f}" if isinstance(dt, (int, float)) else str(dt)
            lines.append(f"| {i} | {elem} | {t_k} | {t_c} | {dt_str} |")

        if summary:
            lines.append("")
            max_dep = summary.get("max_depression", {})
            min_dep = summary.get("min_depression", {})
            if max_dep:
                lines.append(f"降低液相线最多: **{max_dep.get('element')}** (ΔT = {max_dep.get('delta_T_K'):+.2f} K)")
            if min_dep:
                lines.append(f"降低液相线最少: **{min_dep.get('element')}** (ΔT = {min_dep.get('delta_T_K'):+.2f} K)")

        errors = data.get("errors", [])
        if errors:
            lines.append("")
            lines.append("计算失败的元素:")
            for err in errors:
                lines.append(f"  - {err.get('element', '?')}: {err.get('error', '未知错误')}")

        return "\n".join(lines)

    def save_session(self):
        """保存当前对话到磁盘"""
        history = self.get_history()
        if history:
            self.memory.save_session(history)

    def reset(self):
        """重置会话（先保存再重置）"""
        self.save_session()
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
