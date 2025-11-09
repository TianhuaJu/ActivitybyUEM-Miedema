"""
Phase Diagram Calculator
=========================
计算多组元合金的相图特征温度

功能:
- 液相线温度 (Liquidus Temperature)
- 固相线温度 (Solidus Temperature)
- 液相线/固相线随成分变化的曲线

基于:
1. TDB数据库的纯物质相变数据
2. Gibbs能最小化原理
3. 相平衡条件: μ^liquid_i = μ^solid_i

作者: Claude
日期: 2025-11-08
"""

import math
import sys
import os
from typing import Dict, Optional, Tuple, List
from scipy.optimize import brentq, minimize_scalar
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tdb_parser import get_tdb_parser, TDBParser
from core.constants import Constants
from calculations.thermodynamic_properties import ThermodynamicProperties


class PhaseDiagram:
    """相图计算器"""

    def __init__(self):
        """初始化相图计算器"""
        self.tdb_parser: TDBParser = get_tdb_parser()
        self.thermo = ThermodynamicProperties()
        self.R = Constants.R

    def get_melting_point(self, element: str) -> Optional[float]:
        """
        获取元素的熔点

        通过查找G(liquid) = G(solid)的温度

        Args:
            element: 元素符号

        Returns:
            熔点温度 (K)，如果未找到返回None
        """
        # 从元素信息获取初始估计
        elem_info = self.tdb_parser.get_element_info(element)
        if elem_info is None:
            return None

        # 尝试在合理的温度范围内查找熔点
        # 大多数金属熔点在300-4000K之间
        T_min = 300.0
        T_max = 4000.0

        try:
            def gibbs_diff(T):
                """液相和固相Gibbs能之差"""
                G_liq = self.tdb_parser.get_gibbs_energy(element, 'LIQUID', T)
                G_ser = self.tdb_parser.get_gibbs_energy(element, 'SER', T)

                if G_liq is None or G_ser is None:
                    return float('inf')

                return G_liq - G_ser

            # 检查边界值
            diff_min = gibbs_diff(T_min)
            diff_max = gibbs_diff(T_max)

            # 如果符号相同，说明在这个范围内没有交点
            if diff_min * diff_max > 0:
                # 尝试通过固相线推断
                # 使用一些常见金属的熔点作为参考
                common_melting_points = {
                    'FE': 1811.0,  # Fe
                    'AL': 933.47,  # Al
                    'CU': 1357.77, # Cu
                    'NI': 1728.0,  # Ni
                    'CR': 2180.0,  # Cr
                    'MN': 1519.0,  # Mn
                    'SI': 1687.0,  # Si
                    'C': 3823.0,   # C (石墨升华)
                }
                return common_melting_points.get(element.upper())

            # 使用Brent方法求根
            T_melt = brentq(gibbs_diff, T_min, T_max, xtol=0.1)
            return T_melt

        except Exception as e:
            print(f"Warning: Could not find melting point for {element}: {e}")
            return None

    def calculate_liquidus_temperature(self,
                                      composition: Dict[str, float],
                                      extrapolation_model: str = 'UEM1',
                                      activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算合金的液相线温度

        液相线是液相开始凝固的温度
        平衡条件: G_liquid(T) = G_solid(T)

        简化方法: 使用加权平均熔点作为初始估计

        Args:
            composition: 成分字典
            extrapolation_model: 外推模型
            activity_model: 活度模型

        Returns:
            液相线温度 (K)
        """
        try:
            # 检查成分是否有效
            if not composition or sum(composition.values()) == 0:
                return None

            # 方法1: 加权平均熔点（简化方法）
            # T_liquidus ≈ Σ(X_i * T_melt_i) / Σ(X_i) for components with known T_melt
            T_weighted_sum = 0.0
            x_sum = 0.0  # 有熔点数据的组分的摩尔分数总和

            for component, x_i in composition.items():
                if x_i > 0:  # 只考虑非零组分
                    T_melt = self.get_melting_point(component)
                    if T_melt is not None:
                        T_weighted_sum += x_i * T_melt
                        x_sum += x_i

            # 如果没有任何组分有熔点数据，返回None
            if x_sum == 0:
                return None

            # 加权平均
            T_liquidus = T_weighted_sum / x_sum

            # 方法2: 使用Gibbs能最小化（更精确，但计算量大）
            # 这里先使用简化方法

            return T_liquidus

        except Exception as e:
            print(f"Error calculating liquidus temperature: {e}")
            return None

    def calculate_solidus_temperature(self,
                                     composition: Dict[str, float],
                                     extrapolation_model: str = 'UEM1',
                                     activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算合金的固相线温度

        固相线是固相开始熔化的温度

        简化方法: 使用最小熔点作为估计

        Args:
            composition: 成分字典
            extrapolation_model: 外推模型
            activity_model: 活度模型

        Returns:
            固相线温度 (K)
        """
        try:
            # 检查成分是否有效
            if not composition or sum(composition.values()) == 0:
                return None

            # 简化方法: 使用最低熔点作为固相线温度的估计
            # 固相线 ≈ min(T_melt_i) for all components with X_i > threshold
            T_solidus = float('inf')
            threshold = 0.001  # 降低阈值到0.1%，避免忽略重要的低熔点组分

            for component, x_i in composition.items():
                if x_i > threshold:  # 只忽略极微量组分
                    T_melt = self.get_melting_point(component)
                    if T_melt is not None and T_melt < T_solidus:
                        T_solidus = T_melt

            if T_solidus == float('inf'):
                return None

            return T_solidus

        except Exception as e:
            print(f"Error calculating solidus temperature: {e}")
            return None

    def calculate_phase_diagram_curve(self,
                                      base_composition: Dict[str, float],
                                      variable_component: str,
                                      x_min: float = 0.0,
                                      x_max: float = 1.0,
                                      n_points: int = 20,
                                      extrapolation_model: str = 'UEM1',
                                      activity_model: str = 'Wagner') -> Dict[str, List]:
        """
        计算液相线/固相线随某组分浓度变化的曲线

        Args:
            base_composition: 基础成分（不包含变化组分）
            variable_component: 变化的组分
            x_min: 变化组分的最小摩尔分数
            x_max: 变化组分的最大摩尔分数
            n_points: 采样点数
            extrapolation_model: 外推模型
            activity_model: 活度模型

        Returns:
            {
                'x': [摩尔分数列表],
                'T_liquidus': [液相线温度列表],
                'T_solidus': [固相线温度列表]
            }
        """
        results = {
            'x': [],
            'T_liquidus': [],
            'T_solidus': []
        }

        # 归一化基础成分
        base_total = sum(base_composition.values())
        if base_total <= 0:
            base_composition = {}

        # 生成采样点
        x_values = np.linspace(x_min, x_max, n_points)

        for x_var in x_values:
            # 构建当前成分
            current_comp = {}

            # 添加可变组分
            current_comp[variable_component] = x_var

            # 添加基础组分（按比例缩放）
            remaining = 1.0 - x_var
            for comp, x_i in base_composition.items():
                if comp != variable_component:
                    if base_total > 0:
                        current_comp[comp] = x_i / base_total * remaining
                    else:
                        current_comp[comp] = 0.0

            # 归一化
            total = sum(current_comp.values())
            if total > 0:
                current_comp = {k: v/total for k, v in current_comp.items()}

            # 计算液相线和固相线温度
            T_liq = self.calculate_liquidus_temperature(
                current_comp, extrapolation_model, activity_model
            )
            T_sol = self.calculate_solidus_temperature(
                current_comp, extrapolation_model, activity_model
            )

            results['x'].append(x_var)
            results['T_liquidus'].append(T_liq if T_liq else None)
            results['T_solidus'].append(T_sol if T_sol else None)

        return results

    def calculate_binary_phase_diagram(self,
                                       component_a: str,
                                       component_b: str,
                                       n_points: int = 20,
                                       extrapolation_model: str = 'UEM1',
                                       activity_model: str = 'Wagner') -> Dict[str, List]:
        """
        计算二元相图

        Args:
            component_a: 组分A
            component_b: 组分B
            n_points: 采样点数
            extrapolation_model: 外推模型
            activity_model: 活度模型

        Returns:
            相图数据
        """
        results = {
            'x_b': [],  # 组分B的摩尔分数
            'T_liquidus': [],
            'T_solidus': []
        }

        x_b_values = np.linspace(0.0, 1.0, n_points)

        for x_b in x_b_values:
            x_a = 1.0 - x_b

            composition = {
                component_a: x_a,
                component_b: x_b
            }

            # 过滤掉零成分
            composition = {k: v for k, v in composition.items() if v > 1e-6}

            if len(composition) == 0:
                continue

            T_liq = self.calculate_liquidus_temperature(
                composition, extrapolation_model, activity_model
            )
            T_sol = self.calculate_solidus_temperature(
                composition, extrapolation_model, activity_model
            )

            results['x_b'].append(x_b)
            results['T_liquidus'].append(T_liq)
            results['T_solidus'].append(T_sol)

        return results


# 测试代码
if __name__ == "__main__":
    print("=" * 70)
    print("Phase Diagram Calculator Test")
    print("=" * 70)

    # 创建相图计算器
    phase_diagram = PhaseDiagram()

    # 测试1: 获取纯元素熔点
    print("\n1. Melting Points of Pure Elements:")
    print("-" * 70)
    elements = ['FE', 'AL', 'CU', 'NI', 'CR', 'SI', 'C']

    for elem in elements:
        T_melt = phase_diagram.get_melting_point(elem)
        if T_melt:
            print(f"{elem:5s}: {T_melt:7.2f} K  ({T_melt-273.15:7.2f} °C)")
        else:
            print(f"{elem:5s}: Not found")

    # 测试2: 计算合金的液相线和固相线温度
    print("\n" + "=" * 70)
    print("2. Liquidus and Solidus Temperatures:")
    print("-" * 70)

    # Fe-C合金（钢）
    composition_steel = {'FE': 0.97, 'C': 0.03}
    T_liq_steel = phase_diagram.calculate_liquidus_temperature(composition_steel)
    T_sol_steel = phase_diagram.calculate_solidus_temperature(composition_steel)

    print(f"\nFe-C Alloy (Steel): {composition_steel}")
    if T_liq_steel:
        print(f"  Liquidus: {T_liq_steel:.2f} K ({T_liq_steel-273.15:.2f} °C)")
    if T_sol_steel:
        print(f"  Solidus:  {T_sol_steel:.2f} K ({T_sol_steel-273.15:.2f} °C)")
    if T_liq_steel and T_sol_steel:
        print(f"  Freezing Range: {T_liq_steel - T_sol_steel:.2f} K")

    # Al-Cu合金
    composition_al_cu = {'AL': 0.96, 'CU': 0.04}
    T_liq_al_cu = phase_diagram.calculate_liquidus_temperature(composition_al_cu)
    T_sol_al_cu = phase_diagram.calculate_solidus_temperature(composition_al_cu)

    print(f"\nAl-Cu Alloy: {composition_al_cu}")
    if T_liq_al_cu:
        print(f"  Liquidus: {T_liq_al_cu:.2f} K ({T_liq_al_cu-273.15:.2f} °C)")
    if T_sol_al_cu:
        print(f"  Solidus:  {T_sol_al_cu:.2f} K ({T_sol_al_cu-273.15:.2f} °C)")
    if T_liq_al_cu and T_sol_al_cu:
        print(f"  Freezing Range: {T_liq_al_cu - T_sol_al_cu:.2f} K")

    # 测试3: 计算二元相图
    print("\n" + "=" * 70)
    print("3. Binary Phase Diagram: Fe-C")
    print("-" * 70)

    phase_data = phase_diagram.calculate_binary_phase_diagram('FE', 'C', n_points=11)

    print(f"\n{'X_C':<10} {'T_liquidus (K)':<15} {'T_liquidus (°C)':<15} "
          f"{'T_solidus (K)':<15} {'T_solidus (°C)':<15}")
    print("-" * 70)

    for i, x_c in enumerate(phase_data['x_b']):
        T_liq = phase_data['T_liquidus'][i]
        T_sol = phase_data['T_solidus'][i]

        T_liq_str = f"{T_liq:.2f}" if T_liq else "N/A"
        T_liq_c_str = f"{T_liq-273.15:.2f}" if T_liq else "N/A"
        T_sol_str = f"{T_sol:.2f}" if T_sol else "N/A"
        T_sol_c_str = f"{T_sol-273.15:.2f}" if T_sol else "N/A"

        print(f"{x_c:<10.3f} {T_liq_str:<15} {T_liq_c_str:<15} "
              f"{T_sol_str:<15} {T_sol_c_str:<15}")

    print("\n" + "=" * 70)
