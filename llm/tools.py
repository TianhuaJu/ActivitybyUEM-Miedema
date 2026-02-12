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
    }
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
    "get_infinite_dilution_activity_coefficient": "计算无限稀释活度系数 ln(γ°_i)。即溶质i在溶剂中浓度趋于0时的活度系数对数。基于Miedema模型计算化学相互作用能。",
    "calculate_chemical_potential": "计算合金中指定组元的化学势 μ_i = μ°_i(T) + RT·ln(a_i)。其中μ°_i(T)从SGTE热力学数据库获取，a_i由活度计算给出。",
    "calculate_entropy": "计算合金的摩尔熵 S = (H - G) / T。其中H为摩尔焓，G为摩尔Gibbs自由能。",
    "calculate_all_properties": "一次性计算合金的所有热力学性质。包括每个组元的活度系数γ、活度a、化学势μ，以及合金整体的摩尔焓H、Gibbs自由能G、摩尔熵S。",
    "save_memory": "保存一条重要信息到长期记忆。当用户提到偏好、常用合金体系、计算习惯等值得记住的信息时，主动调用此工具保存。分类: preference(偏好)、alloy_system(合金体系)、calculation(计算经验)、general(其他)。",
    "recall_memories": "回忆已保存的记忆。可按关键词搜索，不填关键词则返回所有记忆。当用户问'你还记得吗'、'之前说过'等时调用。",
    "delete_memory": "删除一条已保存的记忆。当用户要求忘记某信息时调用。"
}


class ThermodynamicTools:
    """热力学计算工具集"""

    def __init__(self, memory_store=None):
        self._thermo_calc = None
        self._precip_calc = None
        self._binary_model = None
        self._memory_store = memory_store

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

    def _get_all_tool_methods(self) -> Dict[str, Any]:
        """获取所有工具方法映射"""
        return {
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
            "get_infinite_dilution_activity_coefficient": self.get_infinite_dilution_activity_coefficient,
            "calculate_chemical_potential": self.calculate_chemical_potential,
            "calculate_entropy": self.calculate_entropy,
            "calculate_all_properties": self.calculate_all_properties,
            "plot_chart": self.plot_chart,
            "save_memory": self.save_memory,
            "recall_memories": self.recall_memories,
            "delete_memory": self.delete_memory,
        }

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """获取所有工具定义"""
        tool_methods = self._get_all_tool_methods()

        tools = []
        for name, func in tool_methods.items():
            tools.append(ToolDefinition(
                name=name,
                description=TOOL_DESCRIPTIONS.get(name, ""),
                parameters=TOOL_SCHEMAS.get(name, {}),
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
