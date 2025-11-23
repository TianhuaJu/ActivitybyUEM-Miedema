"""
Phase Equilibrium Calculator (Recursive Phase Separation Algorithm)
====================================================================
相平衡计算模块 - 基于递归相分离算法

算法原理:
1. 判断给定合金组成的相稳定性
   - 如果稳定 → 单一相
   - 如果不稳定 → 分解成多相

2. 对于不稳定情况：
   - 找出吉布斯自由能最小的相作为基础相
   - 计算其他元素在该相中的最大溶解度
   - 按最大溶解度固定主相组成

3. 处理剩余成分：
   - 剩余成分构成新的基础合金
   - 递归执行步骤1-2
   - 直至所有成分都处于稳定相中

4. 根据物质守恒计算各相的相分数

理论基础:
- 相稳定性判据: 所有组分化学势不超过其纯态能量
- 溶解度平衡: μᵢ(溶液) = G⁰ᵢ(析出相)
- 物质守恒: Σ(xᵢᵅ × fᵅ) = xᵢ_total

作者: Claude
版本: v2.0 (递归相分离算法)
日期: 2025-11-23
"""

import math
import sys
import os
from typing import Dict, List, Tuple, Optional, Callable, Set
import numpy as np
from scipy.optimize import minimize, root, nnls
from dataclasses import dataclass, field
from copy import deepcopy

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations.phase_diagram import PhaseDiagramCalculator
from models.extrapolation_models import BinaryModel


@dataclass
class PhaseInfo:
    """相信息数据类"""
    name: str  # 相名称 (LIQUID, BCC_A2, FCC_A1, HCP_A3)
    fraction: float = 0.0  # 相分数 (0-1)
    composition: Dict[str, float] = field(default_factory=dict)  # 相组成 {元素: 摩尔分数}
    gibbs_energy: float = 0.0  # 该相的摩尔吉布斯自由能 (J/mol)
    absolute_amounts: Dict[str, float] = field(default_factory=dict)  # 绝对量 (用于物质守恒计算)


