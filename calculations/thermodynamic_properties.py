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

        Args:
            composition: 成分字典 {'FE': 0.7, 'C': 0.03, 'SI': 0.27}
            component: 要计算的组分
            temperature: 温度 (K)
            phase_state: 相态 ('liquid' 或 'solid')
            solvent: 溶剂（如果为None，自动选择含量最高的组分）
            extrapolation_model: 外推模型
            activity_model: 活度模型

        Returns:
            活度 a_i
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

        Args:
            composition: 成分字典
            component: 要计算的组分
            temperature: 温度 (K)
            phase_state: 相态
            solvent: 溶剂
            extrapolation_model: 外推模型
            activity_model: 活度模型

        Returns:
            ln(γ_i)
        """
        # 确定溶剂
        if solvent is None:
            solvent = max(composition.items(), key=lambda x: x[1])[0]

        # 设置活度计算器（直接设置内部字典）
        self.activity_calculator._comp_dict = composition.copy()

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
            ln_gamma = self.activity_calculator.get_ln_gamma(
                comp_dict=composition,
                component_to_calculate=component,
                solvent=solvent,
                Tem=temperature,
                state=phase_state,
                extra_model=extrap_func,
                extra_model_name=extrapolation_model,
                activity_model=activity_model
            )
            return ln_gamma
        except Exception as e:
            print(f"Error calculating ln(γ) for {component}: {e}")
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
        其中 μ°_i(T) = G°_i(T) (纯物质的摩尔Gibbs能)

        Args:
            composition: 成分字典
            component: 要计算的组分
            temperature: 温度 (K)
            phase_state: 相态
            solvent: 溶剂
            extrapolation_model: 外推模型
            activity_model: 活度模型

        Returns:
            化学势 μ_i (J/mol)
        """
        # 1. 获取纯物质的Gibbs能 μ°_i(T)
        phase_map = {
            'liquid': 'LIQUID',
            'solid': 'SER',  # 使用标准态
        }
        tdb_phase = phase_map.get(phase_state.lower(), 'LIQUID')

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

        其中:
        - H°_i: 纯组分i的摩尔焓（从TDB）
        - H^E: 过剩焓（混合焓，从Miedema模型）

        Args:
            composition: 成分字典
            temperature: 温度 (K)
            phase_state: 相态
            extrapolation_model: 外推模型（用于计算H^E）

        Returns:
            摩尔焓 H (J/mol)
        """
        # 1. 理想混合焓: Σ(X_i * H°_i)
        H_ideal = 0.0
        phase_map = {
            'liquid': 'LIQUID',
            'solid': 'SER',
        }
        tdb_phase = phase_map.get(phase_state.lower(), 'LIQUID')

        for component, x_i in composition.items():
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
            # 如果无法计算过剩焓，仅返回理想项
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

        G_alloy = Σ(X_i * G°_i) + RT * Σ(X_i * ln(a_i))
                = Σ(X_i * μ_i)

        Args:
            composition: 成分字典
            temperature: 温度 (K)
            phase_state: 相态
            solvent: 溶剂
            extrapolation_model: 外推模型
            activity_model: 活度模型

        Returns:
            Gibbs能 G (J/mol)
        """
        G_total = 0.0

        for component, x_i in composition.items():
            # 计算每个组分的化学势
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

        或者: S = Σ(X_i * S°_i) + S^config + S^E

        Args:
            composition: 成分字典
            temperature: 温度 (K)
            phase_state: 相态
            solvent: 溶剂
            extrapolation_model: 外推模型
            activity_model: 活度模型

        Returns:
            摩尔熵 S (J/(mol*K))
        """
        # 方法1: 从 S = (H - G) / T 计算
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

        S = (H - G) / temperature

        return S

    def _calculate_excess_enthalpy(self,
                                   composition: Dict[str, float],
                                   temperature: float,
                                   phase_state: str = 'liquid',
                                   extrapolation_model: str = 'UEM1') -> Optional[float]:
        """
        使用Miedema模型计算过剩焓（混合焓）

        对于多元体系:
        H^E = ΣΣ X_i X_j H_ij + 高阶项

        Args:
            composition: 成分字典
            temperature: 温度 (K)
            phase_state: 相态
            extrapolation_model: 外推模型

        Returns:
            过剩焓 H^E (J/mol)
        """
        try:
            components = list(composition.keys())
            n = len(components)

            # 如果是纯物质，过剩焓为0
            if n == 1:
                return 0.0

            # 二元体系：直接使用Miedema模型
            if n == 2:
                elem_a = components[0]
                elem_b = components[1]
                x_a = composition[elem_a]
                x_b = composition[elem_b]

                # 使用BinaryModel计算
                self.binary_model.set_state(phase_state)
                self.binary_model.set_temperature(temperature)

                H_mix = self.binary_model.binary_model(
                    a=elem_a,
                    b=elem_b,
                    xa=x_a,
                    xb=x_b
                )

                return H_mix

            # 三元及以上体系：使用外推方法
            # 简化计算：所有二元对的加权和（Muggianu对称外推）
            H_excess = 0.0

            for i in range(n):
                for j in range(i+1, n):
                    elem_i = components[i]
                    elem_j = components[j]
                    x_i = composition[elem_i]
                    x_j = composition[elem_j]

                    if x_i > 0 and x_j > 0:
                        # 计算二元混合焓
                        self.binary_model.set_state(phase_state)
                        self.binary_model.set_temperature(temperature)

                        # 归一化到二元体系
                        x_sum = x_i + x_j
                        x_i_norm = x_i / x_sum
                        x_j_norm = x_j / x_sum

                        H_ij = self.binary_model.binary_model(
                            a=elem_i,
                            b=elem_j,
                            xa=x_i_norm,
                            xb=x_j_norm
                        )

                        # 加权贡献（Muggianu）
                        H_excess += x_i * x_j * H_ij / x_sum

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

        Args:
            composition: 成分字典
            temperature: 温度 (K)
            phase_state: 相态
            solvent: 溶剂
            extrapolation_model: 外推模型
            activity_model: 活度模型

        Returns:
            结果字典，格式:
            {
                'component_properties': {
                    'FE': {'ln_gamma': ..., 'gamma': ..., 'activity': ..., 'mu': ...},
                    'C': {...},
                    ...
                },
                'alloy_properties': {
                    'H': ...,  # 摩尔焓
                    'G': ...,  # Gibbs能
                    'S': ...,  # 熵
                    'T': ...,  # 温度
                    'phase': ...,  # 相态
                }
            }
        """
        results = {
            'component_properties': {},
            'alloy_properties': {}
        }

        # 计算每个组分的性质
        for component in composition.keys():
            comp_results = {}

            # 活度系数
            ln_gamma = self.calculate_ln_activity_coefficient(
                composition, component, temperature, phase_state,
                solvent, extrapolation_model, activity_model
            )
            comp_results['ln_gamma'] = ln_gamma
            comp_results['gamma'] = math.exp(ln_gamma) if ln_gamma is not None else None

            # 活度
            activity = self.calculate_activity(
                composition, component, temperature, phase_state,
                solvent, extrapolation_model, activity_model
            )
            comp_results['activity'] = activity

            # 化学势
            mu = self.calculate_chemical_potential(
                composition, component, temperature, phase_state,
                solvent, extrapolation_model, activity_model
            )
            comp_results['mu'] = mu

            # 摩尔分数
            comp_results['mole_fraction'] = composition[component]

            results['component_properties'][component] = comp_results

        # 计算合金整体性质
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


