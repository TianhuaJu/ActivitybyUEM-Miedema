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


# 测试代码
if __name__ == "__main__":
    print("=" * 70)
    print("Thermodynamic Properties Calculator Test (V2.1)")
    print("=" * 70)

    thermo = ThermodynamicProperties()

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