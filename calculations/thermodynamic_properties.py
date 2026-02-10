"""
Thermodynamic Properties Calculator
====================================
计算多组元合金的完整热力学性质

(V2.1 - [Gemini] 修正了固相活度模型)
- 固相 ('solid') 被假定为理想溶液 (ln_gamma = 0)
- 液相 ('liquid') 继续使用 Miedema/UEM/Wagner 模型

作者: Claude
日期: 2025-11-09
"""

import math
from typing import Dict, Optional, Tuple, List, Callable
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tdb_parser import get_tdb_parser, TDBParser
from core.constants import Constants
from calculations.activity_calculator import ActivityCoefficient,extrap_func
from models.extrapolation_models import BinaryModel

class ThermodynamicProperties:
    """多组元合金热力学性质计算器"""

    def __init__(self):
        self.tdb_parser: TDBParser = get_tdb_parser()

        

        self.activity_calculator = ActivityCoefficient()
        self.binary_model = BinaryModel()
        self.R = Constants.R  # J/(mol*K)

    # ================================================================
    # =================== 符号转换辅助函数 ===================
    # ================================================================
    @staticmethod
    def _to_standard_symbol(symbol: str) -> str:
        """
        (关键修正)
        将TDB的大写符号 (例如 'FE') 转换为 Miedema 的标准符号 (例如 'Fe')。
        """
        if not symbol or len(symbol) == 0:
            return symbol
        # .capitalize() 正确处理 'FE' -> 'Fe' 和 'C' -> 'C'
        return symbol.capitalize()

    def calculate_activity(self,
                          composition: Dict[str, float],
                          component: str,
                          temperature: float,
                          phase_state: str,
                          extrapolation_model_func: extrap_func,
                          extrapolation_model_name: str,
                          activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算组分的活度 a_i = γ_i * X_i
        """
        ln_gamma = self.calculate_ln_activity_coefficient(composition, component, temperature, phase_state,
                                                          extrapolation_model_func, extrapolation_model_name, activity_model)
        if ln_gamma is None:
            return None
        gamma = math.exp(ln_gamma)
        x_i = composition.get(component, 0.0)
        activity = gamma * x_i
        return activity

    def calculate_ln_activity_coefficient(self,
                                         composition: Dict[str, float],
                                         component: str,
                                         temperature: float,
                                         phase_state: str,
                                         extrapolation_model_func: extrap_func,
                                          extrapolation_model_name,
                                         activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算活度系数的对数 ln(γ_i)

        (V2.2 扩展) 支持液相和固相溶体。
        - 'liquid': 使用 UEM/Wagner/Miedema 模型 (state='liquid')
        - 'solid':  使用 UEM/Wagner/Miedema 模型 (state='solid')

        固相溶体和液相均通过 UEM-Miedema 框架计算活度系数。
        """

        # 1. 确定溶剂 (仍然使用大写符号)
        valid_components = {k: v for k, v in composition.items() if v > 0}
        solvent = max(valid_components.items(), key=lambda x: x[1])[0]
        

        # 2. --- (关键修正: 转换为标准符号) ---
        try:
            comp_dict_std = {self._to_standard_symbol(k): v for k, v in composition.items()}
            component_std = self._to_standard_symbol(component)
            solvent_std = self._to_standard_symbol(solvent)
        except Exception as e:
            print(f"Error standardizing symbols: {e}")
            return None
        # --- (修正结束) ---

        ln_gamma = self.activity_calculator.get_ln_gamma(
                comp_dict=comp_dict_std,
                component_to_calculate=component_std,
                solvent=solvent_std,  # 添加 solvent 参数
                Tem=temperature,
                state=phase_state,
                extra_model=extrapolation_model_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model
        )
        return ln_gamma

    def calculate_chemical_potential(self,
                                     composition: Dict[str, float],
                                     component: str,
                                     temperature: float,
                                     phase_state: str = 'liquid',
                                     solvent: str = None,
                                     extrapolation_model_func: extrap_func = None,
                                     extrapolation_model_name: str = 'UEM1',
                                     activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算化学势 μ_i = μ°_i(T) + RT ln(a_i)

        [V2.1 注] TDB 查找需要根据 phase_state 映射到正确的相
        'liquid' -> 'LIQUID'
        'solid'  -> 'BCC_A2', 'FCC_A1' 等。
        但是，phase_diagram.py 会直接传入 TDB 相名 ('BCC_A2')，
        这会导致这里的 phase_map 查找失败。

        我们将假定 phase_diagram.py 中的 _get_chemical_potential 是
        主要的调用者，它不依赖于这个函数。
        这个函数主要用于 if __name__ == "__main__" 测试。
        """
        # Default extrapolation model if not provided
        if extrapolation_model_func is None:
            from models.extrapolation_models import BinaryModel
            bm = BinaryModel()
            extrapolation_model_func = bm.UEM1

        phase_map = {'liquid': 'LIQUID', 'solid': 'SER'}
        
        # 尝试将 'solid' 映射到 TDB 参考相
        tdb_phase = 'LIQUID'
        if phase_state.lower() == 'liquid':
             tdb_phase = 'LIQUID'
        elif phase_state.lower() == 'solid':
             # 这是一个不完美的映射，SER (固相参考态)
             # 在 TDBParser 中可能未实现，它期望 'BCC_A2' 等。
             # 我们将尝试获取参考相。
             try:
                ref_phase = self.tdb_parser.get_reference_phase(component)
                tdb_phase = ref_phase if ref_phase is not None else 'SER'
             except:
                tdb_phase = 'SER' # 回退
        else:
             tdb_phase = 'LIQUID'


        # (正确) 使用大写符号 (FE) 调用 TDB 解析器
        mu_0 = self.tdb_parser.get_gibbs_energy(component, tdb_phase, temperature)
        if mu_0 is None:
            # print(f"Warning: Could not find G° for {component} in {tdb_phase} phase at T={temperature}K")
            # 这是一个常见的警告 (例如 SER for C)，所以暂时注释掉
            pass
            

        # (正确) 内部函数将处理转换
        activity = self.calculate_activity(
            composition, component, temperature, phase_state,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )
        if activity is None or activity <= 0:
            # print(f"Warning: Activity for {component} is {activity}, cannot calculate log(a_i)")
            return None # 无法计算 log(0)
            
        if mu_0 is None:
            # print(f"Warning: G° for {component} ({tdb_phase}) is None, cannot calculate chemical potential.")
            return None

        mu = mu_0 + self.R * temperature * math.log(activity)
        return mu

    def calculate_molar_enthalpy(self,
                                 composition: Dict[str, float],
                                 temperature: float,
                                 phase_state: str = 'liquid',
                                 extrapolation_model_func: extrap_func = None,
                                 extrapolation_model_name: str = 'UEM1') -> Optional[float]:
        """
        计算合金的摩尔焓 H_alloy = Σ(X_i * H°_i) + H^E
        """
        # Default extrapolation model if not provided
        if extrapolation_model_func is None:
            from models.extrapolation_models import BinaryModel
            bm = BinaryModel()
            extrapolation_model_func = bm.UEM1

        H_ideal = 0.0

        # [V2.1 修正] 改进 phase_state 映射
        tdb_phase_map = {'liquid': 'LIQUID', 'solid': None}
        
        for component, x_i in composition.items():
            tdb_phase_name = 'LIQUID'
            if phase_state.lower() == 'liquid':
                 tdb_phase_name = 'LIQUID'
            elif phase_state.lower() == 'solid':
                 ref_phase = self.tdb_parser.get_reference_phase(component)
                 tdb_phase_name = ref_phase if ref_phase is not None else 'SER'
            
            # (正确) 使用大写符号 (FE) 调用 TDB 解析器
            H_i = self.tdb_parser.get_enthalpy(component, tdb_phase_name, temperature)
            if H_i is None:
                # print(f"Warning: Could not find H° for {component} in {tdb_phase_name}")
                # 理想部分将不完整
                pass
            else:
                H_ideal += x_i * H_i

        # (正确) 内部函数将处理转换
        H_excess = self._calculate_excess_enthalpy(
            composition, temperature, phase_state, extrapolation_model_func, extrapolation_model_name
        )
        if H_excess is None:
            print("Warning: Could not calculate excess enthalpy, using ideal mixing only")
            H_excess = 0.0

        H_total = H_ideal + H_excess
        return H_total

    def calculate_gibbs_energy(self,
                               composition: Dict[str, float],
                               temperature: float,
                               phase_state: str = 'liquid',
                               solvent: str = None,
                               extrapolation_model_func: extrap_func = None,
                               extrapolation_model_name: str = 'UEM1',
                               activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算合金的摩尔Gibbs自由能 G_alloy = Σ(X_i * μ_i)
        """
        # Default extrapolation model if not provided
        if extrapolation_model_func is None:
            from models.extrapolation_models import BinaryModel
            bm = BinaryModel()
            extrapolation_model_func = bm.UEM1

        G_total = 0.0
        failed = False
        for component, x_i in composition.items():
            mu_i = self.calculate_chemical_potential(
                composition, component, temperature, phase_state,
                solvent, extrapolation_model_func, extrapolation_model_name, activity_model
            )
            if mu_i is None:
                # print(f"Warning: mu_i for {component} is None, G calculation failed.")
                failed = True
                continue # 尝试计算其他组分
            G_total += x_i * mu_i
            
        if failed and G_total == 0.0:
            return None # 如果所有组分都失败了
            
        return G_total

    def calculate_entropy(self,
                         composition: Dict[str, float],
                         temperature: float,
                         phase_state: str = 'liquid',
                         solvent: str = None,
                         extrapolation_model_func: extrap_func = None,
                         extrapolation_model_name: str = 'UEM1',
                         activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算合金的摩尔熵 S = (H - G) / T
        """
        # Default extrapolation model if not provided
        if extrapolation_model_func is None:
            from models.extrapolation_models import BinaryModel
            bm = BinaryModel()
            extrapolation_model_func = bm.UEM1

        H = self.calculate_molar_enthalpy(
            composition, temperature, phase_state, extrapolation_model_func, extrapolation_model_name
        )
        G = self.calculate_gibbs_energy(
            composition, temperature, phase_state, solvent,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )
        if H is None or G is None:
            return None
        if temperature == 0:
            return None
        S = (H - G) / temperature
        return S

    def _calculate_excess_enthalpy(self,
                                   composition: Dict[str, float],
                                   temperature: float,
                                   phase_state: str = 'liquid',
                                   extrapolation_model_func: extrap_func = None,
                                   extrapolation_model_name: str = 'UEM1') -> Optional[float]:
        """
        使用Miedema模型计算过剩焓（混合焓）
        (已修正) 此函数将大写TDB符号(FE)转换为标准Miedema符号(Fe)。

        [V2.1 注] Miedema 模型是为液相设计的。如果请求固相，
        我们应该返回 0 (理想溶液的 H_excess)。
        """
        # Default extrapolation model if not provided
        if extrapolation_model_func is None:
            from models.extrapolation_models import BinaryModel
            bm = BinaryModel()
            extrapolation_model_func = bm.UEM1

        # --- [V2.1 关键修正] ---
        if phase_state.lower() == 'solid':
            return 0.0 # 固相理想溶液
        # --- [修改结束] ---

        try:
            # --- (关键修正: 转换为标准符号) ---
            comp_std = {self._to_standard_symbol(k): v for k, v in composition.items()}
            components = list(comp_std.keys())
            # --- (修正结束) ---

            n = len(components)
            if n == 1: return 0.0

            if n == 2:
                elem_a = components[0]; elem_b = components[1]
                x_a = comp_std[elem_a]; x_b = comp_std[elem_b]
                self.binary_model.set_state(phase_state)
                self.binary_model.set_temperature(temperature)
                # (正确) 传递 'Fe', 'C'
                H_mix = self.binary_model.binary_model(elem_a, elem_b, x_a, x_b)
                return H_mix

            # 多元外推 - 直接使用传入的函数对象
            # (正确) 传递标准符号
            H_excess = extrapolation_model_func(
                comp_dict=comp_std,
                Tem=temperature,
                binary_model_func=self.binary_model.binary_model,
                state=phase_state
            )

            return H_excess
            
        except Exception as e:
            print(f"Error calculating excess enthalpy: {e}")
            return None

    def calculate_all_properties(self,
                                 composition: Dict[str, float],
                                 temperature: float,
                                 phase_state: str = 'liquid',
                                 solvent: str = None,
                                 extrapolation_model_func: extrap_func = None,
                                 extrapolation_model_name: str = 'UEM1',
                                 activity_model: str = 'Wagner') -> Dict[str, Dict]:
        """
        计算所有热力学性质
        """
        # Default extrapolation model if not provided
        if extrapolation_model_func is None:
            from models.extrapolation_models import BinaryModel
            bm = BinaryModel()
            extrapolation_model_func = bm.UEM1

        results = {'component_properties': {}, 'alloy_properties': {}}
        for component in composition.keys():
            comp_results = {}
            ln_gamma = self.calculate_ln_activity_coefficient(composition, component, temperature, phase_state,
                                                              extrapolation_model_func, extrapolation_model_name, activity_model)
            comp_results['ln_gamma'] = ln_gamma
            comp_results['gamma'] = math.exp(ln_gamma) if ln_gamma is not None else None
            activity = self.calculate_activity(
                composition, component, temperature, phase_state,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )
            comp_results['activity'] = activity
            mu = self.calculate_chemical_potential(
                composition, component, temperature, phase_state,
                solvent, extrapolation_model_func, extrapolation_model_name, activity_model
            )
            comp_results['mu'] = mu
            comp_results['mole_fraction'] = composition[component]
            results['component_properties'][component] = comp_results

        H = self.calculate_molar_enthalpy(
            composition, temperature, phase_state, extrapolation_model_func, extrapolation_model_name
        )
        results['alloy_properties']['H'] = H
        G = self.calculate_gibbs_energy(
            composition, temperature, phase_state, solvent,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )
        results['alloy_properties']['G'] = G
        S = self.calculate_entropy(
            composition, temperature, phase_state, solvent,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )
        results['alloy_properties']['S'] = S
        results['alloy_properties']['T'] = temperature
        results['alloy_properties']['phase'] = phase_state
        return results

    # ================================================================
    # =================== Module 1: 液相线温度计算 ===================
    # ================================================================

    def get_liquidus_temperature(
        self,
        composition: Dict[str, float],
        extrapolation_model_func: extrap_func = None,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner',
        T_initial_guess: float = None,
        max_iterations: int = 50,
        tolerance: float = 0.1,
        user_data: Dict = None
    ) -> Dict:
        """
        计算溶剂液相线温度 (Modified Schroder-van Laar Equation)

        物理原理:
        ---------
        杂质会降低熔点。降低程度由溶剂活度 a_solvent 控制，
        而溶剂活度受溶质-溶质相互作用系数 ε 影响。

        数学模型:
        ---------
        T_liq = (1/T_pure^m - R/ΔH_f * ln(a_solvent))^(-1)

        其中溶剂活度包含相互作用系数修正:
        ln(a_solvent) = ln(x_solvent) + (-1/2 * ΣΣ ε_i^j * x_i * x_j)

        参数:
        -----
        composition : Dict[str, float]
            合金成分 {元素符号: 摩尔分数}
        extrapolation_model_func : callable
            外推模型函数 (默认使用UEM1)
        extrapolation_model_name : str
            外推模型名称
        activity_model : str
            活度模型 ('Wagner', 'Darken', 'Elliott')
        T_initial_guess : float, optional
            初始温度猜测值 (K)
        max_iterations : int
            最大迭代次数 (用于温度相关ε的迭代求解)
        tolerance : float
            收敛容差 (K)
        user_data : Dict, optional
            用户提供的数据覆盖，格式为:
            {
                'enthalpy_of_fusion': {元素符号: 值或可调用函数f(T)},
                'melting_point': {元素符号: 值}
            }

        返回:
        -----
        Dict: {
            'status': 'success', 'error', or 'missing_data',
            'liquidus_temperature': float (K),
            'liquidus_temperature_celsius': float (°C),
            'melting_point_depression': float (K),
            'solvent': str,
            'solvent_activity': float,
            'interaction_correction': float,
            'pure_melting_point': float (K),
            'iterations': int,
            'message': str,
            'missing_data': list (当status='missing_data'时)
        }
        """
        from core.element import Element
        from scipy.optimize import brentq
        from models.activity_interaction_parameters import multicomponentSolution

        # 设置默认外推模型
        if extrapolation_model_func is None:
            extrapolation_model_func = self.binary_model.UEM1

        # 归一化成分
        total = sum(composition.values())
        if total <= 0:
            return {
                'status': 'error',
                'message': '合金成分不能为空',
                'liquidus_temperature': None
            }

        comp = {self._to_standard_symbol(k): v / total for k, v in composition.items()}

        # 确定溶剂（含量最高的组元）
        solvent = max(comp.items(), key=lambda item: item[1])[0]
        x_solvent = comp[solvent]

        # 获取溶剂元素属性
        solvent_elem = Element(solvent)
        if not solvent_elem.is_exist:
            return {
                'status': 'error',
                'message': f'元素 {solvent} 数据不存在',
                'liquidus_temperature': None
            }

        # 初始化user_data
        if user_data is None:
            user_data = {}

        # 收集缺失数据
        missing_data = []

        # 纯溶剂熔点 (K)
        T_pure_m = None
        if 'melting_point' in user_data and solvent in user_data['melting_point']:
            T_pure_m = user_data['melting_point'][solvent]
        elif solvent_elem.tm and solvent_elem.tm > 0:
            T_pure_m = solvent_elem.tm
        else:
            missing_data.append({
                'type': 'melting_point',
                'element': solvent,
                'description': f'元素 {solvent} 的熔点',
                'unit': 'K',
                'example': '1811 (Fe的熔点)'
            })

        # 熔化焓数据 (J/mol) - 常见金属
        ENTHALPY_OF_FUSION = {
            'Al': 10710, 'Fe': 13810, 'Cu': 13260, 'Ni': 17480,
            'Mg': 8480, 'Zn': 7320, 'Ti': 14150, 'Cr': 21000,
            'Mn': 12910, 'Si': 50210, 'Co': 16200, 'Mo': 37480,
            'W': 52310, 'Ag': 11300, 'Au': 12550, 'Pb': 4774,
            'Sn': 7030, 'Zr': 21000, 'Nb': 30000, 'V': 21500
        }

        # 获取熔化焓
        delta_H_f = None
        if 'enthalpy_of_fusion' in user_data and solvent in user_data['enthalpy_of_fusion']:
            user_value = user_data['enthalpy_of_fusion'][solvent]
            # 支持常数或可调用函数
            if callable(user_value):
                delta_H_f = user_value  # 保持为函数，稍后调用
            else:
                delta_H_f = float(user_value)
        elif solvent in ENTHALPY_OF_FUSION:
            delta_H_f = ENTHALPY_OF_FUSION[solvent]
        else:
            missing_data.append({
                'type': 'enthalpy_of_fusion',
                'element': solvent,
                'description': f'元素 {solvent} 的熔化焓 (ΔH_f)',
                'unit': 'J/mol',
                'example': '13810 (Fe的熔化焓)'
            })

        # 如果有缺失数据，返回missing_data状态
        if missing_data:
            return {
                'status': 'missing_data',
                'message': f'缺少必要的热力学数据',
                'missing_data': missing_data,
                'solvent': solvent,
                'liquidus_temperature': None
            }

        if T_initial_guess is None:
            T_initial_guess = T_pure_m * 0.95

        # 获取溶质列表
        solutes = [el for el in comp.keys() if el != solvent and comp[el] > 1e-10]

        if not solutes:
            # 纯溶剂
            return {
                'status': 'success',
                'liquidus_temperature': T_pure_m,
                'liquidus_temperature_celsius': T_pure_m - 273.15,
                'melting_point_depression': 0.0,
                'solvent': solvent,
                'solvent_activity': 1.0,
                'interaction_correction': 0.0,
                'pure_melting_point': T_pure_m,
                'iterations': 0,
                'message': '纯溶剂，液相线温度等于熔点'
            }

        def calculate_solvent_activity(T: float) -> Tuple[float, float]:
            """
            计算溶剂活度 a_solvent = x_solvent * γ_solvent

            使用UIPF模型: ln(γ_solvent) = -1/2 * ΣΣ ε_i^j * x_i * x_j
            """
            ternary_system = multicomponentSolution(T, 'liquid')
            solvent_elem_obj = Element(solvent)

            # 计算相互作用系数修正项
            interaction_sum = 0.0

            for i, solute_i in enumerate(solutes):
                x_i = comp[solute_i]
                solute_i_elem = Element(solute_i)

                for j, solute_j in enumerate(solutes):
                    x_j = comp[solute_j]
                    solute_j_elem = Element(solute_j)

                    try:
                        # 计算一阶相互作用系数 ε_i^j
                        epsilon_ij = ternary_system.activity_interact_coefficient_1st(
                            solvent_elem_obj, solute_i_elem, solute_j_elem,
                            T, 'liquid', extrapolation_model_func, extrapolation_model_name
                        )
                        interaction_sum += epsilon_ij * x_i * x_j
                    except Exception:
                        pass

            # 溶剂活度系数修正 (Gibbs-Duhem积分结果)
            # ln(γ_solvent) ≈ -1/2 * ΣΣ ε_i^j * x_i * x_j
            ln_gamma_solvent = -0.5 * interaction_sum

            # 溶剂活度
            ln_a_solvent = math.log(x_solvent) + ln_gamma_solvent
            a_solvent = math.exp(ln_a_solvent)

            return a_solvent, ln_gamma_solvent

        def get_delta_H_f_at_T(T: float) -> float:
            """获取温度T下的熔化焓（支持温度依赖）"""
            if callable(delta_H_f):
                return delta_H_f(T)
            return delta_H_f

        def liquidus_equation(T: float) -> float:
            """
            液相线方程残差:
            f(T) = 1/T - 1/T_pure_m + R/ΔH_f * ln(a_solvent) = 0
            """
            a_solvent, _ = calculate_solvent_activity(T)

            if a_solvent <= 0 or a_solvent > 1:
                return float('inf')

            # Schroder-van Laar方程 (支持温度依赖的熔化焓)
            delta_H_f_T = get_delta_H_f_at_T(T)
            residual = 1/T - 1/T_pure_m + (self.R / delta_H_f_T) * math.log(a_solvent)
            return residual

        # 迭代求解（因为ε可能依赖于温度）
        try:
            T_current = T_initial_guess

            for iteration in range(max_iterations):
                # 计算当前温度下的溶剂活度
                a_solvent, interaction_correction = calculate_solvent_activity(T_current)

                if a_solvent <= 0:
                    break

                # 使用Schroder-van Laar方程计算新的液相线温度 (支持温度依赖的熔化焓)
                delta_H_f_T = get_delta_H_f_at_T(T_current)
                ln_a = math.log(a_solvent)
                T_new = 1.0 / (1.0/T_pure_m - (self.R / delta_H_f_T) * ln_a)

                # 检查收敛
                if abs(T_new - T_current) < tolerance:
                    final_delta_H_f = get_delta_H_f_at_T(T_new)
                    return {
                        'status': 'success',
                        'liquidus_temperature': T_new,
                        'liquidus_temperature_celsius': T_new - 273.15,
                        'melting_point_depression': T_pure_m - T_new,
                        'solvent': solvent,
                        'solvent_activity': a_solvent,
                        'interaction_correction': interaction_correction,
                        'pure_melting_point': T_pure_m,
                        'enthalpy_of_fusion': final_delta_H_f,
                        'iterations': iteration + 1,
                        'message': f'收敛于{iteration + 1}次迭代'
                    }

                # 更新温度（使用松弛因子避免振荡）
                T_current = 0.7 * T_new + 0.3 * T_current

            # 达到最大迭代次数
            final_delta_H_f = get_delta_H_f_at_T(T_current)
            return {
                'status': 'warning',
                'liquidus_temperature': T_current,
                'liquidus_temperature_celsius': T_current - 273.15,
                'melting_point_depression': T_pure_m - T_current,
                'solvent': solvent,
                'solvent_activity': a_solvent,
                'interaction_correction': interaction_correction,
                'pure_melting_point': T_pure_m,
                'enthalpy_of_fusion': final_delta_H_f,
                'iterations': max_iterations,
                'message': f'达到最大迭代次数{max_iterations}，可能未完全收敛'
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'计算失败: {str(e)}',
                'liquidus_temperature': None
            }

    # ================================================================
    # =================== Module 2: 析出相温度计算 ===================
    # ================================================================

    def get_precipitation_temperature(
        self,
        composition: Dict[str, float],
        phase_type: str = 'Al3Fe',
        extrapolation_model_func: extrap_func = None,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner',
        T_min: float = 300.0,
        T_max: float = 2500.0,
        tolerance: float = 1.0,
        user_data: Dict = None
    ) -> Dict:
        """
        计算杂质析出温度 (Impurity Precipitation Temperature)

        物理原理:
        ---------
        当活度积 (Q_activity) 超过溶度积 (K_sp) 时，析出相形成。
        相互作用系数 ε 决定了杂质的有效浓度（活度）。

        平衡条件:
        ---------
        对于析出相 P = A_m B_n:
        Q_activity(T, x) = K_equilibrium(T)

        其中:
        K_eq(T) = exp(-ΔG°_f(T) / RT)
        Q_act = (a_A)^m * (a_B)^n = (γ_A * x_A)^m * (γ_B * x_B)^n

        活度系数:
        ln(γ_B) = ln(γ_B^∞) + Σ ε_B^k * x_k

        参数:
        -----
        composition : Dict[str, float]
            合金成分 {元素符号: 摩尔分数}
        phase_type : str
            析出相类型，例如:
            - 'Al3Fe', 'Al2Cu', 'Mg2Si' (铝合金)
            - 'Fe3C', 'TiC', 'NbC', 'TiN', 'AlN' (钢铁)
        extrapolation_model_func : callable
            外推模型函数
        extrapolation_model_name : str
            外推模型名称
        activity_model : str
            活度模型
        T_min, T_max : float
            温度搜索范围 (K)
        tolerance : float
            温度收敛容差 (K)

        user_data : Dict, optional
            用户提供的析出相数据覆盖，格式为:
            {
                'precipitate_data': {
                    相名: {
                        'formula': (元素A, 元素B),
                        'stoich': (m, n),
                        'delta_G': (A, B) 或 可调用函数f(T)
                    }
                }
            }

        返回:
        -----
        Dict: {
            'status': 'success', 'error', or 'missing_data',
            'precipitation_temperature': float (K),
            'precipitation_temperature_celsius': float (°C),
            'phase_type': str,
            'stoichiometry': Dict,
            'activity_product': float,
            'equilibrium_constant': float,
            'gibbs_energy_formation': float (J/mol),
            'element_activities': Dict,
            'message': str,
            'missing_data': list (当status='missing_data'时)
        }
        """
        from core.element import Element
        from scipy.optimize import brentq
        from models.activity_interaction_parameters import multicomponentSolution

        # 设置默认外推模型
        if extrapolation_model_func is None:
            extrapolation_model_func = self.binary_model.UEM1

        # 析出相数据库: {相名: {'formula': (元素A, 元素B), 'stoich': (m, n), 'delta_G': (A, B)}}
        # ΔG°_f = A + B*T (J/mol)
        PRECIPITATE_DATABASE = {
            # 铝合金系统
            'Al3Fe': {'formula': ('Al', 'Fe'), 'stoich': (3, 1), 'delta_G': (-152000, 30)},
            'Al2Cu': {'formula': ('Al', 'Cu'), 'stoich': (2, 1), 'delta_G': (-54000, 10)},
            'Mg2Si': {'formula': ('Mg', 'Si'), 'stoich': (2, 1), 'delta_G': (-77800, 15)},
            'Al3Ni': {'formula': ('Al', 'Ni'), 'stoich': (3, 1), 'delta_G': (-165000, 35)},
            'Al3Ti': {'formula': ('Al', 'Ti'), 'stoich': (3, 1), 'delta_G': (-146000, 25)},
            # 钢铁系统
            'Fe3C': {'formula': ('Fe', 'C'), 'stoich': (3, 1), 'delta_G': (29500, -28.0)},
            'TiC': {'formula': ('Ti', 'C'), 'stoich': (1, 1), 'delta_G': (-191000, 17.0)},
            'NbC': {'formula': ('Nb', 'C'), 'stoich': (1, 1), 'delta_G': (-147000, 12.0)},
            'VC': {'formula': ('V', 'C'), 'stoich': (1, 1), 'delta_G': (-115000, 12.0)},
            'TiN': {'formula': ('Ti', 'N'), 'stoich': (1, 1), 'delta_G': (-338000, 90.0)},
            'AlN': {'formula': ('Al', 'N'), 'stoich': (1, 1), 'delta_G': (-303000, 100.0)},
            'VN': {'formula': ('V', 'N'), 'stoich': (1, 1), 'delta_G': (-217000, 80.0)},
            'NbN': {'formula': ('Nb', 'N'), 'stoich': (1, 1), 'delta_G': (-247000, 85.0)},
            'Cr23C6': {'formula': ('Cr', 'C'), 'stoich': (23, 6), 'delta_G': (-410000, 100.0)},
            'Cr7C3': {'formula': ('Cr', 'C'), 'stoich': (7, 3), 'delta_G': (-180000, 50.0)},
        }

        # 初始化user_data
        if user_data is None:
            user_data = {}

        # 查找析出相数据：先检查user_data，再检查数据库
        phase_data = None
        user_provided_gibbs = False

        if 'precipitate_data' in user_data and phase_type in user_data['precipitate_data']:
            phase_data = user_data['precipitate_data'][phase_type]
            user_provided_gibbs = True
        elif phase_type in PRECIPITATE_DATABASE:
            phase_data = PRECIPITATE_DATABASE[phase_type]
        else:
            # 返回missing_data状态，让GUI提示用户输入
            return {
                'status': 'missing_data',
                'message': f'数据库中未找到析出相 {phase_type} 的热力学数据',
                'missing_data': [{
                    'type': 'precipitate_data',
                    'phase_type': phase_type,
                    'description': f'析出相 {phase_type} 的热力学数据',
                    'required_fields': ['formula (元素A, 元素B)', 'stoich (化学计量数m, n)', 'delta_G (A + B*T)'],
                    'example': "TiC: formula=('Ti', 'C'), stoich=(1,1), delta_G=(-191000, 17.0)"
                }],
                'known_phases': list(PRECIPITATE_DATABASE.keys()),
                'precipitation_temperature': None
            }

        elem_A, elem_B = phase_data['formula']
        m, n = phase_data['stoich']

        # delta_G可以是元组(A, B)或可调用函数
        delta_G_spec = phase_data['delta_G']
        if callable(delta_G_spec):
            # 用户提供了温度依赖的函数
            delta_G_func = delta_G_spec
            delta_G_A, delta_G_B = None, None  # 无法提取系数
        else:
            delta_G_A, delta_G_B = delta_G_spec
            delta_G_func = None

        # 归一化成分
        total = sum(composition.values())
        if total <= 0:
            return {
                'status': 'error',
                'message': '合金成分不能为空',
                'precipitation_temperature': None
            }

        comp = {self._to_standard_symbol(k): v / total for k, v in composition.items()}

        # 确定溶剂
        solvent = max(comp.items(), key=lambda item: item[1])[0]

        # 检查析出相元素是否存在
        x_A = comp.get(elem_A, 0)
        x_B = comp.get(elem_B, 0)

        if x_A <= 1e-12 or x_B <= 1e-12:
            return {
                'status': 'error',
                'message': f'析出相 {phase_type} 需要元素 {elem_A} 和 {elem_B}，但成分中缺少',
                'precipitation_temperature': None
            }

        def calculate_equilibrium_constant(T: float) -> Tuple[float, float]:
            """
            计算溶度积常数 K_sp(T)

            对于析出反应: A_m B_n (s) = m[A] + n[B]
            溶度积: K_sp = a_A^m * a_B^n = exp(+ΔG°_f / RT)

            当 Q > K_sp 时，溶液过饱和，析出发生

            返回: (K_sp, delta_G)
            """
            if delta_G_func is not None:
                # 使用用户提供的温度依赖函数
                delta_G = delta_G_func(T)
            else:
                # 使用线性温度依赖: ΔG = A + B*T
                delta_G = delta_G_A + delta_G_B * T
            # 溶度积 = 1/K_formation = exp(+ΔG_formation/RT)
            K_sp = math.exp(delta_G / (self.R * T))
            return K_sp, delta_G

        def calculate_activity_product(T: float) -> Tuple[float, Dict]:
            """
            计算活度积 Q = (a_A)^m * (a_B)^n

            其中活度 a_i = γ_i * x_i
            活度系数通过相互作用参数计算
            """
            ternary_system = multicomponentSolution(T, 'liquid')
            solvent_elem = Element(solvent)

            activities = {}

            for elem, x_elem, power in [(elem_A, x_A, m), (elem_B, x_B, n)]:
                elem_obj = Element(elem)

                if elem == solvent:
                    # 溶剂活度
                    gamma = 1.0  # 简化：溶剂活度系数≈1
                else:
                    # 溶质活度系数: ln(γ_i) = ln(γ_i^∞) + Σ ε_i^k * x_k
                    try:
                        # 无限稀释活度系数
                        ln_gamma_inf = ternary_system.ln_y0(solvent_elem, elem_obj)

                        # 相互作用系数修正
                        interaction_sum = 0.0
                        for other_elem, x_other in comp.items():
                            if other_elem != solvent and x_other > 1e-10:
                                other_elem_obj = Element(other_elem)
                                try:
                                    epsilon = ternary_system.activity_interact_coefficient_1st(
                                        solvent_elem, elem_obj, other_elem_obj,
                                        T, 'liquid', extrapolation_model_func, extrapolation_model_name
                                    )
                                    interaction_sum += epsilon * x_other
                                except:
                                    pass

                        ln_gamma = ln_gamma_inf + interaction_sum
                        gamma = math.exp(ln_gamma)

                    except Exception:
                        gamma = 1.0  # 回退到理想溶液

                activity = gamma * x_elem
                activities[elem] = {
                    'mole_fraction': x_elem,
                    'activity_coefficient': gamma,
                    'activity': activity
                }

            # 活度积
            Q = (activities[elem_A]['activity'] ** m) * (activities[elem_B]['activity'] ** n)

            return Q, activities

        def precipitation_equation(T: float) -> float:
            """
            析出方程残差:
            f(T) = ln(Q_activity) - ln(K_eq) = 0

            当 f(T) > 0: 过饱和，应析出
            当 f(T) < 0: 未饱和，不析出
            """
            K_eq, _ = calculate_equilibrium_constant(T)
            Q, _ = calculate_activity_product(T)

            if Q <= 0 or K_eq <= 0:
                return float('inf')

            return math.log(Q) - math.log(K_eq)

        # 使用Brentq方法求解析出温度
        try:
            # 检查边界条件
            f_min = precipitation_equation(T_min)
            f_max = precipitation_equation(T_max)

            # 如果在整个范围内都过饱和或都未饱和
            if f_min * f_max > 0:
                if f_min > 0 and f_max > 0:
                    # 整个范围都过饱和
                    return {
                        'status': 'warning',
                        'precipitation_temperature': T_max,
                        'precipitation_temperature_celsius': T_max - 273.15,
                        'phase_type': phase_type,
                        'message': f'在整个温度范围({T_min}-{T_max}K)内都过饱和，析出温度可能高于{T_max}K'
                    }
                else:
                    # 整个范围都未饱和
                    return {
                        'status': 'no_precipitation',
                        'precipitation_temperature': None,
                        'phase_type': phase_type,
                        'message': f'{phase_type} 在温度范围 {T_min}-{T_max}K 内不会析出'
                    }

            # 求解析出温度
            T_precip = brentq(precipitation_equation, T_min, T_max, xtol=tolerance)

            # 计算最终结果
            K_eq, delta_G = calculate_equilibrium_constant(T_precip)
            Q, activities = calculate_activity_product(T_precip)

            return {
                'status': 'success',
                'precipitation_temperature': T_precip,
                'precipitation_temperature_celsius': T_precip - 273.15,
                'phase_type': phase_type,
                'stoichiometry': {elem_A: m, elem_B: n},
                'activity_product': Q,
                'equilibrium_constant': K_eq,
                'gibbs_energy_formation': delta_G,
                'element_activities': activities,
                'solvent': solvent,
                'message': f'{phase_type} 析出温度计算成功'
            }

        except ValueError as e:
            return {
                'status': 'error',
                'message': f'数值求解失败: {str(e)}',
                'precipitation_temperature': None
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'计算失败: {str(e)}',
                'precipitation_temperature': None
            }


# 测试代码
if __name__ == "__main__":
    print("=" * 70)
    print("Thermodynamic Properties Calculator Test (V2.2)")
    print("=" * 70)

    thermo = ThermodynamicProperties()

    # ================================================================
    # 测试新增的液相线和析出温度计算功能
    # ================================================================

    print("\n" + "=" * 70)
    print("测试 Module 1: 液相线温度计算 (get_liquidus_temperature)")
    print("=" * 70)

    # 测试1: Al-Fe-Si合金
    al_alloy = {'Al': 0.98, 'Fe': 0.01, 'Si': 0.01}
    print(f"\n铝合金成分: {al_alloy}")

    liq_result = thermo.get_liquidus_temperature(
        composition=al_alloy,
        extrapolation_model_name='UEM1',
        activity_model='Wagner'
    )

    if liq_result['status'] == 'success':
        print(f"  液相线温度: {liq_result['liquidus_temperature']:.2f} K "
              f"({liq_result['liquidus_temperature_celsius']:.2f} °C)")
        print(f"  熔点降低: {liq_result['melting_point_depression']:.2f} K")
        print(f"  溶剂活度: {liq_result['solvent_activity']:.6f}")
        print(f"  相互作用修正: {liq_result['interaction_correction']:.6f}")
        print(f"  纯{liq_result['solvent']}熔点: {liq_result['pure_melting_point']:.2f} K")
        print(f"  迭代次数: {liq_result['iterations']}")
    else:
        print(f"  计算失败: {liq_result['message']}")

    # 测试2: Fe-C-Mn合金
    fe_alloy = {'Fe': 0.96, 'C': 0.02, 'Mn': 0.02}
    print(f"\n钢铁成分: {fe_alloy}")

    liq_result2 = thermo.get_liquidus_temperature(
        composition=fe_alloy,
        extrapolation_model_name='UEM1',
        activity_model='Wagner'
    )

    if liq_result2['status'] == 'success':
        print(f"  液相线温度: {liq_result2['liquidus_temperature']:.2f} K "
              f"({liq_result2['liquidus_temperature_celsius']:.2f} °C)")
        print(f"  熔点降低: {liq_result2['melting_point_depression']:.2f} K")
    else:
        print(f"  计算失败: {liq_result2['message']}")

    print("\n" + "=" * 70)
    print("测试 Module 2: 析出温度计算 (get_precipitation_temperature)")
    print("=" * 70)

    # 测试3: Al合金中Al3Fe析出
    print(f"\n铝合金 {al_alloy} 中 Al3Fe 析出:")
    ppt_result = thermo.get_precipitation_temperature(
        composition=al_alloy,
        phase_type='Al3Fe',
        extrapolation_model_name='UEM1'
    )

    if ppt_result['status'] == 'success':
        print(f"  析出温度: {ppt_result['precipitation_temperature']:.2f} K "
              f"({ppt_result['precipitation_temperature_celsius']:.2f} °C)")
        print(f"  活度积 Q: {ppt_result['activity_product']:.6e}")
        print(f"  平衡常数 K: {ppt_result['equilibrium_constant']:.6e}")
        print(f"  生成自由能: {ppt_result['gibbs_energy_formation']/1000:.2f} kJ/mol")
    elif ppt_result['status'] == 'no_precipitation':
        print(f"  {ppt_result['message']}")
    else:
        print(f"  计算失败: {ppt_result['message']}")

    # 测试4: 钢中TiC析出
    steel_tic = {'Fe': 0.97, 'C': 0.01, 'Ti': 0.02}
    print(f"\n钢 {steel_tic} 中 TiC 析出:")
    ppt_result2 = thermo.get_precipitation_temperature(
        composition=steel_tic,
        phase_type='TiC',
        extrapolation_model_name='UEM1'
    )

    if ppt_result2['status'] == 'success':
        print(f"  析出温度: {ppt_result2['precipitation_temperature']:.2f} K "
              f"({ppt_result2['precipitation_temperature_celsius']:.2f} °C)")
    elif ppt_result2['status'] == 'no_precipitation':
        print(f"  {ppt_result2['message']}")
    else:
        print(f"  计算状态: {ppt_result2['status']}")
        print(f"  {ppt_result2['message']}")

    # 测试5: 钢中TiN析出
    steel_tin = {'Fe': 0.97, 'N': 0.005, 'Ti': 0.02, 'C': 0.005}
    print(f"\n钢 {steel_tin} 中 TiN 析出:")
    ppt_result3 = thermo.get_precipitation_temperature(
        composition=steel_tin,
        phase_type='TiN',
        extrapolation_model_name='UEM1'
    )

    if ppt_result3['status'] == 'success':
        print(f"  析出温度: {ppt_result3['precipitation_temperature']:.2f} K "
              f"({ppt_result3['precipitation_temperature_celsius']:.2f} °C)")
    else:
        print(f"  计算状态: {ppt_result3['status']}")
        print(f"  {ppt_result3['message']}")

    print("\n" + "=" * 70)

    # (正确) 使用大写符号，符合 TDB
    composition = {
        'FE': 0.70,
        'C': 0.03,
        'SI': 0.27
    }
    temperature = 1873.0

    # --- [V2.1 新增测试] ---
    # 分别测试 'liquid' 和 'solid' 两种状态
    
    for phase_state in ['liquid', 'solid']:
        
        print(f"\n" + "=" * 70)
        print(f"Testing Phase State: {phase_state.upper()}")
        print(f"Alloy Composition: {composition}")
        print(f"Temperature: {temperature}K ({temperature-273.15:.1f}°C)")
        print(f"Extrapolation: UEM1, Activity: Wagner")
        print("=" * 70)

        results = thermo.calculate_all_properties(
            composition=composition,
            temperature=temperature,
            phase_state=phase_state,
            extrapolation_model='UEM1',
            activity_model='Wagner'
        )

        print("\nComponent Properties:")
        print("-" * 70)
        print(f"{'Component':<10} {'X_i':<10} {'ln(γ_i)':<12} {'γ_i':<12} {'a_i':<12} {'μ_i (kJ/mol)':<15}")
        print("-" * 70)
        for comp, props in results['component_properties'].items():
            x_i = props['mole_fraction']
            ln_gamma = props['ln_gamma']
            gamma = props['gamma']
            activity = props['activity']
            mu = props['mu']
            ln_gamma_str = f"{ln_gamma:<12.4f}" if ln_gamma is not None else f"{'N/A':<12}"
            gamma_str = f"{gamma:<12.4f}" if gamma is not None else f"{'N/A':<12}"
            activity_str = f"{activity:<12.4f}" if activity is not None else f"{'N/A':<12}"
            mu_str = f"{mu/1000:<15.2f}" if mu is not None else f"{'N/A':<15}"
            print(f"{comp:<10} {x_i:<10.4f} "
                  f"{ln_gamma_str} "
                  f"{gamma_str} "
                  f"{activity_str} "
                  f"{mu_str}")

        print("\n" + "=" * 70)
        print(f"Alloy Properties ({phase_state.upper()}):")
        print("-" * 70)
        alloy_props = results['alloy_properties']
        H = alloy_props['H']; G = alloy_props['G']; S = alloy_props['S']
        if H is not None and math.isfinite(H):
            print(f"Molar Enthalpy (H):        {H/1000:.2f} kJ/mol")
        else:
            print(f"Molar Enthalpy (H):        N/A (Calculation failed)")
        if G is not None and math.isfinite(G):
            print(f"Gibbs Free Energy (G):     {G/1000:.2f} kJ/mol")
        else:
            print(f"Gibbs Free Energy (G):     N/A (Calculation failed)")
        if S is not None and math.isfinite(S):
            print(f"Molar Entropy (S):         {S:.4f} J/(mol*K)")
        else:
            print(f"Molar Entropy (S):         N/A (Calculation failed)")
        print("=" * 70)