# 测试代码
if __name__ == "__main__":
    print("=" * 70)
    print("Thermodynamic Properties Calculator Test")
    print("=" * 70)

    # 创建计算器
    thermo = ThermodynamicProperties()

    # 测试成分：Fe-C-Si合金 (类似钢)
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

        print(f"{comp:<10} {x_i:<10.4f} "
              f"{ln_gamma if ln_gamma else 'N/A':<12} "
              f"{gamma if gamma else 'N/A':<12} "
              f"{activity if activity else 'N/A':<12} "
              f"{mu/1000 if mu else 'N/A':<15}")

    # 显示合金性质
    print("\n" + "=" * 70)
    print("Alloy Properties:")
    print("-" * 70)

    alloy_props = results['alloy_properties']
    H = alloy_props['H']
    G = alloy_props['G']
    S = alloy_props['S']

    if H is not None:
        print(f"Molar Enthalpy (H):        {H/1000:.2f} kJ/mol")
    if G is not None:
        print(f"Gibbs Free Energy (G):     {G/1000:.2f} kJ/mol")
    if S is not None:
        print(f"Molar Entropy (S):         {S:.4f} J/(mol*K)")
    if H is not None and S is not None:
        print(f"T*S:                       {temperature*S/1000:.2f} kJ/mol")
    if H is not None and G is not None:
        print(f"H - G:                     {(H-G)/1000:.2f} kJ/mol")

    print("=" * 70)
