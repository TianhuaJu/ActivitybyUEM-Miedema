"""
Thermodynamic Properties Calculator
====================================
计算多组元合金的完整热力学性质

基于:
1. TDB数据库的纯物质性质
2. Miedema模型的混合项
3. 活度系数计算

计算性质:
- 活度 (Activity)
- 化学势 (Chemical Potential)
- 摩尔焓 (Molar Enthalpy)
- 吉布斯自由能 (Gibbs Free Energy)
- 摩尔熵 (Molar Entropy)
- 摩尔体积 (Molar Volume)

作者: Claude
日期: 2025-11-08
"""

import math
from typing import Dict, Optional, Tuple, List
import sys
import os

# (注意：相图计算所需的 'from scipy.optimize import root' 已被移除)

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tdb_parser import get_tdb_parser, TDBParser
from core.constants import Constants


class ThermodynamicProperties:
    """多组元合金热力学性质计算器"""

    def __init__(self):
        """初始化热力学性质计算器"""
        self.tdb_parser: TDBParser = get_tdb_parser()

        # 延迟导入以避免循环依赖
        from calculations.activity_calculator import ActivityCoefficient
        from models.extrapolation_models import BinaryModel

        self.activity_calculator = ActivityCoefficient()
        self.binary_model = BinaryModel()

        # 常数
        self.R = Constants.R  # J/(mol*K)

    # ================================================================
    # =================== 符号转换辅助函数 ===================
    # ================================================================
    @staticmethod
    def _to_standard_symbol(symbol: str) -> str:
        """
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
                          phase_state: str = 'liquid',
                          solvent: str = None,
                          extrapolation_model: str = 'UEM1',
                          activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算组分的活度
        a_i = γ_i * X_i
        """
        # 获取活度系数
        ln_gamma = self.calculate_ln_activity_coefficient(
            composition=composition,
            component=component,
            temperature=temperature,
            phase_state=phase_state,
            solvent=solvent,
            extrapolation_model=extrapolation_model,
            activity_model=activity_model
        )

        if ln_gamma is None:
            return None

        gamma = math.exp(ln_gamma)

        # 获取摩尔分数
        x_i = composition.get(component, 0.0)

        # 计算活度
        activity = gamma * x_i

        return activity

    def calculate_ln_activity_coefficient(self,
                                         composition: Dict[str, float],
                                         component: str,
                                         temperature: float,
                                         phase_state: str = 'liquid',
                                         solvent: str = None,
                                         extrapolation_model: str = 'UEM1',
                                         activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算活度系数的对数 ln(γ_i)
        
        修正：此函数现在充当翻译器，
        将大写符号 (FE) 转换为标准符号 (Fe) 后再传递给 activity_calculator。
        """
        # 1. 确定溶剂 (仍然使用大写符号) - 添加验证以避免错误
        if solvent is None:
            if not composition:
                raise ValueError("Composition dictionary is empty")

            # 过滤掉摩尔分数为0或负数的组分
            valid_components = {k: v for k, v in composition.items() if v > 0}
            if not valid_components:
                raise ValueError("No valid components with positive mole fractions")

            # 自动选择含量最大的组分
            solvent = max(valid_components.items(), key=lambda x: x[1])[0]

        # 2. --- (修正: 转换为标准符号) ---
        #    这是 Miedema/Activity 计算栈所需要的
        try:
            comp_dict_std = {self._to_standard_symbol(k): v for k, v in composition.items()}
            component_std = self._to_standard_symbol(component)
            solvent_std = self._to_standard_symbol(solvent)
        except Exception as e:
            print(f"Error standardizing symbols: {e}")
            return None
        # --- (修正结束) ---

        # 设置活度计算器（直接设置内部字典）
        self.activity_calculator._comp_dict = comp_dict_std.copy()

        # 选择外推模型函数
        from models.extrapolation_models import BinaryModel
        bm = BinaryModel()

        extrap_func_map = {
            'UEM1': bm.UEM1,
            'UEM2': bm.UEM2,
            'UEM2-Adv': bm.UEM2_Adv,
            'GSM': bm.GSM,
            'Muggianu': bm.Muggianu,
            'Toop-Kohler': bm.Toop_Kohler,
            'Toop-Muggianu': bm.Toop_Muggianu,
        }

        extrap_func = extrap_func_map.get(extrapolation_model, bm.UEM1)

        try:
            # 3. 使用标准符号 (Fe, C, Si) 调用 get_ln_gamma
            ln_gamma = self.activity_calculator.get_ln_gamma(
                comp_dict=comp_dict_std,
                component_to_calculate=component_std,
                solvent=solvent_std,
                Tem=temperature,
                state=phase_state,
                extra_model=extrap_func,
                extra_model_name=extrapolation_model,
                activity_model=activity_model
            )
            return ln_gamma
        except Exception as e:
            # 使用两个符号进行日志记录，以方便调试
            print(f"Error calculating ln(γ) for {component} (as {component_std}): {e}")
            return None

    def calculate_chemical_potential(self,
                                     composition: Dict[str, float],
                                     component: str,
                                     temperature: float,
                                     phase_state: str = 'liquid',
                                     solvent: str = None,
                                     extrapolation_model: str = 'UEM1',
                                     activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算化学势
        μ_i = μ°_i(T) + RT ln(a_i)
        """
        # 1. 获取纯物质的Gibbs能 μ°_i(T)
        phase_map = {
            'liquid': 'LIQUID',
            'solid': 'SER',  # 使用标准态
        }
        tdb_phase = phase_map.get(phase_state.lower(), 'LIQUID')

        # (正确) 使用大写符号 (FE) 调用 TDB 解析器
        mu_0 = self.tdb_parser.get_gibbs_energy(component, tdb_phase, temperature)
        if mu_0 is None:
            print(f"Warning: Could not find G° for {component} in {tdb_phase} phase")
            return None

        # 2. 计算活度
        activity = self.calculate_activity(
            composition=composition,
            component=component,
            temperature=temperature,
            phase_state=phase_state,
            solvent=solvent,
            extrapolation_model=extrapolation_model,
            activity_model=activity_model
        )

        if activity is None or activity <= 0:
            return None

        # 3. 计算化学势
        mu = mu_0 + self.R * temperature * math.log(activity)

        return mu

    def calculate_molar_enthalpy(self,
                                 composition: Dict[str, float],
                                 temperature: float,
                                 phase_state: str = 'liquid',
                                 extrapolation_model: str = 'UEM1') -> Optional[float]:
        """
        计算合金的摩尔焓
        H_alloy = Σ(X_i * H°_i) + H^E
        """
        # 1. 理想混合焓: Σ(X_i * H°_i)
        H_ideal = 0.0
        phase_map = {
            'liquid': 'LIQUID',
            'solid': 'SER',
        }
        tdb_phase = phase_map.get(phase_state.lower(), 'LIQUID')

        for component, x_i in composition.items():
            # (正确) 使用大写符号 (FE) 调用 TDB 解析器
            H_i = self.tdb_parser.get_enthalpy(component, tdb_phase, temperature)
            if H_i is None:
                print(f"Warning: Could not find H° for {component}")
                return None
            H_ideal += x_i * H_i

        # 2. 过剩焓 H^E (从Miedema模型)
        H_excess = self._calculate_excess_enthalpy(
            composition=composition,
            temperature=temperature,
            phase_state=phase_state,
            extrapolation_model=extrapolation_model
        )

        if H_excess is None:
            print("Warning: Could not calculate excess enthalpy, using ideal mixing only")
            H_excess = 0.0

        # 3. 总焓
        H_total = H_ideal + H_excess

        return H_total

    def calculate_gibbs_energy(self,
                               composition: Dict[str, float],
                               temperature: float,
                               phase_state: str = 'liquid',
                               solvent: str = None,
                               extrapolation_model: str = 'UEM1',
                               activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算合金的摩尔Gibbs自由能
        G_alloy = Σ(X_i * μ_i)
        """
        G_total = 0.0

        for component, x_i in composition.items():
            # (正确) 使用大写符号 (FE) 调用，内部函数将处理转换
            mu_i = self.calculate_chemical_potential(
                composition=composition,
                component=component,
                temperature=temperature,
                phase_state=phase_state,
                solvent=solvent,
                extrapolation_model=extrapolation_model,
                activity_model=activity_model
            )

            if mu_i is None:
                return None

            G_total += x_i * mu_i

        return G_total

    def calculate_entropy(self,
                         composition: Dict[str, float],
                         temperature: float,
                         phase_state: str = 'liquid',
                         solvent: str = None,
                         extrapolation_model: str = 'UEM1',
                         activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算合金的摩尔熵
        S = (H - G) / T
        """
        H = self.calculate_molar_enthalpy(
            composition=composition,
            temperature=temperature,
            phase_state=phase_state,
            extrapolation_model=extrapolation_model
        )

        G = self.calculate_gibbs_energy(
            composition=composition,
            temperature=temperature,
            phase_state=phase_state,
            solvent=solvent,
            extrapolation_model=extrapolation_model,
            activity_model=activity_model
        )

        if H is None or G is None:
            return None
        
        if temperature == 0:
            return None # 避免除以零

        S = (H - G) / temperature

        return S

    def _calculate_excess_enthalpy(self,
                                   composition: Dict[str, float],
                                   temperature: float,
                                   phase_state: str = 'liquid',
                                   extrapolation_model: str = 'UEM1') -> Optional[float]:
        """
        使用Miedema模型计算过剩焓（混合焓）
        
        修正：此函数现在充当翻译器，
        将大写符号 (FE) 转换为标准符号 (Fe) 后再传递给 binary_model。
        """
        try:
            # --- (修正: 转换为标准符号) ---
            comp_std = {self._to_standard_symbol(k): v for k, v in composition.items()}
            components = list(comp_std.keys())
            # --- (修正结束) ---
            
            n = len(components)

            if n == 1:
                return 0.0

            if n == 2:
                elem_a = components[0] # 'Fe'
                elem_b = components[1] # 'C'
                x_a = comp_std[elem_a]
                x_b = comp_std[elem_b]

                self.binary_model.set_state(phase_state)
                self.binary_model.set_temperature(temperature)

                H_mix = self.binary_model.binary_model(
                    a=elem_a, # (正确) 传递 'Fe'
                    b=elem_b, # (正确) 传递 'C'
                    xa=x_a,
                    xb=x_b
                )
                return H_mix

            H_excess = 0.0
            for i in range(n):
                for j in range(i+1, n):
                    elem_i = components[i] # 'Fe'
                    elem_j = components[j] # 'C'
                    x_i = comp_std[elem_i]
                    x_j = comp_std[elem_j]

                    if x_i > 0 and x_j > 0:
                        self.binary_model.set_state(phase_state)
                        self.binary_model.set_temperature(temperature)

                        x_sum = x_i + x_j
                        if x_sum == 0: continue # 避免除以零
                        
                        x_i_norm = x_i / x_sum
                        x_j_norm = x_j / x_sum

                        H_ij = self.binary_model.binary_model(
                            a=elem_i, # (正确) 传递 'Fe'
                            b=elem_j, # (正确) 传递 'C'
                            xa=x_i_norm,
                            xb=x_j_norm
                        )
                        
                        if H_ij is not None and math.isfinite(H_ij):
                            H_excess += x_i * x_j * H_ij / x_sum
                        else:
                            print(f"Warning: H_ij for {elem_i}-{elem_j} was None or infinite, skipping.")


            return H_excess

        except Exception as e:
            print(f"Error calculating excess enthalpy: {e}")
            return None

    def calculate_all_properties(self,
                                 composition: Dict[str, float],
                                 temperature: float,
                                 phase_state: str = 'liquid',
                                 solvent: str = None,
                                 extrapolation_model: str = 'UEM1',
                                 activity_model: str = 'Wagner') -> Dict[str, Dict]:
        """
        计算所有热力学性质
        """
        results = {
            'component_properties': {},
            'alloy_properties': {}
        }

        # (正确) 所有调用都使用大写符号，内部函数会处理转换
        for component in composition.keys():
            comp_results = {}
            ln_gamma = self.calculate_ln_activity_coefficient(
                composition, component, temperature, phase_state,
                solvent, extrapolation_model, activity_model
            )
            comp_results['ln_gamma'] = ln_gamma
            comp_results['gamma'] = math.exp(ln_gamma) if ln_gamma is not None else None
            activity = self.calculate_activity(
                composition, component, temperature, phase_state,
                solvent, extrapolation_model, activity_model
            )
            comp_results['activity'] = activity
            mu = self.calculate_chemical_potential(
                composition, component, temperature, phase_state,
                solvent, extrapolation_model, activity_model
            )
            comp_results['mu'] = mu
            comp_results['mole_fraction'] = composition[component]
            results['component_properties'][component] = comp_results

        H = self.calculate_molar_enthalpy(
            composition, temperature, phase_state, extrapolation_model
        )
        results['alloy_properties']['H'] = H

        G = self.calculate_gibbs_energy(
            composition, temperature, phase_state, solvent,
            extrapolation_model, activity_model
        )
        results['alloy_properties']['G'] = G

        S = self.calculate_entropy(
            composition, temperature, phase_state, solvent,
            extrapolation_model, activity_model
        )
        results['alloy_properties']['S'] = S

        results['alloy_properties']['T'] = temperature
        results['alloy_properties']['phase'] = phase_state

        return results

    # --- (已移除: 液相线/固相线计算方法) ---


# 测试代码
if __name__ == "__main__":
    print("=" * 70)
    print("Thermodynamic Properties Calculator Test")
    print("=" * 70)

    # 创建计算器
    thermo = ThermodynamicProperties()

    # 测试成分：Fe-C-Si合金 (类似钢)
    # (正确) 使用大写符号，符合 TDB
    composition = {
        'FE': 0.70,
        'C': 0.03,
        'SI': 0.27
    }

    temperature = 1873.0  # K (1600°C)
    phase_state = 'liquid'

    print(f"\nAlloy Composition: {composition}")
    print(f"Temperature: {temperature}K ({temperature-273.15:.1f}°C)")
    print(f"Phase State: {phase_state}")
    print("\n" + "=" * 70)

    # 计算所有性质
    results = thermo.calculate_all_properties(
        composition=composition,
        temperature=temperature,
        phase_state=phase_state,
        extrapolation_model='UEM1',
        activity_model='Wagner'
    )

    # 显示组分性质
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

        # --- (修正: 格式化字符串以处理 None) ---
        ln_gamma_str = f"{ln_gamma:<12.4f}" if ln_gamma is not None else f"{'N/A':<12}"
        gamma_str = f"{gamma:<12.4f}" if gamma is not None else f"{'N/A':<12}"
        activity_str = f"{activity:<12.4f}" if activity is not None else f"{'N/A':<12}"
        mu_str = f"{mu/1000:<15.2f}" if mu is not None else f"{'N/A':<15}"

        print(f"{comp:<10} {x_i:<10.4f} "
              f"{ln_gamma_str} "
              f"{gamma_str} "
              f"{activity_str} "
              f"{mu_str}")
        # --- (修正结束) ---

    # 显示合金性质
    print("\n" + "=" * 70)
    print("Alloy Properties:")
    print("-" * 70)

    alloy_props = results['alloy_properties']
    H = alloy_props['H']
    G = alloy_props['G']
    S = alloy_props['S']

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
    
    # --- (已移除: 液相线/固相线测试代码) ---