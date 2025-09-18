# activity_calculator.py

import re
from copy import deepcopy
from typing import Callable, Dict

from core.element import Element
from models.activity_interaction_parameters import TernaryMelts

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
                         geo_model: extrap_func, geo_model_name: str, activity_model_type: str, full_alloy_str: str = "") -> float:
        """内部通用计算方法。"""
        if solute_i not in comp_dict or solvent not in comp_dict:
            print(f"警告: 组分 {solute_i} 或溶剂 {solvent} 不在成分中。")
            return 0.0

        solv = Element(solvent)
        solui = Element(solute_i)
        solute_keys = [k for k in comp_dict.keys() if k != solvent]
        
        ternary_melts = TernaryMelts(Tem, state)
        ln_yi_0 = ternary_melts.ln_y0(solv, solui)

        linear_sum = 0.0
        for j_name in solute_keys:
            xj = comp_dict[j_name]
            epsilon_i_j = ternary_melts.activity_interact_coefficient_1st(solv, solui, Element(j_name), Tem, state,
                                                                          geo_model, geo_model_name, full_alloy_str)
            linear_sum += epsilon_i_j * xj

        if activity_model_type == "Wagner" or activity_model_type == "wagner":
            return ln_yi_0 + linear_sum

        quadratic_sum_darken = 0.0
        for j_name in solute_keys:
            xj = comp_dict[j_name]
            for k_name in solute_keys:
                xk = comp_dict[k_name]
                epsilon_j_k = ternary_melts.activity_interact_coefficient_1st(solv, Element(j_name), Element(k_name),
                                                                              Tem, state, geo_model, geo_model_name,
                                                                              full_alloy_str)
                quadratic_sum_darken += xj * xk * epsilon_j_k

        if activity_model_type == "Darken" or activity_model_type == "darken":
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
               

        if activity_model_type == "Elliott" or activity_model_type == "elliott":
            return ln_yi_0 + linear_sum + quadratic_sum_elliot
            
        
        corrected_term_sum = 0
        for j_name in solute_keys:
            xj = comp_dict[j_name]
            soluj = Element(j_name)
            for k_name in solute_keys:
                xk = comp_dict[k_name]
                soluk = Element(k_name)
                for p_name in solute_keys:
                    xp = comp_dict[p_name]
                    solup = Element(p_name)
                    epislon_j_k = ternary_melts.activity_interact_coefficient_1st(solv, Element(j_name),
                                                                                  Element(k_name), Tem, state,
                                                                                  geo_model, geo_model_name,
                                                                                  full_alloy_str)
                    epislon_j_p = ternary_melts.activity_interact_coefficient_1st(solv, Element(j_name),
                                                                                  Element(p_name), Tem, state,
                                                                                  geo_model, geo_model_name,
                                                                                  full_alloy_str)
                    epislon_p_k = ternary_melts.activity_interact_coefficient_1st(solv, Element(p_name),
                                                                                  Element(k_name), Tem, state,
                                                                                  geo_model, geo_model_name,
                                                                                  full_alloy_str)
                    rho_p_jk = ternary_melts.roui_jk(solv, soluk, solup, soluj, Tem, state, geo_model, geo_model_name)
                    corrected_term_sum +=  xp * xj * xk * (rho_p_jk + epislon_j_k)
        if activity_model_type == "Elliot1" or activity_model_type == "elliot1":
            # 仿照Darken修正项：添加三次修正项
            return ln_yi_0 + linear_sum + quadratic_sum_elliot  - 1.0/3*corrected_term_sum
            
            
        return 0.0 # Should not happen
        
       
        # 📍 新增功能 1: 根据 Kang-2020.pdf (UIPF模型) 实现溶剂活度系数的计算
    def _calculate_ln_gamma_solvent_UIPF (self, comp_dict: Dict[str, float], solvent: str, Tem: float, state: str,
                                              geo_model: extrap_func, geo_model_name: str,activity_model_type:str,
                                              full_alloy_str: str = "") -> float:
        """
            计算溶剂的活度系数 (ln γ_solvent)。
            该实现基于 Kang-2020.pdf 中描述的 Unified Interaction Parameter Formalism (UIPF)。
            公式: ln γ₁ = - (1/2) * Σ(j,k=2 to N) ε_jk * X_j * X_k
        """
        if solvent not in comp_dict:
            print(f"警告: 溶剂 {solvent} 不在成分中。")
            return 0.0

        solv = Element(solvent)
        solute_keys = [k for k in comp_dict.keys() if k != solvent]
        
        # 如果体系中只有溶剂，则 ln γ_solvent = 0 (活度系数为 1)
        if not solute_keys:
            return 0.0

        ternary_melts = TernaryMelts(Tem, state)
        
        quadratic_sum = 0.0
        # 根据UIPF公式进行双重求和
        for j_name in solute_keys:
            xj = comp_dict[j_name]
            soluj = Element(j_name)
            for k_name in solute_keys:
                xk = comp_dict[k_name]
                soluk = Element(k_name)
                
                # 获取溶质j和溶质k之间的一阶相互作用参数 ε_jk (在溶剂1中)
                epsilon_j_k = ternary_melts.activity_interact_coefficient_1st(solv, soluj, soluk, Tem, state, geo_model,
                                                                              geo_model_name, full_alloy_str)
                
                quadratic_sum += epsilon_j_k * xj * xk

        return -0.5 * quadratic_sum
        
      
        
    # 📍 新增功能 2: 创建一个统一的计算入口函数
    def get_ln_gamma(self, comp_dict: Dict[str, float], component_to_calculate: str, solvent: str,
                     Tem: float, state: str, geo_model: extrap_func, geo_model_name: str,activity_model_type:str,
                     full_alloy_str: str = "") -> float:
        """
        统一的活度系数计算入口。
        根据待计算组分是否为溶剂，分发到不同的计算方法。
        """
        # 如果待计算组分是溶剂
        if component_to_calculate == solvent:
            # Darken模型和UIPF在热力学上是一致的，直接调用UIPF溶剂公式
            return self._calculate_ln_gamma_solvent_UIPF(
                    comp_dict, solvent, Tem, state, geo_model, geo_model_name, activity_model_type, full_alloy_str)
        # 如果待计算组分是溶质
        else:
            return self._calculate_ln_yi(comp_dict, solvent, component_to_calculate, Tem, state, geo_model,
                                         geo_model_name, activity_model_type, full_alloy_str)
    
   
    def get_ln_gamma_wagner (self, comp_dict, solvent, solute_i, Tem: float, state: str,
                                     extra_model: extrap_func, extra_model_name: str,activity_model , full_alloy_str: str = ""):
        """
        Wagner模型计算活度系数
        
        """
        
        
        return self._calculate_ln_yi(comp_dict, solvent, solute_i, Tem, state, extra_model, extra_model_name, activity_model,
                                     full_alloy_str)
    
    def get_ln_gamma_darken (self, comp_dict, solute_i, matrix, Tem: float, phase_state: str,
                                     extra_model: extrap_func, extra_model_name: str,activity_model, full_alloy_str: str = ""):
        """Darken模型 - """
        
        
        return self._calculate_ln_yi(comp_dict, matrix, solute_i, Tem, phase_state, extra_model, extra_model_name, activity_model,
                                     full_alloy_str)
    
    # 📍 修改点6: 修正函数名拼写
    def get_ln_gamma_elliott (self, comp_dict, solute_i, matrix, Tem, phase_state: str,
                                      extra_model: extrap_func, extra_model_name: str,activity_model, full_alloy_str: str = ""):
        """Elliott模型 - """
        
        
        return self._calculate_ln_yi(comp_dict, matrix, solute_i, Tem, phase_state, extra_model, extra_model_name, activity_model,
                                     full_alloy_str)
    
   
    
   