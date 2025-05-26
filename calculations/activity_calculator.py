# activity_calculator.py

import re
import math
from core.element import Element
from models.activity_interaction_parameters import TernaryMelts
from typing import Callable, Dict

extrap_func = Callable[[str, str, str, float, str], float]

class ActivityCoefficient:
    """提供计算活度和活度系数的高级接口。"""
    def __init__(self):
        self._comp_dict: Dict[str, float] = {}

    def set_composition_dict(self, text: str):
        """设置体系的初始成分 (例如 AxByCz)。"""
        self._comp_dict = {} # Reset before setting
        pattern = r"([A-Z][a-z]?)(\d*\.?\d*)?"
        matches = re.finditer(pattern, text)

        for match in matches:
            element = match.group(1)
            value_str = match.group(2)
            try:
                x = float(value_str) if value_str else 1.0
            except ValueError:
                x = 1.0 # Default to 1 if conversion fails

            self._comp_dict[element] = self._comp_dict.get(element, 0.0) + x
        self._standardize_composition()

    def _standardize_composition(self):
        """将成分字典标准化为摩尔分数。"""
        total = sum(self._comp_dict.values())
        if total > 0 and len(self._comp_dict) > 1:
            self._comp_dict = {key: value / total for key, value in self._comp_dict.items()}

    @property
    def melts_dict(self) -> Dict[str, float]:
        """返回标准化的摩尔成分字典。"""
        return self._comp_dict

    def _calculate_ln_yi(self, comp_dict, solvent, solute_i, Tem: float, state: str,
                         geo_model: extrap_func, geo_model_name: str, model_type: str) -> float:
        """内部通用计算方法。"""
        if solute_i not in comp_dict or solvent not in comp_dict:
            print(f"警告: 组分 {solute_i} 或溶剂 {solvent} 不在成分中。")
            return 0.0

        solv = Element(solvent)
        solui = Element(solute_i)
        ternary_melts = TernaryMelts(Tem, state)
        ln_yi_0 = ternary_melts.ln_y0(solv, solui)

        linear_sum = 0.0
        for j_name, xj in comp_dict.items():
            if j_name != solvent:
                epsilon_i_j = ternary_melts.activity_interact_coefficient_1st(
                    solv, solui, Element(j_name), Tem, state, geo_model, geo_model_name)
                linear_sum += epsilon_i_j * xj

        if model_type == "Wagner":
            return ln_yi_0 + linear_sum

        quadratic_sum_darken = 0.0
        solute_keys = [k for k in comp_dict.keys() if k != solvent]
        for j_name in solute_keys:
            xj = comp_dict[j_name]
            for k_name in solute_keys:
                xk = comp_dict[k_name]
                epsilon_j_k = ternary_melts.activity_interact_coefficient_1st(
                    solv, Element(j_name), Element(k_name), Tem, state, geo_model, geo_model_name)
                quadratic_sum_darken += xj * xk * epsilon_j_k

        if model_type == "Darken":
            return ln_yi_0 + linear_sum - 0.5 * quadratic_sum_darken

        quadratic_sum_elliot = 0.0
        for j_name in solute_keys:
            xj = comp_dict[j_name]
            soluj = Element(j_name)
            for k_name in solute_keys:
                xk = comp_dict[k_name]
                soluk = Element(k_name)
                rho_i_jk = ternary_melts.roui_jk(solv, solui, soluj, soluk, Tem, state, geo_model, geo_model_name)
                quadratic_sum_elliot += 0.5 * rho_i_jk * xj * xk

        if model_type == "Elliot":
            return ln_yi_0 + linear_sum + quadratic_sum_elliot

        return 0.0 # Should not happen

    def activity_coefficient_wagner(self, comp_dict, solvent, solute_i, Tem: float, state: str, geo_model: extrap_func,
                                     geo_model_name):
        return self._calculate_ln_yi(comp_dict, solvent, solute_i, Tem, state, geo_model, geo_model_name, "Wagner")

    def activity_coefficient_darken(self, comp_dict, solute_i, matrix, Tem: float, phase_state: str,
                                     geo_model: extrap_func, geo_model_name):
        return self._calculate_ln_yi(comp_dict, matrix, solute_i, Tem, phase_state, geo_model, geo_model_name, "Darken")

    def activity_coefficient_elloit(self, comp_dict, solute_i, matrix, Tem, phase_state: str, geo_model: extrap_func,
                                     geo_model_name):
        return self._calculate_ln_yi(comp_dict, matrix, solute_i, Tem, phase_state, geo_model, geo_model_name, "Elliot")