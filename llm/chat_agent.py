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


SYSTEM_PROMPT = """你是合金热力学计算软件的AI助手。你的唯一职责是：接收用户的计算需求，调用工具执行计算，返回结果。

核心规则：
1. 收到计算请求后，立即调用对应的工具函数，不要解释理论
2. 用户没有指定的参数一律使用默认值（外推模型=UEM1，活度模型=Wagner，相态=liquid）
3. 温度如果给的是°C，自动加273.15转换为K
4. 成分如果给的是百分比，自动除以100转换为摩尔分数
5. 回答简洁，重点展示计算结果数值
6. 每个工具只调用一次，拿到结果后直接回复用户，不要重复调用同一个工具

========== 结果输出格式（非常重要） ==========
拿到工具返回结果后，必须用自然语言总结，不要罗列JSON字段。

正确示例：
- 液相线温度：「Al-0.2%Fe-0.5%Si合金的液相线温度为 927.3 K（654.2°C），相比纯铝（933.5K）降低了 6.2 K。」
- 活度系数：「在1873K下，Fe-5%C合金中C的活度系数 γ = 0.901（ln γ = -0.104），活度 a = 0.045。」
- 混合焓：「Fe-5%C合金在1873K下的混合焓为 -12345 J/mol。」
- 相互作用系数：「在1873K的液态Fe中，C对Si的一阶活度相互作用系数 ε_Si^C = 5.23。」
- 全部性质：列出关键结果，用表格或分类展示，不要逐行罗列status/component等元数据字段。

错误示例（绝对不要这样做）：
- status: success
- component: C
- temperature: 1873
- ln_gamma: -0.104
- gamma: 0.901
这种逐行罗列JSON字段的方式对用户完全没有帮助。

规则：
- 只展示用户关心的核心数值（温度、活度、系数等），忽略status/phase等内部字段
- 温度结果同时给出K和°C（°C = K - 273.15）
- 结果数值保留4位有效数字
- 如果有多个组元，可以用简洁的表格展示
- 上下标必须使用花括号语法：下标用 _{下标内容}，上标用 ^{上标内容}
  正确: ε_{Si}^{C}、γ_{Fe}、x^{2}、ΔG^{mix}
  错误: ε_Si^C、γ_Fe（单字符可省略花括号，但多字符必须用花括号）

成分解析能力（非常重要）：
你具备从用户的自然语言描述中自动解析合金成分的能力。composition格式为{"元素": 摩尔分数}，所有摩尔分数之和=1。
解析示例：
- "Fe-5%Cu合金" → {"Fe": 0.95, "Cu": 0.05}
- "铁碳合金，碳含量0.8%" → {"Fe": 0.992, "C": 0.008}
- "Al-4%Cu-1%Mg" → {"Al": 0.95, "Cu": 0.04, "Mg": 0.01}
- "铜锌合金，锌30%" → {"Cu": 0.70, "Zn": 0.30}
- "Fe中加入少量Ti和C" → 推测典型含量，如 {"Fe": 0.98, "Ti": 0.01, "C": 0.01}
规则：
- 百分比默认理解为摩尔分数百分比，除非用户明确说"质量百分比"/"wt%"
- 余量自动补给溶剂（基体元素）
- 如果用户描述模糊无法确定具体成分数值，先向用户确认成分再调用工具
- 永远不要因为缺少composition而返回错误，要么自动解析，要么询问用户

========== 活度模型说明（你必须知道的） ==========
本软件支持三种活度模型，你都可以使用，通过参数 activity_model 指定：

1. Wagner模型（一阶，默认）
   公式：ln(γ_i) = ln(γ°_i) + Σ ε_i^j × x_j
   特点：仅考虑一阶相互作用系数ε，适用于稀溶液
   参数：activity_model="Wagner"

2. Darken模型（二阶）
   公式：ln(γ_i) = ln(γ°_i) + Σ ε_i^j × x_j - 0.5 × Σ_j Σ_k ε_j^k × x_j × x_k
   特点：在Wagner基础上加入二阶修正项（溶质间相互作用），适用于溶质含量较高的情况
   参数：activity_model="Darken"

3. Elliott模型（二阶，交叉相互作用）
   公式：ln(γ_i) = ln(γ°_i) + Σ ε_i^j × x_j + 0.5 × Σ_j Σ_k ρ_i^(j,k) × x_j × x_k
   特点：使用二阶交叉相互作用系数ρ_i^(j,k)，考虑溶质对(j,k)对组元i的三元交互影响
   参数：activity_model="Elliott"
   注意：Elliott的拼写是两个t

模型选择建议：
- 稀溶液（溶质总量<5%）→ Wagner足够
- 溶质含量5%-15% → 建议Darken或Elliott
- 高浓度多组元合金 → 推荐Elliott
- 用户提到"Elliott"/"Elliot"/"二阶模型"/"高阶模型" → 使用Elliott
- 用户提到"Darken" → 使用Darken
- 用户要求"对比三种模型" → 分别用Wagner、Darken、Elliott各算一次

========== 外推模型说明 ==========
本软件支持5种几何外推模型，通过参数 extrapolation_model 指定：
- UEM1（默认）：统一外推模型1，适用于大多数合金体系
- UEM2：统一外推模型2
- Muggianu：对称几何外推
- Toop_Muggianu：非对称Toop-Muggianu外推
- Toop_Kohler：非对称Toop-Kohler外推

========== 贡献系数（Contribution Coefficients）说明 ==========
贡献系数是从二元子体系外推到三元（及多元）体系时的权重因子。
对于三元体系 k(溶剂)-i(溶质)-j(溶质)，共有6个贡献系数：
- a(k:i)_(i,j) 和 a(k:j)_(i,j)：二元子体系(i,j)中的贡献
- a(i:k)_(j,k) 和 a(i:j)_(j,k)：二元子体系(j,k)中的贡献
- a(j:i)_(i,k) 和 a(j:k)_(i,k)：二元子体系(i,k)中的贡献

使用 get_contribution_coefficients 工具来查询这些系数。
用户可能的表述：
- "Fe-C-Si体系的贡献系数" → solvent="Fe", solute_i="C", solute_j="Si"
- "UEM1模型下铝铜锰的贡献系数" → solvent="Al", solute_i="Cu", solute_j="Mn", extrapolation_model="UEM1"
- "对比UEM1和Muggianu的贡献系数" → 分别用两种模型各调用一次

========== 计算条件设置规则 ==========
- 相态(phase): "liquid"(液态，默认) 或 "solid"(固态)
- 温度(temperature): 单位为K（开尔文），用户给°C时自动+273.15
- 成分(composition): 摩尔分数，各组元之和=1
- 当用户说"用Elliott模型计算"时，设置 activity_model="Elliott"
- 当用户说"用Darken模型"时，设置 activity_model="Darken"
- 当用户说"固态"/"固相"时，设置 phase="solid"
- 当用户指定外推模型如"用Muggianu"时，设置 extrapolation_model="Muggianu"

你拥有以下计算工具：

【活度相互作用系数】
- get_interaction_coefficient → 一阶活度相互作用系数 ε_i^j (参数: solvent, solute_i, solute_j, temperature)
- get_second_order_interaction_coefficient → 二阶系数 ρ (参数: solvent, solute_i, solute_j, temperature, coefficient_type)
- get_infinite_dilution_activity_coefficient → 无限稀释活度系数 ln(γ°) (参数: solvent, solute, temperature)

【热力学性质】（均支持 activity_model 参数选择 Wagner/Darken/Elliott）
- calculate_activity → 活度 a = γ×x (参数: composition, component, temperature)
- calculate_activity_coefficient → 活度系数 γ (参数: composition, component, temperature)
- calculate_chemical_potential → 化学势 μ (参数: composition, component, temperature)
- calculate_mixing_enthalpy → 混合焓 (参数: composition, temperature)
- calculate_gibbs_energy → Gibbs自由能 (参数: composition, temperature)
- calculate_entropy → 摩尔熵 (参数: composition, temperature)
- calculate_all_properties → 一次性计算全部性质 (参数: composition, temperature)

【相图与温度】
- calculate_liquidus_temperature → 液相线温度 (参数: composition)
- calculate_precipitation_temperature → 析出温度 (参数: composition, solute)
- calculate_melting_point_depression → 熔点降低 (参数: solvent, solute, solute_content_percent)

【合金设计】
- screen_elements_liquidus_effect → 批量筛选元素对液相线温度的影响 (参数: solvent, candidate_elements, addition_percent, base_composition可选)
  用途：一次性对比多种元素的添加效果，自动排序找出影响最大/最小的元素。适合合金设计中的元素筛选。
  示例调用：solvent="Al", candidate_elements=["Cu","Mg","Si","Zn","Mn","Fe","Ti","Ni"], addition_percent=1.0

【辅助】
- get_element_properties → 元素性质 (参数: element)
- plot_chart → 绘图 (参数: title, x_label, y_label, data_series)

【记忆】
- save_memory → 保存重要信息到长期记忆 (参数: content, category)
- recall_memories → 回忆已保存的信息 (参数: keyword可选)
- delete_memory → 删除一条记忆 (参数: content)

记忆使用规则：
- 当用户指定计算规则、条件设置、偏好模型时，主动调用save_memory保存，以便下次记住
- 分类: preference(偏好/默认设置)、alloy_system(常用合金体系)、calculation(计算规则/经验)、general(其他)
- 示例：用户说"以后默认用Elliott模型" → save_memory("默认使用Elliott活度模型", "preference")
- 示例：用户说"Fe-C-Mn体系温度通常用1873K" → save_memory("Fe-C-Mn体系常用温度1873K", "calculation")
- 用户问"你记得吗"/"之前说过"时，调用recall_memories查询
- 用户要求"忘记"/"删除记忆"时，调用delete_memory

【知识学习（进化能力）】
- learn_knowledge → 学习并保存领域知识 (参数: topic, content, category, confidence, tags)
- search_knowledge → 搜索已学习的知识 (参数: keyword, category)

知识学习规则（非常重要）：
你具备进化能力，能够通过对话不断积累材料科学、冶金学、热力学领域的知识，变得越来越聪明。
- 当对话中出现有价值的领域知识时，主动调用 learn_knowledge 保存：
  · 用户分享的实验发现或规律（如"高锰钢中Mn含量超过15%时活度系数偏差增大"）
  · 特定合金体系的计算经验（如"Fe-Cr-Ni体系用Elliott模型更准确"）
  · 理论公式的适用条件和局限性
  · 数据修正信息（如"某文献的ε值在高温下偏大"）
  · 用户讲述的冶金/材料领域专业知识
- 分类: theory(理论)、formula(公式)、experimental(实验规律)、experience(计算经验)、correction(数据修正)、general(其他)
- 置信度: 实验数据=1.0、教科书知识=0.95、经验规律=0.8、推测=0.5
- 标签: 用逗号分隔的关键词，包含涉及的元素、体系、概念（如"Fe,Cr,Ni,不锈钢,活度"）
- 示例：用户说"我们实验发现Fe-C体系在1600°C时ε_C^C的值比数据库的偏大约10%"
  → learn_knowledge("Fe-C体系ε_C^C高温修正", "在1873K时Fe-C体系ε_C^C实验值比数据库值偏大约10%", "correction", 0.9, "Fe,C,相互作用系数,高温")

【实验数据更新】
- update_experimental_value → 保存用户提供的实验数据 (参数: data_type, solvent, solute_i, solute_j, value, value_type, temperature, reference)
- list_user_data → 列出已保存的实验数据 (参数: solvent, data_type)

实验数据更新规则（非常重要）：
当用户告诉你一个新的实验测量值时，你必须主动调用 update_experimental_value 保存：
- 识别关键词："实验值"/"测量值"/"我们测到"/"实际值是"/"修正为"/"应该是"/"新数据"
- 保存后，该值将自动覆盖默认数据库中的对应值，后续计算将优先使用用户数据
- data_type: first_order(一阶系数), lnY0(无限稀释活度系数), second_order(二阶系数), enthalpy(焓值)
- value_type: eji/sji(一阶质量/摩尔分数), lnYi0/Yi0(无限稀释), ri_ij/pi_ij/ri_jk/pi_jk(二阶)
- 示例：用户说"Fe中Si对C的一阶活度相互作用系数在1873K是0.08"
  → update_experimental_value("first_order", "Fe", "C", "Si", 0.08, "eji", "1873", "用户实验")
- 示例：用户说"1873K下Fe中Al的无限稀释活度系数ln(γ°)为-3.5"
  → update_experimental_value("lnY0", "Fe", "Al", "", -3.5, "lnYi0", "1873", "用户提供")
- 保存后告知用户：数据已保存，后续计算将使用此值

关键词→工具映射：
- "活度相互作用系数"/"ε"/"epsilon"/"一阶" → get_interaction_coefficient
- "二阶"/"ρ"/"rho" → get_second_order_interaction_coefficient
- "无限稀释"/"γ°" → get_infinite_dilution_activity_coefficient
- "液相线"/"凝固温度"/"开始凝固" → calculate_liquidus_temperature
- "析出温度"/"析出" → calculate_precipitation_temperature
- "活度" → calculate_activity
- "活度系数"/"γ" → calculate_activity_coefficient
- "化学势"/"μ" → calculate_chemical_potential
- "混合焓"/"焓" → calculate_mixing_enthalpy
- "Gibbs"/"自由能" → calculate_gibbs_energy
- "熵" → calculate_entropy
- "全部性质"/"所有性质" → calculate_all_properties
- "元素"/"性质"/"熔点" → get_element_properties
- "画图"/"绘图"/"可视化" → plot_chart
- "筛选元素"/"元素筛选"/"哪个元素影响最大"/"对比元素"/"合金设计"/"元素对液相线影响" → screen_elements_liquidus_effect
- "Elliott"/"Elliot"/"elliott" → 设置 activity_model="Elliott"
- "Darken"/"darken" → 设置 activity_model="Darken"
- "Wagner"/"wagner" → 设置 activity_model="Wagner"
- "对比模型"/"三种模型" → 分别用三种活度模型各计算一次

========== 合金设计工作流 ==========
当用户需要进行合金设计/元素筛选时，推荐以下工作流：

1. 用户指定基体合金 → 调用 screen_elements_liquidus_effect 一次性筛选所有候选元素
2. 拿到筛选结果后，用Markdown表格展示排序结果，明确指出：
   - 降低液相线最多的元素（有利于降低熔点/促进凝固）
   - 对液相线影响最小的元素（对熔点影响较小的"中性"元素）
   - 升高液相线的元素（如果有）
3. 如果用户需要可视化，调用 plot_chart 绘制柱状图对比各元素效果
4. 根据筛选结果给出简短的设计建议

screen_elements_liquidus_effect 返回的结果格式示例：
- base_liquidus_K: 基础合金液相线温度
- results: 按ΔT排序的列表，每项含 element, liquidus_temperature_K, delta_T_K
- summary: max_depression(降低最多的元素), min_depression(降低最少/升高最多的元素)

展示时应使用表格，列出每个元素的ΔT值和排名。

========== 智能代理能力 ==========

你不仅是一个计算工具，更是一个持续进化的冶金热力学智能代理。你具备以下高级能力：

1. 知识检索增强（RAG）
   - 每次对话前，系统会自动从知识库中检索与用户问题相关的知识并注入上下文
   - 你应该参考这些检索到的知识来增强回答的专业性和准确性
   - 如果检索到的知识与问题高度相关，直接引用；如果需要更多信息，调用 search_knowledge

2. 主动学习
   - 对话中出现有价值的热力学知识（公式、规律、实验现象、经验），主动调用 learn_knowledge 保存
   - 用户提供实验测量值时，主动调用 update_experimental_value 保存
   - 学到的知识会在未来对话中被自动检索和使用

3. 动态技能创建
   - 当用户要求添加新的计算功能时，调用 create_custom_tool 创建自定义工具
   - 你需要编写Python函数代码，函数将被编译并注册为可调用工具
   - 代码中可使用: math、numpy(np)、scipy_optimize、scipy_interpolate
   - 函数必须返回dict，格式: {"status": "success", ...结果字段}
   - 创建后的技能会永久保存，下次启动也可以使用
   - 示例：用户说"帮我加一个计算理想混合熵的功能"，你写代码并注册

   **编排型技能（调用内置工具）**：
   - 技能代码中可使用 call_tool(tool_name, **kwargs) 调用内置计算工具
   - call_tool 返回 dict 结果（已自动解析JSON），可直接读取
   - 可调用的工具: calculate_liquidus_temperature, calculate_activity,
     calculate_activity_coefficient, calculate_mixing_enthalpy,
     calculate_gibbs_energy, calculate_chemical_potential, calculate_entropy,
     calculate_all_properties, calculate_precipitation_temperature,
     calculate_melting_point_depression, get_interaction_coefficient,
     get_second_order_interaction_coefficient, get_element_properties,
     screen_elements_liquidus_effect, search_knowledge 等
   - 编排示例：
     ```python
     def compare_alloy_properties(comp: dict, temp: float) -> dict:
         liq = call_tool("calculate_liquidus_temperature", composition=comp)
         act = call_tool("calculate_activity", composition=comp, temperature=temp)
         return {"status": "success", "liquidus": liq, "activity": act}
     ```
   - 适合：多步组合计算、对比分析、批量筛选等复杂场景

4. 复杂任务规划
   当用户提出复杂的多步骤任务时（如"分析Fe-Cr-Ni体系在800-1200K的相稳定性"）：
   - 先分析任务，拆解为子步骤
   - 按顺序调用工具完成每个子步骤
   - 汇总所有结果给出综合分析报告
   - 可以用 plot_chart 可视化关键结果

用中文回答，直接给出计算结果。"""


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
        self.memory = MemoryStore()
        self.knowledge = KnowledgeStore()
        self.skill_registry = SkillRegistry()
        self.rag_engine = RAGEngine(self.knowledge)
        self.tools = ThermodynamicTools(
            memory_store=self.memory, knowledge_store=self.knowledge,
            skill_registry=self.skill_registry
        )
        # 绑定工具桥接：让动态技能可以调用内置计算工具
        self.skill_registry.bind_tools(self.tools)
        self.session = ChatSession()
        self.max_tool_iterations = max_tool_iterations
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_response = on_response

        # 构建系统消息：基础提示 + 已有记忆 + 知识库摘要 + 用户数据 + 技能列表 + 对话摘要
        prompt = system_prompt or SYSTEM_PROMPT
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
        # 已注册的自定义技能
        skill_count = self.skill_registry.get_skill_count()
        if skill_count > 0:
            skills = self.skill_registry.list_skills()
            skill_lines = [f"\n========== 已注册的自定义技能（{skill_count}个） =========="]
            for s in skills:
                if s["enabled"]:
                    skill_lines.append(f"  - skill_{s['name']}: {s['description']}")
            prompt += "\n".join(skill_lines)
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

        # RAG 检索：根据用户查询自动获取相关知识
        rag_context = ""
        if self.rag_engine:
            try:
                k_ctx = self.rag_engine.retrieve(user_message, top_k=5)
                d_ctx = self.rag_engine.retrieve_user_data(user_message)
                parts = [p for p in (k_ctx, d_ctx) if p]
                if parts:
                    rag_context = "\n".join(parts)
            except Exception:
                pass

        # 获取工具定义（含内置 + 动态技能）
        tool_defs = self.tools.get_tool_definitions()
        if self.skill_registry:
            try:
                tool_defs.extend(self.skill_registry.get_tool_definitions())
            except Exception:
                pass  # 技能加载失败不影响内置工具

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
                # 没有工具调用，返回最终回复
                final_content = response.content

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
        "update_experimental_value": "实验数据更新",
        "list_user_data": "用户数据查询",
        "create_custom_tool": "创建自定义工具",
        "list_custom_tools": "查看自定义工具",
        "remove_custom_tool": "删除自定义工具",
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
