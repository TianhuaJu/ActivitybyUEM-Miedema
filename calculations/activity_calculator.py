# activity_calculator.py

import re
import math
from copy import deepcopy

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
        solute_keys = [k for k in comp_dict.keys() if k != solvent]
        ternary_melts = TernaryMelts(Tem, state)
        ln_yi_0 = ternary_melts.ln_y0(solv, solui)

        linear_sum = 0.0
        for j_name in solute_keys:
            xj = comp_dict[j_name]
            epsilon_i_j = ternary_melts.activity_interact_coefficient_1st(
                    solv, solui, Element(j_name), Tem, state, geo_model, geo_model_name)
            linear_sum += epsilon_i_j * xj

        if model_type == "Wagner":
            return ln_yi_0 + linear_sum

        quadratic_sum_darken = 0.0
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
                    epsilon_j_k = ternary_melts.activity_interact_coefficient_1st(
                            solv, Element(j_name), Element(k_name), Tem, state, geo_model, geo_model_name)
                    rho_p_jk = ternary_melts.roui_jk(solv, solup, soluj, soluk, Tem, state, geo_model, geo_model_name)
                    corrected_term_sum +=  xp * xj * xk * (rho_p_jk + epsilon_j_k)
        if model_type == "corrected":
            # 仿照Darken修正项：添加三次修正项
            return ln_yi_0 + linear_sum + quadratic_sum_elliot  - 1.0/3*corrected_term_sum
            
            
        return 0.0 # Should not happen
        
        # 📍 修改点3: 新增溶剂活度系数计算函数
    def _calculate_ln_gamma_solvent (self, comp_dict, solvent, Tem: float, state: str,
                                         geo_model: extrap_func, geo_model_name: str, model_type: str) -> float:
            """
			计算溶剂活度系数

			基于对称性和Gibbs-Duhem一致性的溶剂活度系数计算
			"""
            if solvent not in comp_dict:
                print(f"警告: 溶剂 {solvent} 不在成分中。")
                return 0.0
            
            solv = Element(solvent)
            solute_keys = [k for k in comp_dict.keys() if k != solvent]
            
            # 如果只有溶剂，活度系数为1 (ln γ = 0)
            if len(solute_keys) == 0:
                return 0.0
            
            ternary_melts = TernaryMelts(Tem, state)
            
            # 计算溶剂-溶质相互作用贡献
            linear_sum = 0.0
            for j_name in solute_keys:
                xj = comp_dict[j_name]
                # 溶剂-溶质相互作用参数 (对称性)
                epsilon_solv_j = ternary_melts.activity_interact_coefficient_1st(
                        solv, solv, Element(j_name), Tem, state, geo_model, geo_model_name)
                linear_sum += epsilon_solv_j * xj
            
            if model_type == "Wagner":
                return linear_sum
            
            # 计算二次项贡献
            quadratic_sum = 0.0
            
            if model_type == "Darken":
                # Darken模型的溶剂二次项
                for j_name in solute_keys:
                    xj = comp_dict[j_name]
                    for k_name in solute_keys:
                        xk = comp_dict[k_name]
                        epsilon_j_k = ternary_melts.activity_interact_coefficient_1st(
                                solv, Element(j_name), Element(k_name), Tem, state, geo_model, geo_model_name)
                        quadratic_sum += xj * xk * epsilon_j_k
                
                # 溶剂自身的相互作用项
                x_solvent = comp_dict[solvent]
                for j_name in solute_keys:
                    xj = comp_dict[j_name]
                    epsilon_solv_j = ternary_melts.activity_interact_coefficient_1st(
                            solv, solv, Element(j_name), Tem, state, geo_model, geo_model_name)
                    quadratic_sum += 2 * x_solvent * xj * epsilon_solv_j
                
                return linear_sum - 0.5 * quadratic_sum
            
            elif model_type == "Elliot":
                # Elliott模型的溶剂项
                for j_name in solute_keys:
                    xj = comp_dict[j_name]
                    soluj = Element(j_name)
                    for k_name in solute_keys:
                        xk = comp_dict[k_name]
                        soluk = Element(k_name)
                        rho_solv_jk = ternary_melts.roui_jk(solv, solv, soluj, soluk, Tem, state, geo_model,
                                                            geo_model_name)
                        quadratic_sum += 0.5 * rho_solv_jk * xj * xk
                
                return linear_sum + quadratic_sum
            
            elif model_type == "corrected":
                # Elliott项
                quadratic_sum_elliot = 0.0
                for j_name in solute_keys:
                    xj = comp_dict[j_name]
                    soluj = Element(j_name)
                    for k_name in solute_keys:
                        xk = comp_dict[k_name]
                        soluk = Element(k_name)
                        rho_solv_jk = ternary_melts.roui_jk(solv, solv, soluj, soluk, Tem, state, geo_model,
                                                            geo_model_name)
                        quadratic_sum_elliot += 0.5 * rho_solv_jk * xj * xk
                
                # 三次修正项
                cubic_sum = 0.0
                for j_name in solute_keys:
                    xj = comp_dict[j_name]
                    soluj = Element(j_name)
                    for k_name in solute_keys:
                        xk = comp_dict[k_name]
                        soluk = Element(k_name)
                        for p_name in solute_keys:
                            xp = comp_dict[p_name]
                            solup = Element(p_name)
                            epsilon_j_k = ternary_melts.activity_interact_coefficient_1st(
                                    solv, Element(j_name), Element(k_name), Tem, state, geo_model, geo_model_name)
                            rho_solv_jk = ternary_melts.roui_jk(solv, solv, soluj, soluk, Tem, state, geo_model,
                                                                geo_model_name)
                            cubic_sum += xp * xj * xk * (rho_solv_jk + epsilon_j_k)
                
                return linear_sum + quadratic_sum_elliot - 1.0 / 3 * cubic_sum
            
            return 0.0
    
    
    # 📍 修改点4: 改进的G-D验证函数
    def verify_gibbs_duhem (self, comp_dict, solvent, Tem: float, state: str,
                            geo_model, geo_model_name: str, model_type: str,
                            perturbation: float = 1e-6, tolerance: float = 1e-4,
                            verbose: bool = False) -> dict:
        """
        完整的Gibbs-Duhem方程验证函数

        新增参数:
        verbose : bool
            是否输出详细验证信息
        """
        # 验证输入
        if abs(sum(comp_dict.values()) - 1.0) > 1e-10:
            return {
                'valid': False,
                'error': f'摩尔分数之和不为1: {sum(comp_dict.values())}'
            }
        
        if solvent not in comp_dict:
            return {
                'valid': False,
                'error': f'溶剂 {solvent} 不在组分字典中'
            }
        
        all_components = list(comp_dict.keys())
        solute_components = [comp for comp in all_components if comp != solvent]
        
        if len(solute_components) < 1:
            return {
                'valid': False,
                'error': '至少需要一个溶质组分来验证G-D方程'
            }
        
        results = {
            'valid': True,
            'gd_violations': [],
            'max_violation': 0.0,
            'component_derivatives': {},
            'summary': {}
        }
        
        try:
            # 📍 修改: 计算所有组分的活度系数，包括溶剂
            original_ln_gamma = {}
            for comp in all_components:
                if comp == solvent:
                    original_ln_gamma[comp] = self._calculate_ln_gamma_solvent(
                            comp_dict, solvent, Tem, state, geo_model, geo_model_name, model_type
                    )
                else:
                    original_ln_gamma[comp] = self._calculate_ln_yi(
                            comp_dict, solvent, comp, Tem, state, geo_model, geo_model_name, model_type
                    )
            
            if verbose:
                print("原始活度系数:")
                for comp, ln_gamma in original_ln_gamma.items():
                    print(f"  ln γ_{comp} = {ln_gamma:.6f}")
            
            # 对每个溶质组分进行扰动验证
            for perturb_comp in solute_components:
                perturbed_comp_dict = deepcopy(comp_dict)
                
                if comp_dict[perturb_comp] <= perturbation:
                    results['gd_violations'].append(f'组分 {perturb_comp} 的摩尔分数太小，无法扰动')
                    continue
                
                # 正向扰动
                perturbed_comp_dict[perturb_comp] += perturbation
                # 为保持总和为1，按比例调整其他组分
                remaining_sum = 1.0 - perturbed_comp_dict[perturb_comp]
                original_remaining_sum = 1.0 - comp_dict[perturb_comp]
                
                if original_remaining_sum > 0:
                    scale_factor = remaining_sum / original_remaining_sum
                    for comp in all_components:
                        if comp != perturb_comp:
                            perturbed_comp_dict[comp] = comp_dict[comp] * scale_factor
                
                # 计算扰动后的ln_gamma
                perturbed_ln_gamma = {}
                for comp in all_components:
                    if comp == solvent:
                        perturbed_ln_gamma[comp] = self._calculate_ln_gamma_solvent(
                                perturbed_comp_dict, solvent, Tem, state, geo_model, geo_model_name, model_type
                        )
                    else:
                        perturbed_ln_gamma[comp] = self._calculate_ln_yi(
                                perturbed_comp_dict, solvent, comp, Tem, state,
                                geo_model, geo_model_name, model_type
                        )
                
                # 计算数值导数
                derivatives = {}
                for comp in all_components:
                    derivatives[comp] = (perturbed_ln_gamma[comp] - original_ln_gamma[comp]) / perturbation
                
                results['component_derivatives'][perturb_comp] = derivatives
                
                # 📍 修改: G-D方程包含所有组分，包括溶剂
                gd_sum = 0.0
                for comp in all_components:  # 包含溶剂
                    gd_sum += comp_dict[comp] * derivatives[comp]
                
                if verbose:
                    print(f"\n扰动组分 {perturb_comp}:")
                    for comp in all_components:
                        print(
                                f"  x_{comp} * d(ln γ_{comp})/dx_{perturb_comp} = {comp_dict[comp]:.4f} * {derivatives[comp]:.6e}")
                    print(f"  G-D求和 = {gd_sum:.6e}")
                
                if abs(gd_sum) > tolerance:
                    violation_msg = f'对组分 {perturb_comp} 扰动时，G-D方程违背: {gd_sum:.6e}'
                    results['gd_violations'].append(violation_msg)
                    results['max_violation'] = max(results['max_violation'], abs(gd_sum))
            
            # 生成总结
            if results['gd_violations']:
                results['valid'] = False
                results['summary'] = {
                    'status': '不满足G-D方程',
                    'violation_count': len(results['gd_violations']),
                    'max_violation': results['max_violation'],
                    'tolerance': tolerance
                }
            else:
                results['summary'] = {
                    'status': '满足G-D方程',
                    'max_violation': results['max_violation'],
                    'tolerance': tolerance
                }
        
        except Exception as e:
            results['valid'] = False
            results['error'] = f'计算过程中出现错误: {str(e)}'
        
        return results
        
    # 📍 修改点5: 优化的活度系数计算函数
    
    def activity_coefficient_wagner (self, comp_dict, solvent, solute_i, Tem: float, state: str,
                                     geo_model: extrap_func, geo_model_name: str,
                                     verify_gd: bool = False, gd_verbose: bool = False):
        """
        Wagner模型计算活度系数

        新增参数:
        verify_gd : bool
            是否验证G-D方程，默认False
        gd_verbose : bool
            G-D验证是否输出详细信息，默认False
        """
        if verify_gd:
            if gd_verbose:
                print("=" * 50)
                print("Wagner模型 G-D方程验证")
                print("=" * 50)
            
            gd_result = self.verify_gibbs_duhem(
                    comp_dict, solvent, Tem, state, geo_model, geo_model_name, "Wagner",
                    verbose=gd_verbose
            )
            
            if gd_verbose:
                self._print_gd_summary(gd_result)
            else:
                print(f"Wagner G-D验证: {gd_result['summary']['status']}")
                if gd_result['gd_violations']:
                    print(f"  最大违背: {gd_result['max_violation']:.6e}")
        
        return self._calculate_ln_yi(comp_dict, solvent, solute_i, Tem, state, geo_model, geo_model_name, "Wagner")
    
    def activity_coefficient_darken (self, comp_dict, solute_i, matrix, Tem: float, phase_state: str,
                                     geo_model: extrap_func, geo_model_name: str,
                                     verify_gd: bool = False, gd_verbose: bool = False):
        """Darken模型 - 参数名统一为solvent而非matrix"""
        if verify_gd:
            if gd_verbose:
                print("=" * 50)
                print("Darken模型 G-D方程验证")
                print("=" * 50)
            
            gd_result = self.verify_gibbs_duhem(
                    comp_dict, matrix, Tem, phase_state, geo_model, geo_model_name, "Darken",
                    verbose=gd_verbose
            )
            
            if gd_verbose:
                self._print_gd_summary(gd_result)
            else:
                print(f"Darken G-D验证: {gd_result['summary']['status']}")
                if gd_result['gd_violations']:
                    print(f"  最大违背: {gd_result['max_violation']:.6e}")
        
        return self._calculate_ln_yi(comp_dict, matrix, solute_i, Tem, phase_state, geo_model, geo_model_name,
                                     "Darken")
    
    # 📍 修改点6: 修正函数名拼写
    def activity_coefficient_elliott (self, comp_dict, solute_i, matrix, Tem, phase_state: str,
                                      geo_model: extrap_func, geo_model_name: str,
                                      verify_gd: bool = False, gd_verbose: bool = False):
        """Elliott模型 - 修正了函数名拼写"""
        if verify_gd:
            if gd_verbose:
                print("=" * 50)
                print("Elliott模型 G-D方程验证")
                print("=" * 50)
            
            gd_result = self.verify_gibbs_duhem(
                    comp_dict, matrix, Tem, phase_state, geo_model, geo_model_name, "Elliot",
                    verbose=gd_verbose
            )
            
            if gd_verbose:
                self._print_gd_summary(gd_result)
            else:
                print(f"Elliott G-D验证: {gd_result['summary']['status']}")
                if gd_result['gd_violations']:
                    print(f"  最大违背: {gd_result['max_violation']:.6e}")
        
        return self._calculate_ln_yi(comp_dict, matrix, solute_i, Tem, phase_state, geo_model, geo_model_name,
                                     "Elliot")
    
    def activity_coefficient_corrected (self, comp_dict, solute_i, matrix, Tem, phase_state: str,
                                        geo_model: extrap_func, geo_model_name: str,
                                        verify_gd: bool = False, gd_verbose: bool = False):
        """修正模型"""
        if verify_gd:
            if gd_verbose:
                print("=" * 50)
                print("Corrected模型 G-D方程验证")
                print("=" * 50)
            
            gd_result = self.verify_gibbs_duhem(
                    comp_dict, matrix, Tem, phase_state, geo_model, geo_model_name, "corrected",
                    verbose=gd_verbose
            )
            
            if gd_verbose:
                self._print_gd_summary(gd_result)
            else:
                print(f"Corrected G-D验证: {gd_result['summary']['status']}")
                if gd_result['gd_violations']:
                    print(f"  最大违背: {gd_result['max_violation']:.6e}")
        
        return self._calculate_ln_yi(comp_dict, matrix, solute_i, Tem, phase_state, geo_model, geo_model_name,
                                     "corrected")
    
    # 📍 修改点7: 新增辅助函数
    def _print_gd_summary (self, gd_result: dict):
        """打印G-D验证摘要的辅助函数"""
        print(f"\n📊 验证结果摘要:")
        print(f"   状态: {gd_result['summary']['status']}")
        print(f"   最大违背: {gd_result['max_violation']:.6e}")
        print(f"   容差: {gd_result['summary']['tolerance']:.6e}")
        
        if gd_result['gd_violations']:
            print(f"   违背次数: {len(gd_result['gd_violations'])}")
            print("   违背详情:")
            for violation in gd_result['gd_violations']:
                print(f"     • {violation}")
        else:
            print("   ✅ 完全满足G-D方程!")
    
    # 📍 修改点8: 新增获取溶剂活度系数的公共接口
    def get_solvent_activity_coefficient (self, comp_dict, solvent, Tem: float, state: str,
                                          geo_model: extrap_func, geo_model_name: str, model_type: str) -> float:
        """
        获取溶剂活度系数的公共接口

        Returns:
        --------
        float : ln(γ_solvent)
        """
        return self._calculate_ln_gamma_solvent(comp_dict, solvent, Tem, state, geo_model, geo_model_name,
                                                model_type)
    
    # 📍 修改点9: 新增完整组成活度系数计算
    def get_all_activity_coefficients (self, comp_dict, solvent, Tem: float, state: str,
                                       geo_model: extrap_func, geo_model_name: str, model_type: str) -> dict:
        """
        计算所有组分的活度系数

        Returns:
        --------
        dict : {组分名: ln(γ_i)}
        """
        ln_gamma_dict = {}
        
        # 计算溶剂活度系数
        ln_gamma_dict[solvent] = self._calculate_ln_gamma_solvent(
                comp_dict, solvent, Tem, state, geo_model, geo_model_name, model_type
        )
        
        # 计算所有溶质活度系数
        for comp in comp_dict.keys():
            if comp != solvent:
                ln_gamma_dict[comp] = self._calculate_ln_yi(
                        comp_dict, solvent, comp, Tem, state, geo_model, geo_model_name, model_type
                )
        
        return ln_gamma_dict
        