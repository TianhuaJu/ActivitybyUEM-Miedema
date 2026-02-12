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
    "calculate_melting_point_depression": "计算指定溶质含量对溶剂熔点的降低值。"
}


class ThermodynamicTools:
    """热力学计算工具集"""

    def __init__(self):
        self._thermo_calc = None
        self._precip_calc = None
        self._binary_model = None

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
        """归一化成分到摩尔分数"""
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

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """获取所有工具定义"""
        tool_methods = {
            "calculate_liquidus_temperature": self.calculate_liquidus_temperature,
            "calculate_precipitation_temperature": self.calculate_precipitation_temperature,
            "calculate_activity": self.calculate_activity,
            "calculate_activity_coefficient": self.calculate_activity_coefficient,
            "calculate_mixing_enthalpy": self.calculate_mixing_enthalpy,
            "calculate_gibbs_energy": self.calculate_gibbs_energy,
            "get_element_properties": self.get_element_properties,
            "calculate_melting_point_depression": self.calculate_melting_point_depression
        }

        tools = []
        for name, func in tool_methods.items():
            tools.append(ToolDefinition(
                name=name,
                description=TOOL_DESCRIPTIONS.get(name, ""),
                parameters=TOOL_SCHEMAS.get(name, {}),
                function=func
            ))
        return tools

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """执行工具调用"""
        tool_methods = {
            "calculate_liquidus_temperature": self.calculate_liquidus_temperature,
            "calculate_precipitation_temperature": self.calculate_precipitation_temperature,
            "calculate_activity": self.calculate_activity,
            "calculate_activity_coefficient": self.calculate_activity_coefficient,
            "calculate_mixing_enthalpy": self.calculate_mixing_enthalpy,
            "calculate_gibbs_energy": self.calculate_gibbs_energy,
            "get_element_properties": self.get_element_properties,
            "calculate_melting_point_depression": self.calculate_melting_point_depression
        }

        if tool_name not in tool_methods:
            return json.dumps({"status": "error", "message": f"未知工具: {tool_name}"})

        try:
            result = tool_methods[tool_name](**arguments)
            return json.dumps(result, ensure_ascii=False, indent=2)
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
