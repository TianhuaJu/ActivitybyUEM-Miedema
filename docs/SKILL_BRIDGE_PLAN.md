# Skill Bridge 实现计划 — 让动态技能调用内置工具

## 目标

让用户通过对话创建的动态技能（SkillRegistry）可以调用内置计算工具（ThermodynamicTools），
实现「编排型技能」：用户描述多步计算流程 → AI 生成编排代码 → 技能自动串联内置工具完成任务。

## 示例场景

用户说："帮我做一个工具，输入合金成分，同时计算液相线温度和各溶质的活度系数，并汇总比较。"

AI 创建编排型技能：
```python
def compare_liquidus_and_activity(composition: dict, temperature: float) -> dict:
    # 调用内置工具计算液相线温度
    liq = call_tool("calculate_liquidus_temperature", composition=composition)
    # 调用内置工具计算活度系数
    act = call_tool("calculate_activity_coefficient", composition=composition, temperature=temperature)
    # 汇总
    return {
        "status": "success",
        "liquidus": liq.get("liquidus_temperature"),
        "activity_coefficients": act.get("results"),
        "summary": f"液相线温度 {liq.get('liquidus_temperature')}K, 共 {len(act.get('results', {}))} 个溶质"
    }
```

## 实现步骤

### Step 1: SkillRegistry 添加 ToolBridge 桥接器 [skill_registry.py]

- 新增 `ToolBridge` 类，包装 `ThermodynamicTools.execute_tool()`
- 提供 `call_tool(name, **kwargs) -> dict` 接口给技能代码调用
- `execute_tool` 返回 JSON 字符串 → ToolBridge 自动 `json.loads` 为 dict
- 安全限制：只暴露计算类工具，屏蔽 `save_memory`, `delete_memory`, `create_custom_tool` 等副作用工具
- 调用深度限制：防止技能→工具→技能的递归循环（max_depth=1）

### Step 2: _compile() 注入桥接器到沙箱 [skill_registry.py]

- `SkillRegistry.__init__` 新增 `tools_ref` 可选参数
- `_compile()` 将 `call_tool` 函数注入 `safe_globals`
- 无 tools_ref 时 `call_tool` 为 no-op（返回 error dict），保证向后兼容

### Step 3: ChatAgent 传递 tools 引用 [chat_agent.py]

- `ChatAgent.__init__` 中创建 SkillRegistry 后，调用 `skill_registry.bind_tools(self.tools)`
- 或修改 SkillRegistry 构造函数接受 tools 参数
- 确保 tools 引用在整个生命周期内有效

### Step 4: 更新 system prompt 和 schema [chat_agent.py, tools.py]

- SYSTEM_PROMPT 新增说明：create_custom_tool 的代码中可以使用 `call_tool("工具名", ...)` 调用内置工具
- 列出所有可调用工具名和简要说明
- create_custom_tool 的 code 参数描述中补充 `call_tool` 用法

### Step 5: 端到端验证

- py_compile 所有修改文件
- 确保向后兼容（无 tools_ref 时技能仍正常工作）
- 推送

## 可用内置工具清单（技能可调用）

| 工具名 | 说明 |
|--------|------|
| calculate_liquidus_temperature | 液相线温度 |
| calculate_precipitation_temperature | 析出温度 |
| calculate_activity | 活度 |
| calculate_activity_coefficient | 活度系数 |
| calculate_mixing_enthalpy | 混合焓 |
| calculate_gibbs_energy | Gibbs自由能 |
| calculate_chemical_potential | 化学势 |
| calculate_entropy | 摩尔熵 |
| calculate_all_properties | 全部热力学性质 |
| calculate_melting_point_depression | 熔点降低 |
| get_interaction_coefficient | 一阶交互作用系数 |
| get_second_order_interaction_coefficient | 二阶交互作用系数 |
| get_contribution_coefficients | 贡献系数 |
| get_infinite_dilution_activity_coefficient | 无限稀释活度系数 |
| get_element_properties | 元素性质 |
| screen_elements_liquidus_effect | 元素筛选 |
| search_knowledge | 搜索知识库 |

## 被屏蔽的工具（技能不可调用）

| 工具名 | 原因 |
|--------|------|
| save_memory | 副作用：修改记忆 |
| delete_memory | 副作用：删除记忆 |
| recall_memories | 无计算意义 |
| learn_knowledge | 副作用：修改知识库 |
| update_experimental_value | 副作用：修改实验数据 |
| list_user_data | 无计算意义 |
| create_custom_tool | 递归风险 |
| list_custom_tools | 无计算意义 |
| remove_custom_tool | 递归风险 |
| plot_chart | 需要 GUI 交互 |

## 文件修改清单

1. `llm/skill_registry.py` — Step 1 + 2
2. `llm/chat_agent.py` — Step 3 + 4（SYSTEM_PROMPT）
3. `llm/tools.py` — Step 4（schema 描述）
