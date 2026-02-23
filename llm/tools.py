# -*- coding: utf-8 -*-
"""
LLM Tools - 热力学计算函数的工具定义
====================================
为LLM提供可调用的热力学计算函数接口

作者: Claude
日期: 2026-02-12
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.llm_backend import ToolDefinition


# ============= 工具定义 =============

TOOL_SCHEMAS = {
    "calculate_liquidus_temperature": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分，键为元素符号，值为摩尔分数。例如: {\"Al\": 0.95, \"Cu\": 0.05}",
                "additionalProperties": {"type": "number"}
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "description": "活度模型",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            }
        },
        "required": ["composition"]
    },

    "calculate_precipitation_temperature": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分，键为元素符号，值为摩尔分数。例如: {\"Fe\": 0.95, \"C\": 0.02}",
                "additionalProperties": {"type": "number"}
            },
            "solute": {
                "type": "string",
                "description": "溶质元素符号，即要计算析出温度的元素。例如: \"C\""
            },
            "solution_phase": {
                "type": "string",
                "description": "溶液相类型",
                "enum": ["LIQUID", "SOLID"],
                "default": "LIQUID"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "description": "活度模型",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            },
            "T_min": {
                "type": "number",
                "description": "温度搜索范围下限(K)",
                "default": 300
            },
            "T_max": {
                "type": "number",
                "description": "温度搜索范围上限(K)",
                "default": 3000
            }
        },
        "required": ["composition", "solute"]
    },

    "calculate_activity": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分，键为元素符号，值为摩尔分数",
                "additionalProperties": {"type": "number"}
            },
            "component": {
                "type": "string",
                "description": "要计算活度的组元符号"
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "description": "活度模型",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            }
        },
        "required": ["composition", "component", "temperature"]
    },

    "calculate_activity_coefficient": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分，键为元素符号，值为摩尔分数",
                "additionalProperties": {"type": "number"}
            },
            "component": {
                "type": "string",
                "description": "要计算活度系数的组元符号"
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "description": "活度模型",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            }
        },
        "required": ["composition", "component", "temperature"]
    },

    "calculate_mixing_enthalpy": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分，键为元素符号，值为摩尔分数",
                "additionalProperties": {"type": "number"}
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Kohler", "Muggianu", "Toop"],
                "default": "UEM1"
            }
        },
        "required": ["composition", "temperature"]
    },

    "calculate_gibbs_energy": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分，键为元素符号，值为摩尔分数",
                "additionalProperties": {"type": "number"}
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "description": "活度模型",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            }
        },
        "required": ["composition", "temperature"]
    },

    "get_element_properties": {
        "type": "object",
        "properties": {
            "element": {
                "type": "string",
                "description": "元素符号，如 'Fe', 'Al', 'Cu'"
            }
        },
        "required": ["element"]
    },

    "calculate_melting_point_depression": {
        "type": "object",
        "properties": {
            "solvent": {
                "type": "string",
                "description": "溶剂元素符号，如 'Al'"
            },
            "solute": {
                "type": "string",
                "description": "溶质元素符号，如 'Cu'"
            },
            "solute_content_percent": {
                "type": "number",
                "description": "溶质含量(质量百分比或摩尔百分比)"
            },
            "content_type": {
                "type": "string",
                "description": "含量类型",
                "enum": ["mole_percent", "weight_percent"],
                "default": "mole_percent"
            }
        },
        "required": ["solvent", "solute", "solute_content_percent"]
    },

    "plot_chart": {
        "type": "object",
        "properties": {
            "chart_type": {
                "type": "string",
                "description": "图表类型",
                "enum": ["line", "scatter", "bar"],
                "default": "line"
            },
            "title": {
                "type": "string",
                "description": "图表标题"
            },
            "x_label": {
                "type": "string",
                "description": "X轴标签"
            },
            "y_label": {
                "type": "string",
                "description": "Y轴标签"
            },
            "data_series": {
                "type": "array",
                "description": "数据系列列表，每个系列包含名称和数据点",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "数据系列名称（图例标签）"
                        },
                        "x_values": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "X轴数据"
                        },
                        "y_values": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "Y轴数据"
                        }
                    },
                    "required": ["name", "x_values", "y_values"]
                }
            }
        },
        "required": ["title", "x_label", "y_label", "data_series"]
    },

    "get_interaction_coefficient": {
        "type": "object",
        "properties": {
            "solvent": {
                "type": "string",
                "description": "溶剂元素符号（基体），如 'Fe', 'Al'"
            },
            "solute_i": {
                "type": "string",
                "description": "溶质i的元素符号（被影响的溶质）"
            },
            "solute_j": {
                "type": "string",
                "description": "溶质j的元素符号（施加影响的溶质）"
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            }
        },
        "required": ["solvent", "solute_i", "solute_j", "temperature"]
    },

    "get_second_order_interaction_coefficient": {
        "type": "object",
        "properties": {
            "solvent": {
                "type": "string",
                "description": "溶剂元素符号（基体）"
            },
            "solute_i": {
                "type": "string",
                "description": "溶质i的元素符号"
            },
            "solute_j": {
                "type": "string",
                "description": "溶质j的元素符号（与solute_i相同则计算自相互作用系数ρ_i^ii）"
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "coefficient_type": {
                "type": "string",
                "description": "二阶系数类型: rho_ii(自相互作用ρ_i^ii), rho_jj(混合ρ_i^jj), rho_ij(交叉ρ_i^ij)",
                "enum": ["rho_ii", "rho_jj", "rho_ij"],
                "default": "rho_ij"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            }
        },
        "required": ["solvent", "solute_i", "solute_j", "temperature"]
    },

    "get_contribution_coefficients": {
        "type": "object",
        "properties": {
            "solvent": {
                "type": "string",
                "description": "溶剂元素符号（基体），如 'Fe'"
            },
            "solute_i": {
                "type": "string",
                "description": "溶质i的元素符号，如 'C'"
            },
            "solute_j": {
                "type": "string",
                "description": "溶质j的元素符号，如 'Si'"
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            }
        },
        "required": ["solvent", "solute_i", "solute_j", "temperature"]
    },

    "get_infinite_dilution_activity_coefficient": {
        "type": "object",
        "properties": {
            "solvent": {
                "type": "string",
                "description": "溶剂元素符号（基体），如 'Fe'"
            },
            "solute": {
                "type": "string",
                "description": "溶质元素符号，如 'C', 'Mn'"
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            }
        },
        "required": ["solvent", "solute", "temperature"]
    },

    "calculate_chemical_potential": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分，键为元素符号，值为摩尔分数",
                "additionalProperties": {"type": "number"}
            },
            "component": {
                "type": "string",
                "description": "要计算化学势的组元符号"
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "description": "活度模型",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            }
        },
        "required": ["composition", "component", "temperature"]
    },

    "calculate_entropy": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分，键为元素符号，值为摩尔分数",
                "additionalProperties": {"type": "number"}
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "description": "活度模型",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            }
        },
        "required": ["composition", "temperature"]
    },

    "calculate_all_properties": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分，键为元素符号，值为摩尔分数",
                "additionalProperties": {"type": "number"}
            },
            "temperature": {
                "type": "number",
                "description": "温度(K)"
            },
            "phase": {
                "type": "string",
                "description": "相态",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "description": "活度模型",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            }
        },
        "required": ["composition", "temperature"]
    },

    # === 合金设计工具 ===
    "screen_elements_liquidus_effect": {
        "type": "object",
        "properties": {
            "solvent": {
                "type": "string",
                "description": "溶剂（基体）元素符号，如 'Fe', 'Al'"
            },
            "candidate_elements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "候选溶质元素列表，如 [\"Cu\", \"Mg\", \"Si\", \"Zn\", \"Mn\"]"
            },
            "addition_percent": {
                "type": "number",
                "description": "每种候选元素的添加量(摩尔百分比)，默认1%",
                "default": 1.0
            },
            "base_composition": {
                "type": "object",
                "description": "可选的基础合金成分(摩尔分数)。如不指定，则以纯溶剂为基础。如 {\"Fe\": 0.95, \"C\": 0.02, \"Mn\": 0.03}",
                "additionalProperties": {"type": "number"}
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "description": "活度模型",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            }
        },
        "required": ["solvent", "candidate_elements"]
    },

    # === 记忆工具 ===
    "save_memory": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "要记住的信息内容"
            },
            "category": {
                "type": "string",
                "description": "记忆分类",
                "enum": ["preference", "alloy_system", "calculation", "general"],
                "default": "general"
            }
        },
        "required": ["content"]
    },
    "recall_memories": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词（可选，不填则返回所有记忆）",
                "default": ""
            }
        },
        "required": []
    },
    "delete_memory": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "要删除的记忆内容（精确匹配）"
            }
        },
        "required": ["content"]
    },

    # === 知识学习工具 ===
    "learn_knowledge": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "知识主题，简短概括（如'Fe-C体系活度系数温度依赖性'）"
            },
            "content": {
                "type": "string",
                "description": "知识内容，详细描述"
            },
            "category": {
                "type": "string",
                "description": "知识分类",
                "enum": ["theory", "formula", "experimental", "experience", "correction", "general"],
                "default": "general"
            },
            "confidence": {
                "type": "number",
                "description": "置信度(0-1)，实验数据=1.0，经验规律=0.8，推测=0.5",
                "default": 0.8
            },
            "tags": {
                "type": "string",
                "description": "标签，逗号分隔（如'Fe,C,活度,温度'）",
                "default": ""
            }
        },
        "required": ["topic", "content"]
    },
    "optimize_knowledge": {
        "type": "object",
        "properties": {
            "similarity_threshold": {
                "type": "number",
                "description": "相似度阈值(0-1)，超过此阈值的知识将被建议合并。默认0.6",
                "default": 0.6
            }
        },
        "required": []
    },
    "search_knowledge": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词（搜索主题、内容和标签）",
                "default": ""
            },
            "category": {
                "type": "string",
                "description": "按分类过滤（可选）",
                "enum": ["theory", "formula", "experimental", "experience", "correction", "general"],
                "default": ""
            }
        },
        "required": []
    },

    # === 实验数据更新工具 ===
    "update_experimental_value": {
        "type": "object",
        "properties": {
            "data_type": {
                "type": "string",
                "description": "数据类型",
                "enum": ["first_order", "lnY0", "second_order", "enthalpy"]
            },
            "solvent": {
                "type": "string",
                "description": "基体（溶剂）元素符号，如'Fe'"
            },
            "solute_i": {
                "type": "string",
                "description": "溶质i元素符号"
            },
            "solute_j": {
                "type": "string",
                "description": "溶质j元素符号（一阶系数必填，lnY0可不填）",
                "default": ""
            },
            "value": {
                "type": "number",
                "description": "实验数值"
            },
            "value_type": {
                "type": "string",
                "description": "值的类型：eji(质量分数一阶), sji(摩尔分数一阶), lnYi0(无限稀释活度系数对数), Yi0(无限稀释活度系数), ri_ij/pi_ij(二阶系数)",
                "enum": ["eji", "sji", "lnYi0", "Yi0", "ri_ij", "pi_ij", "ri_jk", "pi_jk"]
            },
            "temperature": {
                "type": "string",
                "description": "温度(K)或温度公式，如'1873'或'-126300/T+39.0'"
            },
            "reference": {
                "type": "string",
                "description": "数据来源/文献引用",
                "default": "用户提供"
            }
        },
        "required": ["data_type", "solvent", "solute_i", "value", "value_type", "temperature"]
    },
    "list_user_data": {
        "type": "object",
        "properties": {
            "solvent": {
                "type": "string",
                "description": "按基体元素过滤（可选）",
                "default": ""
            },
            "data_type": {
                "type": "string",
                "description": "按数据类型过滤（可选）",
                "default": ""
            }
        },
        "required": []
    },

    # ========== DFT 校准工具 ==========

    "store_dft_compound_energy": {
        "type": "object",
        "properties": {
            "compound_name": {
                "type": "string",
                "description": "化合物名称，如 'TiC', 'Fe3C', 'Ni3Al'"
            },
            "elements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "组成元素列表，如 ['Ti', 'C']"
            },
            "stoichiometry": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "化学计量数列表，如 [1, 1]"
            },
            "formation_energy_J": {
                "type": "number",
                "description": "形成能 ΔH_f (J/mol-atom)。可从 DFT 计算或文献获取"
            },
            "delta_G_A": {
                "type": "number",
                "description": "Gibbs 自由能系数 A，ΔG(T) = A + B*T (J/mol)。不提供则默认等于形成能",
                "default": 0
            },
            "delta_G_B": {
                "type": "number",
                "description": "Gibbs 自由能系数 B (J/(mol·K))。不提供则默认为 0",
                "default": 0
            },
            "source": {
                "type": "string",
                "description": "数据来源",
                "enum": ["dft", "literature", "user"],
                "default": "dft"
            },
            "dft_engine": {
                "type": "string",
                "description": "DFT 引擎名称（如 'vasp', 'qe'）",
                "default": ""
            },
            "reference": {
                "type": "string",
                "description": "参考文献或备注",
                "default": ""
            }
        },
        "required": ["compound_name", "elements", "stoichiometry", "formation_energy_J"]
    },

    "calculate_liquidus_dft_calibrated": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分 {元素: 摩尔分数}",
                "additionalProperties": {"type": "number"}
            },
            "extrapolation_model": {
                "type": "string",
                "description": "外推模型名称",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "description": "活度模型",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            }
        },
        "required": ["composition"]
    },

    "calculate_precipitation_dft_calibrated": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "合金成分 {元素: 摩尔分数}",
                "additionalProperties": {"type": "number"}
            },
            "phase_type": {
                "type": "string",
                "description": "析出相名称，如 'TiC', 'Fe3C', 'Ni3Al'"
            },
            "solution_phase": {
                "type": "string",
                "enum": ["LIQUID", "SOLID"],
                "default": "LIQUID"
            },
            "extrapolation_model": {
                "type": "string",
                "enum": ["UEM1", "UEM2", "Muggianu", "Toop_Muggianu", "Toop_Kohler"],
                "default": "UEM1"
            },
            "activity_model": {
                "type": "string",
                "enum": ["Wagner", "Darken", "Elliott"],
                "default": "Wagner"
            }
        },
        "required": ["composition", "phase_type"]
    },

    "compare_mixing_enthalpy": {
        "type": "object",
        "properties": {
            "element_a": {
                "type": "string",
                "description": "元素 A"
            },
            "element_b": {
                "type": "string",
                "description": "元素 B"
            },
            "temperature": {
                "type": "number",
                "description": "温度 (K)",
                "default": 1800
            },
            "phase": {
                "type": "string",
                "enum": ["liquid", "solid"],
                "default": "liquid"
            }
        },
        "required": ["element_a", "element_b"]
    },

    "get_dft_data_summary": {
        "type": "object",
        "properties": {
            "element_filter": {
                "type": "string",
                "description": "按元素过滤（可选）"
            }
        },
        "required": []
    },

    "import_dft_result": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "DFT 计算任务 ID"
            },
            "compound_name": {
                "type": "string",
                "description": "化合物名称"
            },
            "elements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "组成元素"
            },
            "stoichiometry": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "化学计量数"
            },
            "reference_energies": {
                "type": "object",
                "description": "纯元素参考能量 {元素: eV/atom}",
                "additionalProperties": {"type": "number"}
            }
        },
        "required": ["compound_name", "elements", "stoichiometry", "reference_energies"]
    },

    # ========== 溶解度积计算工具 ==========

    "calculate_solubility_product": {
        "type": "object",
        "properties": {
            "compound": {
                "type": "string",
                "description": "化合物名称或平衡反应方程式。例如: \"TiN\", \"NbC\", \"AlN\", 或 \"TiN = [Ti] + [N]\""
            },
            "temperature": {
                "type": "number",
                "description": "温度 (K)"
            },
            "phase": {
                "type": "string",
                "description": "基体相",
                "enum": ["AUSTENITE", "FERRITE", "LIQUID"],
                "default": "AUSTENITE"
            },
            "method": {
                "type": "string",
                "description": "计算方法: empirical(经验公式,默认), thermodynamic(热力学), both(两种对比)",
                "enum": ["empirical", "thermodynamic", "both"],
                "default": "empirical"
            }
        },
        "required": ["compound", "temperature"]
    },

    "calculate_precipitation_temperature_sp": {
        "type": "object",
        "properties": {
            "compound": {
                "type": "string",
                "description": "化合物名称，如 \"TiN\", \"NbC\""
            },
            "metal_content": {
                "type": "number",
                "description": "金属元素质量百分数 (wt%)，如 Ti=0.02 表示 0.02%Ti"
            },
            "nonmetal_content": {
                "type": "number",
                "description": "非金属元素质量百分数 (wt%)，如 N=0.005 表示 0.005%N"
            },
            "phase": {
                "type": "string",
                "description": "基体相",
                "enum": ["AUSTENITE", "FERRITE", "LIQUID"],
                "default": "AUSTENITE"
            }
        },
        "required": ["compound", "metal_content", "nonmetal_content"]
    },

    "calculate_equilibrium_solubility": {
        "type": "object",
        "properties": {
            "compound": {
                "type": "string",
                "description": "化合物名称，如 \"TiN\", \"NbC\""
            },
            "temperature": {
                "type": "number",
                "description": "温度 (K)"
            },
            "fixed_element": {
                "type": "string",
                "description": "已知含量的元素符号或角色。如 \"Ti\", \"N\", \"metal\", \"nonmetal\""
            },
            "fixed_content": {
                "type": "number",
                "description": "已知元素的质量百分数 (wt%)"
            },
            "phase": {
                "type": "string",
                "description": "基体相",
                "enum": ["AUSTENITE", "FERRITE", "LIQUID"],
                "default": "AUSTENITE"
            }
        },
        "required": ["compound", "temperature", "fixed_element", "fixed_content"]
    },

    "get_precipitation_sequence": {
        "type": "object",
        "properties": {
            "composition": {
                "type": "object",
                "description": "钢的成分（质量百分数 wt%）。例如: {\"Ti\": 0.015, \"Nb\": 0.025, \"C\": 0.08, \"N\": 0.008}",
                "additionalProperties": {"type": "number"}
            },
            "phase": {
                "type": "string",
                "description": "基体相",
                "enum": ["AUSTENITE", "FERRITE", "LIQUID"],
                "default": "AUSTENITE"
            }
        },
        "required": ["composition"]
    },
}

TOOL_DESCRIPTIONS = {
    "calculate_liquidus_temperature": "计算合金的液相线温度（开始凝固温度）。基于修正的Schroder-van Laar方程，考虑溶质相互作用对溶剂活度的影响。",
    "calculate_precipitation_temperature": "计算合金中指定溶质的析出温度。基于热力学平衡条件μ_solute = G°_precipitate求解。",
    "calculate_activity": "计算合金中指定组元的活度 a = γ × x，其中γ是活度系数，x是摩尔分数。",
    "calculate_activity_coefficient": "计算合金中指定组元的活度系数γ，基于UEM-Miedema模型框架。",
    "calculate_mixing_enthalpy": "计算合金的混合焓（过剩焓），基于Miedema模型。",
    "calculate_gibbs_energy": "计算合金的摩尔Gibbs自由能，包含理想混合和过剩贡献。",
    "get_element_properties": "获取元素的基本热力学性质，包括熔点、原子半径、电负性等。",
    "calculate_melting_point_depression": "计算指定溶质含量对溶剂熔点的降低值。",
    "plot_chart": "在对话中绘制图表。支持折线图、散点图、柱状图。可同时绘制多条数据曲线进行对比。用于将计算结果可视化展示。",
    "get_interaction_coefficient": "计算一阶活度相互作用系数 ε_i^j（epsilon）。描述溶剂中溶质j对溶质i活度系数的影响。基于UEM-Miedema模型。Wagner模型: ln(γ_i) = ln(γ_i^∞) + Σ ε_i^j * x_j。这是冶金热力学中最核心的参数之一。",
    "get_second_order_interaction_coefficient": "计算二阶活度相互作用系数ρ。支持三种类型: ρ_i^ii(自相互作用), ρ_i^jj(混合相互作用), ρ_i^ij(交叉相互作用)。用于Darken/Elliott等高阶活度模型。",
    "get_contribution_coefficients": "计算三元体系的贡献系数（contribution coefficients）。贡献系数是从二元子体系外推到多元体系时的权重因子，共6个参数：a_{k:i}^{i,j}、a_{k:j}^{i,j}、a_{i:k}^{j,k}、a_{i:j}^{j,k}、a_{j:i}^{i,k}、a_{j:k}^{i,k}。不同外推模型（UEM1、Muggianu等）会给出不同的贡献系数值。这些系数用于计算活度相互作用系数ε。",
    "get_infinite_dilution_activity_coefficient": "计算无限稀释活度系数 ln(γ°_i)。即溶质i在溶剂中浓度趋于0时的活度系数对数。基于Miedema模型计算化学相互作用能。",
    "calculate_chemical_potential": "计算合金中指定组元的化学势 μ_i = μ°_i(T) + RT·ln(a_i)。其中μ°_i(T)从SGTE热力学数据库获取，a_i由活度计算给出。",
    "calculate_entropy": "计算合金的摩尔熵 S = (H - G) / T。其中H为摩尔焓，G为摩尔Gibbs自由能。",
    "calculate_all_properties": "一次性计算合金的所有热力学性质。包括每个组元的活度系数γ、活度a、化学势μ，以及合金整体的摩尔焓H、Gibbs自由能G、摩尔熵S。",
    "screen_elements_liquidus_effect": "批量筛选多种元素对合金液相线温度的影响。输入溶剂和候选元素列表，一次性计算所有元素在指定添加量下对液相线温度的降低/升高效果，返回按影响大小排序的结果。用于合金设计中的元素筛选。",
    "save_memory": "保存一条重要信息到长期记忆。当用户提到偏好、常用合金体系、计算习惯等值得记住的信息时，主动调用此工具保存。分类: preference(偏好)、alloy_system(合金体系)、calculation(计算经验)、general(其他)。",
    "recall_memories": "回忆已保存的记忆。可按关键词搜索，不填关键词则返回所有记忆。当用户问'你还记得吗'、'之前说过'等时调用。",
    "delete_memory": "删除一条已保存的记忆。当用户要求忘记某信息时调用。",
    "learn_knowledge": "从对话中学习并保存领域知识。当对话中出现有价值的材料科学、热力学、冶金学知识（理论、公式、实验规律、计算经验等）时，主动调用此工具保存。分类：theory(理论)、formula(公式)、experimental(实验数据规律)、experience(计算经验)、correction(数据修正)、general(其他)。",
    "optimize_knowledge": "优化知识库：自动检测相似或重复的知识条目，合并去重，提升知识库质量。当用户要求整理/优化知识库，或知识库条目较多时主动调用。",
    "search_knowledge": "搜索已学习的领域知识。可按关键词和分类检索。当需要参考之前学到的知识时调用。",
    "update_experimental_value": "保存或更新用户提供的实验数据到用户数据库。当用户告诉你一个新的实验测量值（如活度相互作用系数、活度系数等）时，主动调用此工具保存。保存后该值将在后续计算中优先使用。支持一阶系数(first_order)、无限稀释活度系数(lnY0)、二阶系数(second_order)、焓值(enthalpy)。",
    "list_user_data": "列出用户已保存的所有实验数据。可按基体元素和数据类型过滤。",
    "create_custom_tool": "创建自定义计算工具（技能）。当用户要求添加新的计算功能时调用。你需要编写一个Python函数，该函数将被注册为可调用工具。函数内可使用math、numpy(np)、scipy_optimize、scipy_interpolate。",
    "list_custom_tools": "列出所有已注册的自定义工具（技能），包括名称、描述和状态。",
    "remove_custom_tool": "删除一个已注册的自定义工具（技能）。",
    "store_dft_compound_energy": "存储 DFT 计算或文献中的化合物形成能数据。存储后该数据将在液相线温度、析出温度、固溶度等计算中自动优先使用，替代内置经验值。支持存储 ΔH_f 和 ΔG(T) = A + B*T 格式。",
    "calculate_liquidus_dft_calibrated": "使用 DFT 数据校准的液相线温度计算。如果 DFT 数据库中有相关的端基能量或混合焓数据，自动使用 DFT 值进行校准；否则回退到 Miedema 经验值。返回结果中标注数据来源。",
    "calculate_precipitation_dft_calibrated": "使用 DFT 数据校准的析出温度计算。如果 DFT 数据库中有该化合物的形成能，自动使用 DFT 值替代内置经验数据库；否则回退到经验值。返回结果中标注是否使用了 DFT 校准。",
    "compare_mixing_enthalpy": "对比 Miedema 模型预测和 DFT 计算的二元系混合焓曲线。返回 Miedema 曲线和 DFT 数据点，以及偏差统计。用于评估 Miedema 模型在特定体系的预测精度。",
    "get_dft_data_summary": "获取 DFT 数据库的统计信息和所有存储的数据概要。包括化合物数量、混合焓数据点数、元素参数数量等。",
    "import_dft_result": "从已完成的 DFT 计算任务中自动导入结果到 DFT 数据库。需要提供化合物信息和纯元素参考能量，系统自动计算形成能并存储。",
    "calculate_solubility_product": "计算化合物（碳化物、氮化物、硫化物等）在指定相中的溶解度积Ksp。支持经验公式法（Turkdogan，基于wt%）和热力学法（基于Gibbs能）。可用于TiN、NbC、VC、AlN、MnS等约40种化合物。经验表达式: log[%M][%X]^n = A - B/T。",
    "calculate_precipitation_temperature_sp": "根据溶解度积计算化合物在钢中的析出温度。输入化合物名称和金属/非金属元素的质量百分数(wt%)，返回析出温度。基于 T = B/(A - log[%M][%X]^n)。",
    "calculate_equilibrium_solubility": "计算给定温度下化合物的平衡溶解度。固定一种元素含量，计算另一种元素的平衡含量(wt%)。例如：已知温度和[Ti]含量，计算平衡[N]含量。",
    "get_precipitation_sequence": "计算多种析出物在钢中的析出顺序。输入钢的成分（wt%），返回按析出温度从高到低排列的化合物列表。用于分析微合金钢中碳氮化物的析出行为。",
}

# 自定义工具元操作的Schema
TOOL_SCHEMAS["create_custom_tool"] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "技能名称（英文snake_case），如 calculate_ternary_mixing_enthalpy"
        },
        "description": {
            "type": "string",
            "description": "技能的中文描述，说明功能和使用场景"
        },
        "code": {
            "type": "string",
            "description": "Python函数代码。必须定义一个与name同名的函数，参数用type hints，返回dict。可用math/np/scipy_optimize。可用call_tool(tool_name, **kwargs)调用内置计算工具（如calculate_activity等），返回dict结果。"
        },
        "parameters": {
            "type": "object",
            "description": "JSON Schema格式的参数定义，与其他工具的schema格式一致"
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "标签，如 ['焓', '三元', 'Fe-Cr-Ni']"
        }
    },
    "required": ["name", "description", "code", "parameters"]
}

TOOL_SCHEMAS["list_custom_tools"] = {
    "type": "object",
    "properties": {},
    "required": []
}

TOOL_SCHEMAS["remove_custom_tool"] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "要删除的技能名称"
        }
    },
    "required": ["name"]
}

# ========== 技能库管理工具 ==========

TOOL_SCHEMAS["list_skill_libraries"] = {
    "type": "object",
    "properties": {},
    "required": []
}

TOOL_SCHEMAS["load_skill_library"] = {
    "type": "object",
    "properties": {
        "library_name": {
            "type": "string",
            "description": "技能库名称，如 'alloy_thermodynamics'"
        }
    },
    "required": ["library_name"]
}

TOOL_SCHEMAS["unload_skill_library"] = {
    "type": "object",
    "properties": {
        "library_name": {
            "type": "string",
            "description": "要卸载的技能库名称"
        }
    },
    "required": ["library_name"]
}

TOOL_DESCRIPTIONS["list_skill_libraries"] = "列出所有可用的技能库（包括内置库和用户自定义库），显示每个库的名称、描述、技能数量和加载状态。"
TOOL_DESCRIPTIONS["load_skill_library"] = "加载指定的技能库。加载后库中的技能将注册为可调用工具，AI可以直接使用。用户可以将自定义技能库JSON文件放在 ~/.alloyact/skill_libraries/ 目录下。"
TOOL_DESCRIPTIONS["unload_skill_library"] = "卸载指定的技能库，移除该库中所有已加载的技能。"


class ThermodynamicTools:
    """热力学计算工具集"""

    def __init__(self, memory_store=None, knowledge_store=None,
                 skill_registry=None, plugin_registry=None):
        self._thermo_calc = None
        self._precip_calc = None
        self._binary_model = None
        self._dft_calc = None
        self._solubility_calc = None
        self._memory_store = memory_store
        self._knowledge_store = knowledge_store
        self._skill_registry = skill_registry
        self._plugin_registry = plugin_registry

    @property
    def thermo_calc(self):
        if self._thermo_calc is None:
            from calculations.thermodynamic_properties import ThermodynamicProperties
            self._thermo_calc = ThermodynamicProperties()
        return self._thermo_calc

    @property
    def precip_calc(self):
        if self._precip_calc is None:
            from calculations.precipitation_temperature import PrecipitationTemperatureCalculator
            self._precip_calc = PrecipitationTemperatureCalculator()
        return self._precip_calc

    @property
    def binary_model(self):
        if self._binary_model is None:
            from models.extrapolation_models import BinaryModel
            self._binary_model = BinaryModel()
        return self._binary_model

    @property
    def dft_calc(self):
        """DFT 校准的热力学计算器（延迟初始化）"""
        if self._dft_calc is None:
            try:
                from calculations.dft_calibrated_properties import DFTCalibratedProperties
                self._dft_calc = DFTCalibratedProperties()
            except Exception:
                pass
        return self._dft_calc

    @property
    def solubility_calc(self):
        """化合物溶解度积计算器（延迟初始化）"""
        if self._solubility_calc is None:
            from calculations.compound_solubility import CompoundSolubilityCalculator
            self._solubility_calc = CompoundSolubilityCalculator()
        return self._solubility_calc

    def _parse_compound_input(self, compound_input: str) -> str:
        """解析用户输入的化合物名称或反应方程式"""
        import re
        s = compound_input.strip()
        # 如果是反应方程式: "TiN = [Ti] + [N]" 或 "TiN -> Ti + N"
        for sep in ('⇌', '⇋', '->', '→', '='):
            if sep in s:
                s = s.split(sep)[0].strip()
                break
        # 移除冶金学中常用的括号标记
        s = re.sub(r'[\[\]()]', '', s)
        return s.strip()

    def _get_extrapolation_func(self, model_name: str):
        """获取外推模型函数"""
        model_map = {
            "UEM1": self.binary_model.UEM1,
            "UEM2": self.binary_model.UEM2,
            "Muggianu": self.binary_model.Muggianu,
            "Toop_Muggianu": self.binary_model.Toop_Muggianu,
            "Toop_Kohler": self.binary_model.Toop_Kohler
        }
        return model_map.get(model_name, self.binary_model.UEM1)

    def _normalize_composition(self, composition: Dict[str, float]) -> Dict[str, float]:
        """归一化成分到摩尔分数（自动将字符串转为浮点数）"""
        # LLM有时会把数值传成字符串，这里统一转换
        composition = {k: float(v) for k, v in composition.items()}
        total = sum(composition.values())
        if total <= 0:
            return composition
        return {k: v / total for k, v in composition.items()}

    def calculate_liquidus_temperature(
        self,
        composition: Dict[str, float],
        extrapolation_model: str = "UEM1",
        activity_model: str = "Wagner"
    ) -> Dict[str, Any]:
        """计算液相线温度"""
        try:
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            result = self.thermo_calc.get_liquidus_temperature(
                composition=composition,
                extrapolation_model_func=extrap_func,
                extrapolation_model_name=extrapolation_model,
                activity_model=activity_model
            )
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_precipitation_temperature(
        self,
        composition: Dict[str, float],
        solute: str,
        solution_phase: str = "LIQUID",
        extrapolation_model: str = "UEM1",
        activity_model: str = "Wagner",
        T_min: float = 300,
        T_max: float = 3000
    ) -> Dict[str, Any]:
        """计算析出温度"""
        try:
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            result = self.precip_calc.calculate_precipitation_temperature(
                alloy_composition=composition,
                solute_element=solute,
                solution_phase=solution_phase,
                extrapolation_func=extrap_func,
                extrapolation_model_name=extrapolation_model,
                activity_model=activity_model,
                T_min=T_min,
                T_max=T_max
            )
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_activity(
        self,
        composition: Dict[str, float],
        component: str,
        temperature: float,
        phase: str = "liquid",
        extrapolation_model: str = "UEM1",
        activity_model: str = "Wagner"
    ) -> Dict[str, Any]:
        """计算活度"""
        try:
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            activity = self.thermo_calc.calculate_activity(
                composition=composition,
                component=component,
                temperature=temperature,
                phase_state=phase,
                extrapolation_model_func=extrap_func,
                extrapolation_model_name=extrapolation_model,
                activity_model=activity_model
            )
            return {
                "status": "success",
                "component": component,
                "temperature": temperature,
                "phase": phase,
                "activity": activity
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_activity_coefficient(
        self,
        composition: Dict[str, float],
        component: str,
        temperature: float,
        phase: str = "liquid",
        extrapolation_model: str = "UEM1",
        activity_model: str = "Wagner"
    ) -> Dict[str, Any]:
        """计算活度系数"""
        try:
            import math
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            ln_gamma = self.thermo_calc.calculate_ln_activity_coefficient(
                composition=composition,
                component=component,
                temperature=temperature,
                phase_state=phase,
                extrapolation_model_func=extrap_func,
                extrapolation_model_name=extrapolation_model,
                activity_model=activity_model
            )
            gamma = math.exp(ln_gamma) if ln_gamma is not None else None
            return {
                "status": "success",
                "component": component,
                "temperature": temperature,
                "phase": phase,
                "ln_gamma": ln_gamma,
                "gamma": gamma
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_mixing_enthalpy(
        self,
        composition: Dict[str, float],
        temperature: float,
        phase: str = "liquid",
        extrapolation_model: str = "UEM1"
    ) -> Dict[str, Any]:
        """计算混合焓"""
        try:
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            H = self.thermo_calc.calculate_molar_enthalpy(
                composition=composition,
                temperature=temperature,
                phase_state=phase,
                extrapolation_model_func=extrap_func,
                extrapolation_model_name=extrapolation_model
            )
            return {
                "status": "success",
                "temperature": temperature,
                "phase": phase,
                "molar_enthalpy": H,
                "unit": "J/mol"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_gibbs_energy(
        self,
        composition: Dict[str, float],
        temperature: float,
        phase: str = "liquid",
        extrapolation_model: str = "UEM1",
        activity_model: str = "Wagner"
    ) -> Dict[str, Any]:
        """计算Gibbs自由能"""
        try:
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            G = self.thermo_calc.calculate_gibbs_energy(
                composition=composition,
                temperature=temperature,
                phase_state=phase,
                extrapolation_model_func=extrap_func,
                extrapolation_model_name=extrapolation_model,
                activity_model=activity_model
            )
            return {
                "status": "success",
                "temperature": temperature,
                "phase": phase,
                "gibbs_energy": G,
                "unit": "J/mol"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_element_properties(self, element: str) -> Dict[str, Any]:
        """获取元素属性"""
        try:
            from core.element import Element
            elem = Element(element)
            if not elem.is_exist:
                return {"status": "error", "message": f"元素 {element} 不存在"}

            return {
                "status": "success",
                "element": element,
                "melting_point_K": elem.tm,
                "melting_point_C": elem.tm - 273.15 if elem.tm else None,
                "molar_volume": elem.v,  # v is the molar volume in Element class
                "electronegativity": elem.phi,
                "electron_density": elem.n_ws,  # n_ws is electron density
                "molar_mass": elem.m,  # m is molar mass
                "boiling_point_K": elem.tb
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_melting_point_depression(
        self,
        solvent: str,
        solute: str,
        solute_content_percent: float,
        content_type: str = "mole_percent"
    ) -> Dict[str, Any]:
        """计算熔点降低"""
        try:
            # 将百分比转换为摩尔分数
            x_solute = solute_content_percent / 100.0
            x_solvent = 1.0 - x_solute

            composition = {solvent: x_solvent, solute: x_solute}

            result = self.calculate_liquidus_temperature(composition)

            if result.get("status") == "success":
                depression = result.get("melting_point_depression", 0)
                return {
                    "status": "success",
                    "solvent": solvent,
                    "solute": solute,
                    "solute_content_percent": solute_content_percent,
                    "pure_melting_point_K": result.get("pure_melting_point"),
                    "liquidus_temperature_K": result.get("liquidus_temperature"),
                    "liquidus_temperature_C": result.get("liquidus_temperature_celsius"),
                    "melting_point_depression_K": depression,
                    "depression_per_percent": depression / solute_content_percent if solute_content_percent > 0 else 0
                }
            else:
                return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_interaction_coefficient(
        self,
        solvent: str,
        solute_i: str,
        solute_j: str,
        temperature: float,
        phase: str = "liquid",
        extrapolation_model: str = "UEM1"
    ) -> Dict[str, Any]:
        """计算一阶活度相互作用系数 ε_i^j"""
        try:
            from core.element import Element
            from models.activity_interaction_parameters import multicomponentSolution

            solv = Element(solvent)
            si = Element(solute_i)
            sj = Element(solute_j)

            if not solv.is_exist:
                return {"status": "error", "message": f"元素 {solvent} 不存在"}
            if not si.is_exist:
                return {"status": "error", "message": f"元素 {solute_i} 不存在"}
            if not sj.is_exist:
                return {"status": "error", "message": f"元素 {solute_j} 不存在"}

            extrap_func = self._get_extrapolation_func(extrapolation_model)
            system = multicomponentSolution(temperature, phase)
            epsilon = system.activity_interact_coefficient_1st(
                solv, si, sj, temperature, phase, extrap_func, extrapolation_model
            )

            return {
                "status": "success",
                "solvent": solvent,
                "solute_i": solute_i,
                "solute_j": solute_j,
                "temperature": temperature,
                "phase": phase,
                "epsilon_i_j": epsilon,
                "description": f"ε_{solute_i}^{solute_j} in {solvent}",
                "meaning": f"溶质{solute_j}对溶质{solute_i}活度系数的影响参数（无量纲，已除以RT）"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_second_order_interaction_coefficient(
        self,
        solvent: str,
        solute_i: str,
        solute_j: str,
        temperature: float,
        coefficient_type: str = "rho_ij",
        phase: str = "liquid",
        extrapolation_model: str = "UEM1"
    ) -> Dict[str, Any]:
        """计算二阶活度相互作用系数 ρ"""
        try:
            from core.element import Element
            from models.activity_interaction_parameters import multicomponentSolution

            solv = Element(solvent)
            si = Element(solute_i)
            sj = Element(solute_j)

            extrap_func = self._get_extrapolation_func(extrapolation_model)
            system = multicomponentSolution(temperature, phase)

            if coefficient_type == "rho_ii":
                rho = system.roui_ii(solv, si, temperature, phase, extrap_func, extrapolation_model)
                label = f"ρ_{solute_i}^{solute_i}{solute_i}"
            elif coefficient_type == "rho_jj":
                rho = system.roui_jj(solv, si, sj, temperature, phase, extrap_func, extrapolation_model)
                label = f"ρ_{solute_i}^{solute_j}{solute_j}"
            elif coefficient_type == "rho_ij":
                rho = system.roui_ij(solv, si, sj, temperature, phase, extrap_func, extrapolation_model)
                label = f"ρ_{solute_i}^{solute_i}{solute_j}"
            else:
                return {"status": "error", "message": f"未知系数类型: {coefficient_type}"}

            return {
                "status": "success",
                "solvent": solvent,
                "solute_i": solute_i,
                "solute_j": solute_j,
                "temperature": temperature,
                "phase": phase,
                "coefficient_type": coefficient_type,
                "rho": rho,
                "label": label
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_contribution_coefficients(
        self,
        solvent: str,
        solute_i: str,
        solute_j: str,
        temperature: float,
        phase: str = "liquid",
        extrapolation_model: str = "UEM1"
    ) -> Dict[str, Any]:
        """计算三元体系的6个贡献系数"""
        try:
            from core.element import Element

            solv = Element(solvent)
            si = Element(solute_i)
            sj = Element(solute_j)

            if not solv.is_exist:
                return {"status": "error", "message": f"元素 {solvent} 不存在"}
            if not si.is_exist:
                return {"status": "error", "message": f"元素 {solute_i} 不存在"}
            if not sj.is_exist:
                return {"status": "error", "message": f"元素 {solute_j} 不存在"}

            extrap_func = self._get_extrapolation_func(extrapolation_model)

            # 计算6个贡献系数（与 activity_interact_coefficient_1st 中一致）
            # k=溶剂, i=solute_i, j=solute_j
            aki_ij = extrap_func(solv.name, si.name, sj.name, temperature, phase)
            akj_ij = extrap_func(solv.name, sj.name, si.name, temperature, phase)
            aik_jk = extrap_func(si.name, solv.name, sj.name, temperature, phase)
            aij_jk = extrap_func(si.name, sj.name, solv.name, temperature, phase)
            aji_ik = extrap_func(sj.name, si.name, solv.name, temperature, phase)
            ajk_ik = extrap_func(sj.name, solv.name, si.name, temperature, phase)

            k, i, j = solvent, solute_i, solute_j
            return {
                "status": "success",
                "solvent": solvent,
                "solute_i": solute_i,
                "solute_j": solute_j,
                "temperature": temperature,
                "phase": phase,
                "extrapolation_model": extrapolation_model,
                "coefficients": {
                    f"a({k}:{i})_({i},{j})": round(aki_ij, 6),
                    f"a({k}:{j})_({i},{j})": round(akj_ij, 6),
                    f"a({i}:{k})_({j},{k})": round(aik_jk, 6),
                    f"a({i}:{j})_({j},{k})": round(aij_jk, 6),
                    f"a({j}:{i})_({i},{k})": round(aji_ik, 6),
                    f"a({j}:{k})_({i},{k})": round(ajk_ik, 6),
                },
                "description": (
                    f"三元{k}-{i}-{j}体系在{temperature}K下的贡献系数（{extrapolation_model}模型）"
                )
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_infinite_dilution_activity_coefficient(
        self,
        solvent: str,
        solute: str,
        temperature: float,
        phase: str = "liquid"
    ) -> Dict[str, Any]:
        """计算无限稀释活度系数 ln(γ°_i)"""
        try:
            import math
            from core.element import Element
            from models.activity_interaction_parameters import multicomponentSolution

            solv = Element(solvent)
            sol = Element(solute)

            if not solv.is_exist:
                return {"status": "error", "message": f"元素 {solvent} 不存在"}
            if not sol.is_exist:
                return {"status": "error", "message": f"元素 {solute} 不存在"}

            system = multicomponentSolution(temperature, phase)
            ln_gamma_0 = system.ln_y0(solv, sol)
            gamma_0 = math.exp(ln_gamma_0) if ln_gamma_0 is not None else None

            return {
                "status": "success",
                "solvent": solvent,
                "solute": solute,
                "temperature": temperature,
                "phase": phase,
                "ln_gamma_0": ln_gamma_0,
                "gamma_0": gamma_0,
                "description": f"ln(γ°_{solute}) in {solvent} at {temperature}K"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_chemical_potential(
        self,
        composition: Dict[str, float],
        component: str,
        temperature: float,
        phase: str = "liquid",
        extrapolation_model: str = "UEM1",
        activity_model: str = "Wagner"
    ) -> Dict[str, Any]:
        """计算化学势"""
        try:
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            mu = self.thermo_calc.calculate_chemical_potential(
                composition=composition,
                component=component,
                temperature=temperature,
                phase_state=phase,
                extrapolation_model_func=extrap_func,
                extrapolation_model_name=extrapolation_model,
                activity_model=activity_model
            )
            return {
                "status": "success",
                "component": component,
                "temperature": temperature,
                "phase": phase,
                "chemical_potential": mu,
                "unit": "J/mol"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_entropy(
        self,
        composition: Dict[str, float],
        temperature: float,
        phase: str = "liquid",
        extrapolation_model: str = "UEM1",
        activity_model: str = "Wagner"
    ) -> Dict[str, Any]:
        """计算摩尔熵"""
        try:
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            S = self.thermo_calc.calculate_entropy(
                composition=composition,
                temperature=temperature,
                phase_state=phase,
                extrapolation_model_func=extrap_func,
                extrapolation_model_name=extrapolation_model,
                activity_model=activity_model
            )
            return {
                "status": "success",
                "temperature": temperature,
                "phase": phase,
                "entropy": S,
                "unit": "J/(mol·K)"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_all_properties(
        self,
        composition: Dict[str, float],
        temperature: float,
        phase: str = "liquid",
        extrapolation_model: str = "UEM1",
        activity_model: str = "Wagner"
    ) -> Dict[str, Any]:
        """一次性计算所有热力学性质"""
        try:
            import math
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            results = self.thermo_calc.calculate_all_properties(
                composition=composition,
                temperature=temperature,
                phase_state=phase,
                extrapolation_model_func=extrap_func,
                extrapolation_model_name=extrapolation_model,
                activity_model=activity_model
            )
            # 整理输出格式
            output = {
                "status": "success",
                "temperature": temperature,
                "phase": phase,
                "components": {},
                "alloy": {}
            }
            for comp_name, props in results.get("component_properties", {}).items():
                output["components"][comp_name] = {
                    "mole_fraction": props.get("mole_fraction"),
                    "ln_gamma": props.get("ln_gamma"),
                    "gamma": props.get("gamma"),
                    "activity": props.get("activity"),
                    "chemical_potential_J_per_mol": props.get("mu")
                }
            alloy = results.get("alloy_properties", {})
            output["alloy"] = {
                "molar_enthalpy_J_per_mol": alloy.get("H"),
                "gibbs_energy_J_per_mol": alloy.get("G"),
                "entropy_J_per_mol_K": alloy.get("S")
            }
            return output
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def screen_elements_liquidus_effect(
        self,
        solvent: str,
        candidate_elements: List[str],
        addition_percent: float = 1.0,
        base_composition: Dict[str, float] = None,
        extrapolation_model: str = "UEM1",
        activity_model: str = "Wagner"
    ) -> Dict[str, Any]:
        """批量筛选元素对液相线温度的影响"""
        try:
            x_add = float(addition_percent) / 100.0
            if x_add <= 0 or x_add >= 1:
                return {"status": "error", "message": f"添加量 {addition_percent}% 无效，须在0-100之间"}

            # 确定基础成分
            if base_composition:
                base_comp = {k: float(v) for k, v in base_composition.items()}
            else:
                base_comp = {solvent: 1.0}

            # 归一化基础成分
            base_total = sum(base_comp.values())
            if base_total > 0:
                base_comp = {k: v / base_total for k, v in base_comp.items()}

            # 计算基础合金的液相线温度
            base_result = self.calculate_liquidus_temperature(
                composition=dict(base_comp),
                extrapolation_model=extrapolation_model,
                activity_model=activity_model
            )
            if base_result.get("status") == "error":
                return {"status": "error", "message": f"基础合金液相线计算失败: {base_result.get('message')}"}

            base_liquidus = base_result.get("liquidus_temperature")
            if base_liquidus is None:
                return {"status": "error", "message": "无法获取基础合金液相线温度"}

            # 遍历候选元素
            results = []
            errors = []
            for elem in candidate_elements:
                elem = elem.strip()
                if not elem:
                    continue

                # 构建添加该元素后的成分：按比例压缩原成分，腾出空间
                new_comp = {k: v * (1.0 - x_add) for k, v in base_comp.items()}
                # 如果元素已存在于基础成分中，则叠加
                new_comp[elem] = new_comp.get(elem, 0) + x_add

                try:
                    result = self.calculate_liquidus_temperature(
                        composition=new_comp,
                        extrapolation_model=extrapolation_model,
                        activity_model=activity_model
                    )
                    if result.get("status") == "error":
                        errors.append({"element": elem, "error": result.get("message", "未知错误")})
                        continue

                    new_liquidus = result.get("liquidus_temperature")
                    if new_liquidus is None:
                        errors.append({"element": elem, "error": "未能获取液相线温度"})
                        continue

                    delta_t = new_liquidus - base_liquidus
                    results.append({
                        "element": elem,
                        "liquidus_temperature_K": round(new_liquidus, 2),
                        "liquidus_temperature_C": round(new_liquidus - 273.15, 2),
                        "delta_T_K": round(delta_t, 2),
                    })
                except Exception as e:
                    errors.append({"element": elem, "error": str(e)})

            # 按 delta_T 排序（从最大降低到最小降低）
            results.sort(key=lambda r: r["delta_T_K"])

            # 找出影响最大和最小的
            summary = {}
            if results:
                summary["max_depression"] = {
                    "element": results[0]["element"],
                    "delta_T_K": results[0]["delta_T_K"]
                }
                summary["min_depression"] = {
                    "element": results[-1]["element"],
                    "delta_T_K": results[-1]["delta_T_K"]
                }

            base_desc = " + ".join(f"{k}:{v:.4g}" for k, v in base_comp.items())
            output = {
                "status": "success",
                "base_composition": base_desc,
                "base_liquidus_K": round(base_liquidus, 2),
                "base_liquidus_C": round(base_liquidus - 273.15, 2),
                "addition_percent": addition_percent,
                "element_count": len(results),
                "results": results,
                "summary": summary,
            }
            if errors:
                output["errors"] = errors
            return output
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def plot_chart(
        self,
        title: str,
        x_label: str,
        y_label: str,
        data_series: List[Dict[str, Any]],
        chart_type: str = "line"
    ) -> Dict[str, Any]:
        """绘制图表（返回图表数据，由UI层渲染）"""
        try:
            # 验证数据
            if not data_series:
                return {"status": "error", "message": "数据系列不能为空"}

            for i, series in enumerate(data_series):
                if "x_values" not in series or "y_values" not in series:
                    return {"status": "error", "message": f"数据系列 {i} 缺少 x_values 或 y_values"}
                if len(series["x_values"]) != len(series["y_values"]):
                    return {"status": "error", "message": f"数据系列 {i} 的 x_values 和 y_values 长度不一致"}

            return {
                "status": "success",
                "type": "chart",
                "chart_type": chart_type,
                "title": title,
                "x_label": x_label,
                "y_label": y_label,
                "data_series": data_series
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ============= 记忆工具 =============

    def save_memory(self, content: str, category: str = "general") -> Dict[str, Any]:
        """保存记忆"""
        if self._memory_store is None:
            return {"status": "error", "message": "记忆功能未启用"}
        msg = self._memory_store.add(content, category)
        return {"status": "success", "message": msg}

    def recall_memories(self, keyword: str = "") -> Dict[str, Any]:
        """回忆记忆"""
        if self._memory_store is None:
            return {"status": "error", "message": "记忆功能未启用"}
        if keyword:
            memories = self._memory_store.search(keyword)
        else:
            memories = self._memory_store.get_all()
        items = [{"content": m.content, "category": m.category} for m in memories]
        return {
            "status": "success",
            "count": len(items),
            "memories": items
        }

    def delete_memory(self, content: str) -> Dict[str, Any]:
        """删除记忆"""
        if self._memory_store is None:
            return {"status": "error", "message": "记忆功能未启用"}
        msg = self._memory_store.remove(content)
        return {"status": "success", "message": msg}

    # ==================== 知识学习工具 ====================

    def learn_knowledge(self, topic: str, content: str, category: str = "general",
                        confidence: float = 0.8, tags: str = "") -> Dict[str, Any]:
        """学习并保存领域知识"""
        if self._knowledge_store is None:
            return {"status": "error", "message": "知识学习功能未启用"}
        result = self._knowledge_store.add_knowledge(
            topic=topic, content=content, category=category,
            source="对话学习", confidence=confidence, tags=tags
        )
        return result

    def search_knowledge(self, keyword: str = "", category: str = "") -> Dict[str, Any]:
        """搜索已学习的知识"""
        if self._knowledge_store is None:
            return {"status": "error", "message": "知识学习功能未启用"}
        entries = self._knowledge_store.search_knowledge(keyword, category)
        items = []
        for e in entries:
            items.append({
                "id": e.id, "topic": e.topic, "content": e.content,
                "category": e.category, "confidence": e.confidence,
                "tags": e.tags
            })
            self._knowledge_store.increment_access(e.id)
        return {"status": "success", "count": len(items), "entries": items}

    def optimize_knowledge(self, similarity_threshold: float = 0.6) -> Dict[str, Any]:
        """优化知识库：查找相似条目并自动合并去重"""
        if self._knowledge_store is None:
            return {"status": "error", "message": "知识学习功能未启用"}

        all_entries = self._knowledge_store.get_all_knowledge()
        if len(all_entries) < 2:
            return {"status": "success", "message": "知识库条目不足，无需优化",
                    "merged_groups": 0, "total_merged": 0}

        # 查找相似组
        processed = set()
        merge_groups = []
        for i, entry in enumerate(all_entries):
            if entry.id in processed:
                continue
            similar = self._knowledge_store.find_similar_knowledge(
                entry.topic, entry.content, threshold=similarity_threshold
            )
            # 排除自身，只保留未处理的
            group_ids = [entry.id]
            group_entries = [entry]
            for sim_entry, sim_score in similar:
                if sim_entry.id != entry.id and sim_entry.id not in processed:
                    group_ids.append(sim_entry.id)
                    group_entries.append(sim_entry)
                    processed.add(sim_entry.id)
            if len(group_ids) > 1:
                processed.add(entry.id)
                merge_groups.append((group_ids, group_entries))

        if not merge_groups:
            return {"status": "success", "message": "未发现需要合并的相似知识",
                    "merged_groups": 0, "total_merged": 0}

        # 执行合并
        total_merged = 0
        for group_ids, group_entries in merge_groups:
            # 取置信度最高的条目作为基准
            best = max(group_entries, key=lambda e: (e.confidence, e.access_count))
            # 合并内容：取最长的
            longest = max(group_entries, key=lambda e: len(e.content))
            self._knowledge_store.merge_knowledge(
                source_ids=group_ids,
                merged_topic=best.topic,
                merged_content=longest.content,
                category=best.category,
                confidence=best.confidence
            )
            total_merged += len(group_ids)

        return {
            "status": "success",
            "message": f"知识库优化完成：合并了 {len(merge_groups)} 组共 {total_merged} 条知识",
            "merged_groups": len(merge_groups),
            "total_merged": total_merged
        }

    def update_experimental_value(self, data_type: str, solvent: str,
                                  solute_i: str, value: float,
                                  value_type: str, temperature: str,
                                  solute_j: str = "",
                                  reference: str = "用户提供") -> Dict[str, Any]:
        """保存或更新用户提供的实验数据"""
        if self._knowledge_store is None:
            return {"status": "error", "message": "知识学习功能未启用"}
        result = self._knowledge_store.add_user_data(
            data_type=data_type, solvent=solvent,
            solute_i=solute_i, solute_j=solute_j,
            value=value, value_type=value_type,
            temperature=temperature, reference=reference
        )
        return result

    def list_user_data(self, solvent: str = "",
                       data_type: str = "") -> Dict[str, Any]:
        """列出用户保存的实验数据"""
        if self._knowledge_store is None:
            return {"status": "error", "message": "知识学习功能未启用"}
        entries = self._knowledge_store.query_user_data(
            data_type=data_type, solvent=solvent
        )
        items = []
        for e in entries:
            items.append({
                "id": e.id, "data_type": e.data_type,
                "solvent": e.solvent, "solute_i": e.solute_i,
                "solute_j": e.solute_j, "value": e.value,
                "value_type": e.value_type, "temperature": e.temperature,
                "reference": e.reference
            })
        return {"status": "success", "count": len(items), "data": items}

    # ==================== 动态技能元操作 ====================

    def create_custom_tool(self, name: str, description: str, code: str,
                           parameters: Dict[str, Any],
                           tags: List[str] = None) -> Dict[str, Any]:
        """创建自定义计算工具"""
        if not self._skill_registry:
            return {"status": "error",
                    "message": "技能系统未初始化，无法创建自定义工具"}
        return self._skill_registry.create_skill(
            name=name, description=description, code=code,
            parameters=parameters, tags=tags
        )

    def list_custom_tools(self) -> Dict[str, Any]:
        """列出所有自定义工具"""
        if not self._skill_registry:
            return {"status": "success", "count": 0, "tools": []}
        skills = self._skill_registry.list_skills()
        return {"status": "success", "count": len(skills), "tools": skills}

    def remove_custom_tool(self, name: str) -> Dict[str, Any]:
        """删除自定义工具"""
        if not self._skill_registry:
            return {"status": "error", "message": "技能系统未初始化"}
        return self._skill_registry.remove_skill(name)

    # ==================== 技能库管理工具 ====================

    def list_skill_libraries(self) -> Dict[str, Any]:
        """列出所有可用的技能库"""
        if not self._skill_registry:
            return {"status": "success", "count": 0, "libraries": []}
        libraries = self._skill_registry.list_libraries()
        return {
            "status": "success",
            "count": len(libraries),
            "libraries": libraries,
        }

    def load_skill_library(self, library_name: str) -> Dict[str, Any]:
        """加载指定的技能库"""
        if not self._skill_registry:
            return {"status": "error", "message": "技能系统未初始化"}
        return self._skill_registry.load_library(library_name)

    def unload_skill_library(self, library_name: str) -> Dict[str, Any]:
        """卸载指定的技能库"""
        if not self._skill_registry:
            return {"status": "error", "message": "技能系统未初始化"}
        return self._skill_registry.unload_library(library_name)

    # ==================== DFT 校准工具 ====================

    def store_dft_compound_energy(self, compound_name: str,
                                  elements: list,
                                  stoichiometry: list,
                                  formation_energy_J: float,
                                  delta_G_A: float = 0,
                                  delta_G_B: float = 0,
                                  source: str = "dft",
                                  dft_engine: str = "",
                                  reference: str = "") -> Dict[str, Any]:
        """存储化合物形成能到 DFT 数据库"""
        if not self.dft_calc:
            return {"status": "error", "message": "DFT 校准模块未就绪"}
        try:
            from core.dft_data_store import CompoundEnergy
            data = CompoundEnergy(
                compound_name=compound_name,
                elements=tuple(elements),
                stoichiometry=tuple(stoichiometry),
                formation_energy_J=formation_energy_J,
                delta_G_A=delta_G_A if delta_G_A else formation_energy_J,
                delta_G_B=delta_G_B,
                source=source,
                dft_engine=dft_engine,
                reference=reference,
            )
            self.dft_calc.dft_store.store_compound_energy(data)
            return {
                "status": "success",
                "message": f"已存储 {compound_name} 的形成能: "
                           f"{formation_energy_J:.0f} J/mol "
                           f"({formation_energy_J/1000:.1f} kJ/mol)",
                "compound": compound_name,
                "formation_energy_J": formation_energy_J,
                "formation_energy_kJ": formation_energy_J / 1000,
                "delta_G": f"ΔG(T) = {delta_G_A or formation_energy_J:.0f} "
                           f"+ {delta_G_B:.1f}*T (J/mol)",
                "source": source,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_liquidus_dft_calibrated(self, composition: Dict[str, float],
                                          extrapolation_model: str = "UEM1",
                                          activity_model: str = "Wagner") -> Dict[str, Any]:
        """DFT 校准的液相线温度计算"""
        if not self.dft_calc:
            return {"status": "error", "message": "DFT 校准模块未就绪"}
        try:
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            result = self.dft_calc.calculate_liquidus_temperature_calibrated(
                composition=composition,
                extrapolation_model_func=extrap_func,
                extrapolation_model_name=extrapolation_model,
                activity_model=activity_model,
            )
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_precipitation_dft_calibrated(self, composition: Dict[str, float],
                                                phase_type: str,
                                                solution_phase: str = "LIQUID",
                                                extrapolation_model: str = "UEM1",
                                                activity_model: str = "Wagner") -> Dict[str, Any]:
        """DFT 校准的析出温度计算"""
        if not self.dft_calc:
            return {"status": "error", "message": "DFT 校准模块未就绪"}
        try:
            extrap_func = self._get_extrapolation_func(extrapolation_model)
            result = self.dft_calc.calculate_precipitation_temperature_calibrated(
                alloy_composition=composition,
                phase_type=phase_type,
                solution_phase=solution_phase,
                extrapolation_model_func=extrap_func,
                extrapolation_model_name=extrapolation_model,
                activity_model=activity_model,
            )
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def compare_mixing_enthalpy(self, element_a: str, element_b: str,
                                temperature: float = 1800,
                                phase: str = "liquid") -> Dict[str, Any]:
        """对比 Miedema 和 DFT 混合焓"""
        if not self.dft_calc:
            return {"status": "error", "message": "DFT 校准模块未就绪"}
        try:
            result = self.dft_calc.compare_mixing_enthalpy(
                element_a=element_a,
                element_b=element_b,
                temperature_K=temperature,
                phase=phase,
            )
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_dft_data_summary(self, element_filter: str = "") -> Dict[str, Any]:
        """获取 DFT 数据库摘要"""
        if not self.dft_calc:
            return {"status": "error", "message": "DFT 校准模块未就绪"}
        try:
            result = self.dft_calc.get_dft_data_summary()
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def import_dft_result(self, compound_name: str,
                          elements: list,
                          stoichiometry: list,
                          reference_energies: Dict[str, float],
                          task_id: str = "") -> Dict[str, Any]:
        """从 DFT 计算结果导入形成能"""
        if not self.dft_calc:
            return {"status": "error", "message": "DFT 校准模块未就绪"}

        # 如果有 task_id，从任务队列获取结果
        dft_result = None
        if task_id and self._plugin_registry:
            try:
                plugin = self._plugin_registry.get_plugin("dft")
                if plugin:
                    mgr = plugin._get_job_manager()
                    if mgr:
                        dft_result = mgr.get_results(task_id)
            except Exception:
                pass

        if dft_result and dft_result.get("status") == "success":
            result = self.dft_calc.dft_store.import_from_dft_result(
                dft_result=dft_result,
                compound_name=compound_name,
                elements=tuple(elements),
                stoichiometry=tuple(stoichiometry),
                reference_energies=reference_energies,
            )
        else:
            result = {
                "status": "error",
                "message": f"无法获取 DFT 结果。请手动使用 store_dft_compound_energy 存储数据，"
                           f"或确保 task_id '{task_id}' 对应的计算已完成",
            }
        return result

    # ========== 溶解度积计算工具方法 ==========

    def calculate_solubility_product(
        self,
        compound: str,
        temperature: float,
        phase: str = "AUSTENITE",
        method: str = "empirical"
    ) -> Dict[str, Any]:
        """计算化合物溶解度积"""
        try:
            import math
            compound = self._parse_compound_input(compound)

            from database.solubility_product_database import (
                calculate_log_solubility_product,
                get_solubility_product_data
            )

            results = {}

            if method in ("empirical", "both"):
                log_ksp = calculate_log_solubility_product(compound, phase, temperature)
                sp_data = get_solubility_product_data(compound, phase)
                if log_ksp is not None and sp_data is not None:
                    n = sp_data.get('n', 1.0)
                    results["empirical"] = {
                        "log_Ksp": round(log_ksp, 4),
                        "Ksp": 10 ** log_ksp,
                        "A": sp_data["A"],
                        "B": sp_data["B"],
                        "n": n,
                        "metal": sp_data["metal"],
                        "nonmetal": sp_data["nonmetal"],
                        "expression": f"log[%{sp_data['metal']}][%{sp_data['nonmetal']}]^{n} = {sp_data['A']} - {sp_data['B']}/T",
                        "reference": sp_data.get("reference", ""),
                        "T_min": sp_data.get("T_min"),
                        "T_max": sp_data.get("T_max"),
                    }
                elif method == "empirical":
                    return {"status": "error", "message": f"化合物 {compound} 在 {phase} 相中无经验溶解度积数据"}

            if method in ("thermodynamic", "both"):
                thermo_result = self.solubility_calc.calculate_solubility_product_ideal(
                    compound, temperature, phase
                )
                if thermo_result.get("status") == "success":
                    results["thermodynamic"] = thermo_result
                elif method == "thermodynamic":
                    return thermo_result

            if not results:
                return {"status": "error", "message": f"化合物 {compound} 在 {phase} 相中无可用数据"}

            response = {
                "status": "success",
                "compound": compound,
                "temperature": temperature,
                "temperature_celsius": round(temperature - 273.15, 2),
                "phase": phase,
                "method": method,
            }

            if "empirical" in results:
                emp = results["empirical"]
                response["log_Ksp"] = emp["log_Ksp"]
                response["Ksp"] = emp["Ksp"]
                response["expression"] = emp["expression"]
                response["reference"] = emp["reference"]
                response["metal"] = emp["metal"]
                response["nonmetal"] = emp["nonmetal"]
                response["A"] = emp["A"]
                response["B"] = emp["B"]
                response["n"] = emp["n"]
                if emp.get("T_min") and emp.get("T_max"):
                    response["valid_range"] = f"{emp['T_min']}-{emp['T_max']} K"

            if "thermodynamic" in results:
                thermo = results["thermodynamic"]
                prefix = "thermo_" if "empirical" in results else ""
                response[f"{prefix}log_Ksp"] = round(thermo.get("log_Ksp", 0), 4)
                response[f"{prefix}Ksp"] = thermo.get("Ksp_ideal")
                response[f"{prefix}delta_G_dissolution"] = round(thermo.get("delta_G_dissolution", 0), 1)

            return response
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_precipitation_temperature_sp(
        self,
        compound: str,
        metal_content: float,
        nonmetal_content: float,
        phase: str = "AUSTENITE"
    ) -> Dict[str, Any]:
        """根据溶解度积计算析出温度"""
        try:
            compound = self._parse_compound_input(compound)

            from database.solubility_product_database import (
                calculate_precipitation_temperature_from_product,
                get_solubility_product_data
            )

            sp_data = get_solubility_product_data(compound, phase)
            if sp_data is None:
                return {"status": "error", "message": f"化合物 {compound} 在 {phase} 相中无溶解度积数据"}

            T_precip = calculate_precipitation_temperature_from_product(
                compound, phase, metal_content, nonmetal_content
            )

            if T_precip is None:
                return {
                    "status": "error",
                    "message": f"在给定含量下 {compound} 不会析出（溶解度积过大或含量为零）"
                }

            n = sp_data.get('n', 1.0)
            return {
                "status": "success",
                "compound": compound,
                "metal": sp_data["metal"],
                "nonmetal": sp_data["nonmetal"],
                "metal_content_wt_pct": metal_content,
                "nonmetal_content_wt_pct": nonmetal_content,
                "precipitation_temperature_K": round(T_precip, 1),
                "precipitation_temperature_C": round(T_precip - 273.15, 1),
                "phase": phase,
                "expression": f"log[%{sp_data['metal']}][%{sp_data['nonmetal']}]^{n} = {sp_data['A']} - {sp_data['B']}/T",
                "reference": sp_data.get("reference", ""),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_equilibrium_solubility(
        self,
        compound: str,
        temperature: float,
        fixed_element: str,
        fixed_content: float,
        phase: str = "AUSTENITE"
    ) -> Dict[str, Any]:
        """计算平衡溶解度"""
        try:
            compound = self._parse_compound_input(compound)

            from database.solubility_product_database import (
                calculate_equilibrium_content,
                get_solubility_product_data
            )

            sp_data = get_solubility_product_data(compound, phase)
            if sp_data is None:
                return {"status": "error", "message": f"化合物 {compound} 在 {phase} 相中无溶解度积数据"}

            # 智能解析 fixed_element: 元素符号→metal/nonmetal角色
            fe_upper = fixed_element.upper()
            if fe_upper in ("METAL", "NONMETAL"):
                role = fe_upper.lower()
            elif fe_upper == sp_data["metal"]:
                role = "metal"
            elif fe_upper == sp_data["nonmetal"]:
                role = "nonmetal"
            else:
                return {
                    "status": "error",
                    "message": f"元素 {fixed_element} 不是 {compound} 的组成元素（{sp_data['metal']}/{sp_data['nonmetal']}）"
                }

            eq_content = calculate_equilibrium_content(
                compound, phase, temperature, role, fixed_content
            )

            if eq_content is None:
                return {"status": "error", "message": f"无法计算 {compound} 在 {temperature}K 下的平衡含量"}

            # 确定平衡元素
            if role == "metal":
                eq_element = sp_data["nonmetal"]
                fixed_el_name = sp_data["metal"]
            else:
                eq_element = sp_data["metal"]
                fixed_el_name = sp_data["nonmetal"]

            return {
                "status": "success",
                "compound": compound,
                "temperature": temperature,
                "temperature_celsius": round(temperature - 273.15, 2),
                "phase": phase,
                "fixed_element": fixed_el_name,
                "fixed_content_wt_pct": fixed_content,
                "equilibrium_element": eq_element,
                "equilibrium_content_wt_pct": round(eq_content, 6),
                "equilibrium_content_ppm": round(eq_content * 10000, 2),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_precipitation_sequence(
        self,
        composition: Dict[str, float],
        phase: str = "AUSTENITE"
    ) -> Dict[str, Any]:
        """计算析出顺序"""
        try:
            from database.solubility_product_database import (
                get_precipitation_sequence as _get_precip_seq
            )

            # 键名转大写以匹配数据库
            comp_upper = {k.upper(): float(v) for k, v in composition.items()}

            sequence = _get_precip_seq(comp_upper, phase)

            if not sequence:
                return {
                    "status": "error",
                    "message": f"在给定成分下，{phase} 相中没有可析出的化合物"
                }

            result_sequence = []
            for compound, T_precip in sequence:
                result_sequence.append({
                    "compound": compound,
                    "precipitation_temperature_K": round(T_precip, 1),
                    "precipitation_temperature_C": round(T_precip - 273.15, 1),
                })

            return {
                "status": "success",
                "phase": phase,
                "composition_wt_pct": composition,
                "sequence": result_sequence,
                "count": len(result_sequence),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_all_tool_methods(self) -> Dict[str, Any]:
        """获取所有工具方法映射（含插件工具）"""
        methods = {
            "calculate_liquidus_temperature": self.calculate_liquidus_temperature,
            "calculate_precipitation_temperature": self.calculate_precipitation_temperature,
            "calculate_activity": self.calculate_activity,
            "calculate_activity_coefficient": self.calculate_activity_coefficient,
            "calculate_mixing_enthalpy": self.calculate_mixing_enthalpy,
            "calculate_gibbs_energy": self.calculate_gibbs_energy,
            "get_element_properties": self.get_element_properties,
            "calculate_melting_point_depression": self.calculate_melting_point_depression,
            "get_interaction_coefficient": self.get_interaction_coefficient,
            "get_second_order_interaction_coefficient": self.get_second_order_interaction_coefficient,
            "get_contribution_coefficients": self.get_contribution_coefficients,
            "get_infinite_dilution_activity_coefficient": self.get_infinite_dilution_activity_coefficient,
            "calculate_chemical_potential": self.calculate_chemical_potential,
            "calculate_entropy": self.calculate_entropy,
            "calculate_all_properties": self.calculate_all_properties,
            "screen_elements_liquidus_effect": self.screen_elements_liquidus_effect,
            "plot_chart": self.plot_chart,
            "save_memory": self.save_memory,
            "recall_memories": self.recall_memories,
            "delete_memory": self.delete_memory,
            "learn_knowledge": self.learn_knowledge,
            "search_knowledge": self.search_knowledge,
            "optimize_knowledge": self.optimize_knowledge,
            "update_experimental_value": self.update_experimental_value,
            "list_user_data": self.list_user_data,
            "create_custom_tool": self.create_custom_tool,
            "list_custom_tools": self.list_custom_tools,
            "remove_custom_tool": self.remove_custom_tool,
            "list_skill_libraries": self.list_skill_libraries,
            "load_skill_library": self.load_skill_library,
            "unload_skill_library": self.unload_skill_library,
            "store_dft_compound_energy": self.store_dft_compound_energy,
            "calculate_liquidus_dft_calibrated": self.calculate_liquidus_dft_calibrated,
            "calculate_precipitation_dft_calibrated": self.calculate_precipitation_dft_calibrated,
            "compare_mixing_enthalpy": self.compare_mixing_enthalpy,
            "get_dft_data_summary": self.get_dft_data_summary,
            "import_dft_result": self.import_dft_result,
            "calculate_solubility_product": self.calculate_solubility_product,
            "calculate_precipitation_temperature_sp": self.calculate_precipitation_temperature_sp,
            "calculate_equilibrium_solubility": self.calculate_equilibrium_solubility,
            "get_precipitation_sequence": self.get_precipitation_sequence,
        }
        # 合并扩展插件工具
        if self._plugin_registry:
            try:
                plugin_methods = self._plugin_registry.get_tool_methods()
                methods.update(plugin_methods)
            except Exception:
                pass  # 插件加载失败不影响内置工具
        return methods

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """获取所有工具定义（含插件工具）"""
        tool_methods = self._get_all_tool_methods()

        # 合并插件的 schema 和描述到查找表
        all_schemas = dict(TOOL_SCHEMAS)
        all_descs = dict(TOOL_DESCRIPTIONS)
        if self._plugin_registry:
            try:
                all_schemas.update(self._plugin_registry.get_all_tool_schemas())
                all_descs.update(self._plugin_registry.get_all_tool_descriptions())
            except Exception:
                pass

        tools = []
        for name, func in tool_methods.items():
            tools.append(ToolDefinition(
                name=name,
                description=all_descs.get(name, ""),
                parameters=all_schemas.get(name, {}),
                function=func
            ))
        return tools

    @staticmethod
    def _coerce_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """修正LLM传参中的常见类型错误（如字符串数字、字符串字典）"""
        args = dict(arguments)

        # composition: 值可能是字符串，统一转float
        if "composition" in args and isinstance(args["composition"], dict):
            args["composition"] = {
                k: float(v) if isinstance(v, str) else v
                for k, v in args["composition"].items()
            }

        # temperature: 可能传成字符串
        if "temperature" in args and isinstance(args["temperature"], str):
            try:
                args["temperature"] = float(args["temperature"])
            except ValueError:
                pass

        # solute_content_percent: 可能传成字符串
        if "solute_content_percent" in args and isinstance(args["solute_content_percent"], str):
            try:
                args["solute_content_percent"] = float(args["solute_content_percent"])
            except ValueError:
                pass

        # addition_percent: 可能传成字符串
        if "addition_percent" in args and isinstance(args["addition_percent"], str):
            try:
                args["addition_percent"] = float(args["addition_percent"])
            except ValueError:
                pass

        # candidate_elements: 可能传成逗号分隔的字符串
        if "candidate_elements" in args and isinstance(args["candidate_elements"], str):
            args["candidate_elements"] = [e.strip() for e in args["candidate_elements"].split(",") if e.strip()]

        # value: 可能传成字符串
        if "value" in args and isinstance(args["value"], str):
            try:
                args["value"] = float(args["value"])
            except ValueError:
                pass

        # confidence: 可能传成字符串
        if "confidence" in args and isinstance(args["confidence"], str):
            try:
                args["confidence"] = float(args["confidence"])
            except ValueError:
                pass

        # parameters: create_custom_tool 的参数定义可能被LLM序列化为字符串
        if "parameters" in args and isinstance(args["parameters"], str):
            try:
                args["parameters"] = json.loads(args["parameters"])
            except (json.JSONDecodeError, ValueError):
                pass

        # tags: 可能传成逗号分隔的字符串
        if "tags" in args and isinstance(args["tags"], str):
            args["tags"] = [t.strip() for t in args["tags"].split(",") if t.strip()]

        # 溶解度积工具参数修正
        for key in ("metal_content", "nonmetal_content", "fixed_content"):
            if key in args and isinstance(args[key], str):
                try:
                    args[key] = float(args[key])
                except ValueError:
                    pass

        # phase: 中文别名→标准名
        if "phase" in args and isinstance(args["phase"], str):
            phase_map = {
                "austenite": "AUSTENITE", "gamma": "AUSTENITE", "fcc": "AUSTENITE",
                "ferrite": "FERRITE", "alpha": "FERRITE", "bcc": "FERRITE",
                "liquid": "LIQUID", "melt": "LIQUID",
                "奥氏体": "AUSTENITE", "铁素体": "FERRITE", "液相": "LIQUID",
            }
            args["phase"] = phase_map.get(args["phase"].lower(), args["phase"].upper())

        # method: 统一小写
        if "method" in args and isinstance(args["method"], str):
            args["method"] = args["method"].lower()

        return args

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """执行工具调用"""
        tool_methods = self._get_all_tool_methods()

        if tool_name not in tool_methods:
            return json.dumps({"status": "error", "message": f"未知工具: {tool_name}"})

        # 自动修正LLM常见的类型错误
        arguments = self._coerce_arguments(arguments)

        try:
            result = tool_methods[tool_name](**arguments)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except TypeError as e:
            # 参数缺失或类型错误 — 给出清晰的中文提示
            import inspect
            sig = inspect.signature(tool_methods[tool_name])
            required = [
                p.name for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty and p.name != "self"
            ]
            provided = list(arguments.keys())
            missing = [r for r in required if r not in provided]
            if missing:
                msg = f"缺少必需参数: {', '.join(missing)}。此工具需要: {', '.join(required)}"
            else:
                msg = f"参数类型错误: {str(e)}"
            return json.dumps({"status": "error", "message": msg})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})


# ============= 测试代码 =============

if __name__ == "__main__":
    print("=== 热力学工具测试 ===\n")

    tools = ThermodynamicTools()

    # 测试1: 元素属性
    print("1. 获取Fe元素属性:")
    result = tools.get_element_properties("Fe")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 测试2: 液相线温度
    print("\n2. 计算Al-5%Cu液相线温度:")
    result = tools.calculate_liquidus_temperature({"Al": 0.95, "Cu": 0.05})
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 测试3: 熔点降低
    print("\n3. 计算每1%Cu对Al熔点的降低:")
    result = tools.calculate_melting_point_depression("Al", "Cu", 1.0)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\n=== 测试完成 ===")