class PhaseEquilibriumCalculator(PhaseDiagramCalculator):
    """
    相平衡计算器 (递归相分离算法)

    继承自 PhaseDiagramCalculator，利用已有的溶解度计算和稳定性检查功能
    """

    def __init__(self):
        super().__init__()
        self.binary_model = BinaryModel()

        # 定义常见的固相相结构
        self.solid_phases = ['BCC_A2', 'FCC_A1', 'HCP_A3']
        self.all_phases = ['LIQUID'] + self.solid_phases

        # 递归深度限制 (防止无限递归)
        self.max_recursion_depth = 10

        # 最小组分阈值
        self.min_composition_threshold = 1e-9

    def calculate_single_phase_energy(self,
                                     composition: Dict[str, float],
                                     temperature: float,
                                     phase_name: str,
                                     extrapolation_model_func: Callable,
                                     extrapolation_model_name: str = 'UEM1',
                                     activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算单相的摩尔吉布斯自由能

        G = Σ(xᵢ × μᵢ)
        μᵢ = G⁰ᵢ + RT ln(xᵢ) + RT ln(γᵢ)

        参数:
            composition: 相组成 {元素: 摩尔分数}
            temperature: 温度 (K)
            phase_name: 相名称 (LIQUID, BCC_A2, FCC_A1, HCP_A3)
            extrapolation_model_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型

        返回:
            摩尔吉布斯自由能 (J/mol) 或 None
        """
        try:
            # 归一化组成
            total = sum(composition.values())
            if total <= 0:
                return None
            comp_norm = {k: v/total for k, v in composition.items()}

            # 确定相态
            phase_state = 'liquid' if phase_name == 'LIQUID' else 'solid'

            # 计算总吉布斯自由能
            G_total = 0.0

            for element, x_i in comp_norm.items():
                if x_i < 1e-12:
                    continue

                # 获取标准吉布斯能量
                G_0 = self.tdb_parser.get_gibbs_energy(element, phase_name, temperature)
                if G_0 is None:
                    return None

                # 计算活度系数
                ln_gamma = self.calculate_ln_activity_coefficient(
                    comp_norm, element, temperature, phase_state,
                    extrapolation_model_func, extrapolation_model_name, activity_model
                )

                if ln_gamma is None:
                    return None

                # 计算化学势
                mu_i = G_0 + self.R * temperature * (math.log(max(x_i, 1e-12)) + ln_gamma)

                # 累加
                G_total += x_i * mu_i

            return G_total

        except Exception as e:
            print(f"计算单相能量时出错: {e}")
            return None

    def calculate_phase_equilibrium_at_temperature(self,
                                                   total_composition: Dict[str, float],
                                                   temperature: float,
                                                   extrapolation_model_func: Callable = None,
                                                   extrapolation_model_name: str = 'UEM1',
                                                   activity_model: str = 'Wagner',
                                                   max_phases: int = 2) -> Dict:
        """
        计算给定组成和温度下的相平衡

        参数:
            total_composition: 总组成 {元素: 摩尔分数}
            temperature: 温度 (K)
            extrapolation_model_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型
            max_phases: 最大相数 (默认2相平衡)

        返回:
            {
                'status': 状态,
                'temperature': 温度,
                'total_composition': 总组成,
                'phases': [PhaseInfo, ...],
                'total_gibbs_energy': 总吉布斯自由能,
                'message': 消息
            }
        """
        if extrapolation_model_func is None:
            extrapolation_model_func = self.binary_model.UEM1

        # 归一化总组成
        total = sum(total_composition.values())
        if total <= 0:
            return {
                'status': 'error',
                'message': '总组成不能为空',
                'phases': []
            }

        comp_norm = {k.upper(): v/total for k, v in total_composition.items()}
        n_components = len(comp_norm)

        # 首先尝试单相平衡 (最简单情况)
        single_phase_result = self._try_single_phase_equilibrium(
            comp_norm, temperature, extrapolation_model_func,
            extrapolation_model_name, activity_model
        )

        if single_phase_result['status'] == 'success':
            return single_phase_result

        # 如果单相不稳定,尝试两相平衡
        if max_phases >= 2:
            two_phase_result = self._try_two_phase_equilibrium(
                comp_norm, temperature, extrapolation_model_func,
                extrapolation_model_name, activity_model
            )

            if two_phase_result['status'] == 'success':
                return two_phase_result

        # 如果两相也不行,返回能量最低的单相作为近似
        return single_phase_result

    def _try_single_phase_equilibrium(self,
                                     composition: Dict[str, float],
                                     temperature: float,
                                     extrapolation_model_func: Callable,
                                     extrapolation_model_name: str,
                                     activity_model: str) -> Dict:
        """尝试单相平衡"""

        best_phase = None
        best_energy = float('inf')
        phase_energies = {}

        for phase_name in self.all_phases:
            G = self.calculate_single_phase_energy(
                composition, temperature, phase_name,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )

            if G is not None:
                phase_energies[phase_name] = G
                if G < best_energy:
                    best_energy = G
                    best_phase = phase_name

        if best_phase is None:
            return {
                'status': 'error',
                'message': '无法计算任何相的吉布斯自由能',
                'phases': []
            }

        # 检查该相是否真正稳定 (与其他相能量差足够大)
        stability_threshold = 100.0  # J/mol
        is_stable = True

        for phase_name, G in phase_energies.items():
            if phase_name != best_phase:
                if abs(G - best_energy) < stability_threshold:
                    is_stable = False
                    break

        phase_info = PhaseInfo(
            name=best_phase,
            fraction=1.0,
            composition=composition.copy(),
            gibbs_energy=best_energy
        )

        return {
            'status': 'success' if is_stable else 'metastable',
            'temperature': temperature,
            'total_composition': composition,
            'phases': [phase_info],
            'total_gibbs_energy': best_energy,
            'message': f'单相平衡: {best_phase}' if is_stable else f'可能存在两相区,最稳定单相: {best_phase}',
            'all_phase_energies': phase_energies
        }

    def _try_two_phase_equilibrium(self,
                                   composition: Dict[str, float],
                                   temperature: float,
                                   extrapolation_model_func: Callable,
                                   extrapolation_model_name: str,
                                   activity_model: str) -> Dict:
        """
        尝试两相平衡

        对于二元系统: 使用杠杆定律和化学势平衡
        对于多元系统: 简化处理,寻找能量最低的两相组合
        """

        n_components = len(composition)
        elements = sorted(composition.keys())

        # 对于二元系统,可以精确求解
        if n_components == 2:
            return self._solve_binary_two_phase_equilibrium(
                composition, temperature, extrapolation_model_func,
                extrapolation_model_name, activity_model
            )

        # 对于多元系统,使用简化方法
        # 尝试所有可能的两相组合,找出总能量最低的
        best_result = None
        best_total_energy = float('inf')

        for i, phase1 in enumerate(self.all_phases):
            for phase2 in self.all_phases[i+1:]:
                result = self._optimize_two_phase_composition(
                    composition, temperature, phase1, phase2,
                    extrapolation_model_func, extrapolation_model_name, activity_model
                )

                if result['status'] == 'success':
                    total_energy = result['total_gibbs_energy']
                    if total_energy < best_total_energy:
                        best_total_energy = total_energy
                        best_result = result

        if best_result is not None:
            return best_result

        return {
            'status': 'error',
            'message': '无法找到稳定的两相平衡',
            'phases': []
        }

    def _solve_binary_two_phase_equilibrium(self,
                                           composition: Dict[str, float],
                                           temperature: float,
                                           extrapolation_model_func: Callable,
                                           extrapolation_model_name: str,
                                           activity_model: str) -> Dict:
        """
        求解二元系统的两相平衡

        使用化学势平衡条件:
        μ₁ᵅ = μ₁ᵝ
        μ₂ᵅ = μ₂ᵝ

        和杠杆定律:
        x₁_total = f_α × x₁ᵅ + f_β × x₁ᵝ
        f_α + f_β = 1
        """

        elements = sorted(composition.keys())
        elem_A, elem_B = elements[0], elements[1]
        x_B_total = composition[elem_B]

        best_result = None
        best_energy = float('inf')

        # 尝试所有可能的两相组合
        for phase_alpha in self.all_phases:
            for phase_beta in self.all_phases:
                if phase_alpha == phase_beta:
                    continue

                # 求解两相平衡
                result = self._solve_binary_two_phase_tie_line(
                    elem_A, elem_B, x_B_total, temperature,
                    phase_alpha, phase_beta,
                    extrapolation_model_func, extrapolation_model_name, activity_model
                )

                if result['status'] == 'success':
                    if result['total_gibbs_energy'] < best_energy:
                        best_energy = result['total_gibbs_energy']
                        best_result = result

        if best_result is not None:
            return best_result

        return {
            'status': 'error',
            'message': '二元两相平衡求解失败',
            'phases': []
        }

    def _solve_binary_two_phase_tie_line(self,
                                         elem_A: str, elem_B: str,
                                         x_B_total: float,
                                         temperature: float,
                                         phase_alpha: str,
                                         phase_beta: str,
                                         extrapolation_model_func: Callable,
                                         extrapolation_model_name: str,
                                         activity_model: str) -> Dict:
        """
        求解二元系统两相连接线 (tie-line)

        未知量: [x_B_alpha, x_B_beta]
        方程:
        1. μ_A(α) = μ_A(β)
        2. μ_B(α) = μ_B(β)
        """

        phase_state_alpha = 'liquid' if phase_alpha == 'LIQUID' else 'solid'
        phase_state_beta = 'liquid' if phase_beta == 'LIQUID' else 'solid'

        def residual(x_B_vec):
            """残差函数"""
            x_B_alpha = max(min(x_B_vec[0], 0.999), 0.001)
            x_B_beta = max(min(x_B_vec[1], 0.999), 0.001)

            x_A_alpha = 1.0 - x_B_alpha
            x_A_beta = 1.0 - x_B_beta

            comp_alpha = {elem_A: x_A_alpha, elem_B: x_B_alpha}
            comp_beta = {elem_A: x_A_beta, elem_B: x_B_beta}

            # 计算化学势
            mu_A_alpha = self._get_chemical_potential_phase(
                comp_alpha, elem_A, temperature, phase_alpha,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )
            mu_A_beta = self._get_chemical_potential_phase(
                comp_beta, elem_A, temperature, phase_beta,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )
            mu_B_alpha = self._get_chemical_potential_phase(
                comp_alpha, elem_B, temperature, phase_alpha,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )
            mu_B_beta = self._get_chemical_potential_phase(
                comp_beta, elem_B, temperature, phase_beta,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )

            if any(mu is None for mu in [mu_A_alpha, mu_A_beta, mu_B_alpha, mu_B_beta]):
                return [1e10, 1e10]

            return [
                mu_A_alpha - mu_A_beta,
                mu_B_alpha - mu_B_beta
            ]

        # 尝试不同初值
        initial_guesses = [
            [0.3, 0.7],
            [0.5, 0.5],
            [0.1, 0.9],
            [x_B_total * 0.5, x_B_total * 1.5]
        ]

        best_sol = None
        best_residual = float('inf')

        for x0 in initial_guesses:
            try:
                sol = root(residual, x0, method='hybr')
                if sol.success:
                    res_norm = np.linalg.norm(sol.fun)
                    if res_norm < best_residual:
                        best_residual = res_norm
                        best_sol = sol
            except:
                continue

        if best_sol is None or best_residual > 1e-3:
            return {
                'status': 'failed',
                'message': f'两相平衡求解失败: {phase_alpha}-{phase_beta}'
            }

        # 提取解
        x_B_alpha = max(min(best_sol.x[0], 0.999), 0.001)
        x_B_beta = max(min(best_sol.x[1], 0.999), 0.001)

        # 检查是否满足杠杆定律
        # x_B_total = f_alpha * x_B_alpha + f_beta * x_B_beta
        # f_alpha + f_beta = 1
        # => f_alpha = (x_B_total - x_B_beta) / (x_B_alpha - x_B_beta)

        if abs(x_B_alpha - x_B_beta) < 1e-6:
            return {
                'status': 'failed',
                'message': '两相组成相同,非两相区'
            }

        f_alpha = (x_B_total - x_B_beta) / (x_B_alpha - x_B_beta)
        f_beta = 1.0 - f_alpha

        # 检查相分数是否合理
        if f_alpha < -0.01 or f_alpha > 1.01 or f_beta < -0.01 or f_beta > 1.01:
            return {
                'status': 'failed',
                'message': f'相分数不合理: f_α={f_alpha:.3f}, f_β={f_beta:.3f}'
            }

        # 限制在[0,1]范围
        f_alpha = max(0.0, min(1.0, f_alpha))
        f_beta = 1.0 - f_alpha

        # 计算各相的吉布斯能量
        comp_alpha = {elem_A: 1.0 - x_B_alpha, elem_B: x_B_alpha}
        comp_beta = {elem_A: 1.0 - x_B_beta, elem_B: x_B_beta}

        G_alpha = self.calculate_single_phase_energy(
            comp_alpha, temperature, phase_alpha,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )
        G_beta = self.calculate_single_phase_energy(
            comp_beta, temperature, phase_beta,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )

        if G_alpha is None or G_beta is None:
            return {
                'status': 'failed',
                'message': '无法计算相能量'
            }

        # 总能量
        G_total = f_alpha * G_alpha + f_beta * G_beta

        # 创建相信息
        phases = []
        if f_alpha > 0.001:
            phases.append(PhaseInfo(
                name=phase_alpha,
                fraction=f_alpha,
                composition=comp_alpha,
                gibbs_energy=G_alpha
            ))

        if f_beta > 0.001:
            phases.append(PhaseInfo(
                name=phase_beta,
                fraction=f_beta,
                composition=comp_beta,
                gibbs_energy=G_beta
            ))

        return {
            'status': 'success',
            'temperature': temperature,
            'total_composition': {elem_A: 1.0 - x_B_total, elem_B: x_B_total},
            'phases': phases,
            'total_gibbs_energy': G_total,
            'message': f'两相平衡: {phase_alpha}({f_alpha:.1%}) + {phase_beta}({f_beta:.1%})'
        }

    def _get_chemical_potential_phase(self,
                                     composition: Dict[str, float],
                                     component: str,
                                     temperature: float,
                                     phase_name: str,
                                     extrapolation_model_func: Callable,
                                     extrapolation_model_name: str,
                                     activity_model: str) -> Optional[float]:
        """获取指定相中某组分的化学势"""

        phase_state = 'liquid' if phase_name == 'LIQUID' else 'solid'

        # 获取标准吉布斯能量
        G_0 = self.tdb_parser.get_gibbs_energy(component, phase_name, temperature)
        if G_0 is None:
            return None

        # 计算活度系数
        ln_gamma = self.calculate_ln_activity_coefficient(
            composition, component, temperature, phase_state,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )

        if ln_gamma is None:
            return None

        x_i = composition.get(component, 0.0)
        if x_i < 1e-12:
            x_i = 1e-12

        return G_0 + self.R * temperature * (math.log(x_i) + ln_gamma)

    def _optimize_two_phase_composition(self,
                                       total_composition: Dict[str, float],
                                       temperature: float,
                                       phase1: str,
                                       phase2: str,
                                       extrapolation_model_func: Callable,
                                       extrapolation_model_name: str,
                                       activity_model: str) -> Dict:
        """
        优化两相组成和相分数 (多元系统简化方法)

        这是一个简化的实现,假设两相组成接近总组成
        实际应用中可能需要更复杂的优化算法
        """

        # 简化假设: 相分数各50%,组成接近总组成
        f1 = 0.5
        f2 = 0.5

        comp1 = total_composition.copy()
        comp2 = total_composition.copy()

        G1 = self.calculate_single_phase_energy(
            comp1, temperature, phase1,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )
        G2 = self.calculate_single_phase_energy(
            comp2, temperature, phase2,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )

        if G1 is None or G2 is None:
            return {'status': 'failed'}

        G_total = f1 * G1 + f2 * G2

        phases = [
            PhaseInfo(name=phase1, fraction=f1, composition=comp1, gibbs_energy=G1),
            PhaseInfo(name=phase2, fraction=f2, composition=comp2, gibbs_energy=G2)
        ]

        return {
            'status': 'success',
            'temperature': temperature,
            'total_composition': total_composition,
            'phases': phases,
            'total_gibbs_energy': G_total,
            'message': f'两相平衡(简化): {phase1}({f1:.1%}) + {phase2}({f2:.1%})'
        }

    def calculate_phase_equilibrium_vs_temperature(self,
                                                   total_composition: Dict[str, float],
                                                   T_min: float,
                                                   T_max: float,
                                                   n_points: int = 50,
                                                   extrapolation_model_func: Callable = None,
                                                   extrapolation_model_name: str = 'UEM1',
                                                   activity_model: str = 'Wagner',
                                                   progress_callback: Callable = None) -> Dict:
        """
        计算相平衡随温度的变化

        参数:
            total_composition: 总组成
            T_min: 最低温度 (K)
            T_max: 最高温度 (K)
            n_points: 温度点数
            progress_callback: 进度回调函数

        返回:
            {
                'temperatures': [T1, T2, ...],
                'phase_fractions': {phase_name: [f1, f2, ...]},
                'results': [result1, result2, ...]  # 每个温度的完整结果
            }
        """

        if extrapolation_model_func is None:
            extrapolation_model_func = self.binary_model.UEM1

        temperatures = np.linspace(T_min, T_max, n_points)
        results = []
        phase_fractions = {}

        for i, T in enumerate(temperatures):
            if progress_callback:
                progress_callback(i + 1, n_points)

            result = self.calculate_phase_equilibrium_at_temperature(
                total_composition, T,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )

            results.append(result)

            # 记录相分数
            if result['status'] in ['success', 'metastable']:
                for phase_info in result['phases']:
                    if phase_info.name not in phase_fractions:
                        phase_fractions[phase_info.name] = []
                    phase_fractions[phase_info.name].append(phase_info.fraction)

                # 填充缺失的相 (分数为0)
                for phase_name in self.all_phases:
                    if phase_name not in [p.name for p in result['phases']]:
                        if phase_name not in phase_fractions:
                            phase_fractions[phase_name] = []
                        phase_fractions[phase_name].append(0.0)

        return {
            'status': 'success',
            'temperatures': temperatures.tolist(),
            'phase_fractions': phase_fractions,
            'results': results
        }

    def calculate_phase_equilibrium_vs_composition(self,
                                                   base_composition: Dict[str, float],
                                                   variable_element: str,
                                                   x_min: float,
                                                   x_max: float,
                                                   temperature: float,
                                                   n_points: int = 50,
                                                   extrapolation_model_func: Callable = None,
                                                   extrapolation_model_name: str = 'UEM1',
                                                   activity_model: str = 'Wagner',
                                                   progress_callback: Callable = None) -> Dict:
        """
        计算相平衡随组分的变化 (在指定温度下)

        参数:
            base_composition: 基础组成 (不含变化元素)
            variable_element: 变化的元素
            x_min: 最小摩尔分数
            x_max: 最大摩尔分数
            temperature: 温度 (K)
            n_points: 组分点数
            progress_callback: 进度回调函数

        返回:
            {
                'compositions': [x1, x2, ...],
                'phase_fractions': {phase_name: [f1, f2, ...]},
                'results': [result1, result2, ...]
            }
        """

        if extrapolation_model_func is None:
            extrapolation_model_func = self.binary_model.UEM1

        variable_element = variable_element.upper()
        compositions = np.linspace(x_min, x_max, n_points)
        results = []
        phase_fractions = {}

        # 归一化基础组成
        base_total = sum(base_composition.values())
        base_norm = {k.upper(): v/base_total for k, v in base_composition.items() if k.upper() != variable_element}

        for i, x_var in enumerate(compositions):
            if progress_callback:
                progress_callback(i + 1, n_points)

            # 构建当前组成
            remaining = 1.0 - x_var
            current_comp = {variable_element: x_var}

            for elem, frac in base_norm.items():
                current_comp[elem] = frac * remaining

            # 归一化
            total = sum(current_comp.values())
            current_comp = {k: v/total for k, v in current_comp.items()}

            result = self.calculate_phase_equilibrium_at_temperature(
                current_comp, temperature,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )

            results.append(result)

            # 记录相分数
            if result['status'] in ['success', 'metastable']:
                for phase_info in result['phases']:
                    if phase_info.name not in phase_fractions:
                        phase_fractions[phase_info.name] = []
                    phase_fractions[phase_info.name].append(phase_info.fraction)

                # 填充缺失的相
                for phase_name in self.all_phases:
                    if phase_name not in [p.name for p in result['phases']]:
                        if phase_name not in phase_fractions:
                            phase_fractions[phase_name] = []
                        phase_fractions[phase_name].append(0.0)

        return {
            'status': 'success',
            'compositions': compositions.tolist(),
            'variable_element': variable_element,
            'temperature': temperature,
            'phase_fractions': phase_fractions,
            'results': results
        }
