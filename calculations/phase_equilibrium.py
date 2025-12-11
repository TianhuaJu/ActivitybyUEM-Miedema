# -*- coding: utf-8 -*-
"""
相平衡计算模块 (Phase Equilibrium Calculator)
=============================================
基于UEM-Miedema模型框架的多相平衡计算。

本模块包含两种相平衡计算算法：
1. PhaseEquilibriumCalculator - 基于溶解度约束的多相平衡计算器（基础版）
2. CompoundAwarePhaseEquilibrium - 化合物优先剥离的多相平衡计算器（增强版）

Author: AlloyThermolCal Pro Team
Date: 2025
"""

import math
import copy
import numpy as np
from typing import Dict, List, Optional, Tuple
from itertools import combinations

from calculations.phase_diagram import PhaseDiagramCalculator


# =============================================================================
# 基础版相平衡计算器 (溶解度约束法)
# =============================================================================

class PhaseEquilibriumCalculator(PhaseDiagramCalculator):
    """
    基于溶解度约束和稳定性迭代调整的多相平衡计算器。

    算法逻辑：
    1. 确定溶剂（含量最多的元素）
    2. 计算各溶质在溶剂相中的最大溶解度
    3. 构建饱和组成（每个溶质不超过溶解度）
    4. 判断饱和组成是否稳定
    5. 如果不稳定，逐步减少影响最大的溶质，直至稳定
    6. 得到第一相的组成和分数
    7. 计算剩余组成，重复以上步骤
    """

    def __init__(self):
        super().__init__()

    def calculate_phase_equilibrium(self,
                                    alloy_composition: Dict[str, float],
                                    temperature: float,
                                    extrapolation_model_func=None,
                                    extrapolation_model_name='UEM1',
                                    activity_model='Wagner',
                                    min_phase_fraction: float = 1e-4,
                                    max_iterations: int = 10,
                                    adjustment_factor: float = 0.95) -> List[Dict]:
        """
        计算特定合金组成下的多相平衡。

        参数:
            alloy_composition: 合金组成 {元素: 摩尔分数}
            temperature: 温度 (K)
            extrapolation_model_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型
            min_phase_fraction: 最小相分数阈值
            max_iterations: 最大迭代次数
            adjustment_factor: 调整系数

        返回:
            List[Dict]: 包含各稳定相信息的列表
        """
        print(f"\n{'=' * 60}")
        print(f"开始多相平衡计算（溶解度约束法）")
        print(f"初始合金组成: {self._format_comp(alloy_composition)}")
        print(f"温度: {temperature} K")
        print(f"{'=' * 60}\n")

        results = []
        current_comp = alloy_composition.copy()
        remaining_moles = 1.0
        current_moles_dict = {k: v * remaining_moles for k, v in current_comp.items()}

        for iteration in range(max_iterations):
            print(f"{'─' * 60}")
            print(f"迭代 {iteration + 1}:")
            print(f"当前剩余成分: {self._format_comp(current_comp)}")
            print(f"剩余摩尔分数: {remaining_moles:.6f}\n")

            # 归一化当前成分
            total_current = sum(current_comp.values())
            if total_current <= 1e-9:
                print("剩余物质几乎为零，计算结束")
                break
            current_comp = {k: v / total_current for k, v in current_comp.items()}

            # 确定溶剂
            solvent = max(current_comp.items(), key=lambda x: x[1])[0]
            print(f"  溶剂元素: {solvent} (含量: {current_comp[solvent]:.4f})")

            # 寻找能量最低的相
            matrix_phase = self._find_lowest_energy_phase(current_comp, temperature)
            print(f"  基体相: {matrix_phase}\n")

            # 计算溶解度限
            solubility_limits = self._calculate_solubility_limits(
                solvent=solvent,
                current_comp=current_comp,
                matrix_phase=matrix_phase,
                temperature=temperature,
                extrapolation_func=extrapolation_model_func,
                model_params=(extrapolation_model_name, activity_model)
            )

            # 构建饱和组成
            saturated_comp = self._build_saturated_composition(
                current_comp=current_comp,
                solvent=solvent,
                solubility_limits=solubility_limits
            )
            print(f"  初始饱和组成: {self._format_comp(saturated_comp)}")

            # 迭代调整至稳定
            stable_comp = self._adjust_to_stability(
                initial_comp=saturated_comp,
                solvent=solvent,
                matrix_phase=matrix_phase,
                temperature=temperature,
                extrapolation_func=extrapolation_model_func,
                model_params=(extrapolation_model_name, activity_model),
                adjustment_factor=adjustment_factor
            )
            print(f"  稳定相组成: {self._format_comp(stable_comp)}\n")

            # 计算相摩尔数
            phase_moles, limiting_element = self._calculate_phase_moles(
                current_moles_dict, stable_comp
            )
            print(f"  相摩尔分数: {phase_moles:.6f} (受限于: {limiting_element})")

            if phase_moles < min_phase_fraction:
                print(f"  ⚠ 相分数过小，将剩余物质归入最后一相\n")
                results.append({
                    'phase_name': "Residual_Phase",
                    'composition': current_comp,
                    'mole_fraction': remaining_moles,
                    'type': 'Residue'
                })
                break

            results.append({
                'phase_name': matrix_phase,
                'composition': stable_comp,
                'mole_fraction': phase_moles,
                'type': 'Matrix' if iteration == 0 else 'Precipitate'
            })

            # 更新剩余物质
            new_moles_dict = {}
            for el in current_moles_dict:
                n_consumed = phase_moles * stable_comp.get(el, 0.0)
                n_remaining = max(0.0, current_moles_dict[el] - n_consumed)
                new_moles_dict[el] = n_remaining

            current_moles_dict = new_moles_dict
            remaining_moles = sum(current_moles_dict.values())
            print(f"  剩余摩尔分数: {remaining_moles:.6f}\n")

            if remaining_moles < 1e-6:
                print("所有物质已完全分配，计算结束")
                break

            current_comp = {k: v / remaining_moles for k, v in current_moles_dict.items()}

        # 输出结果摘要
        self._print_results_summary(results)
        return results

    def _calculate_solubility_limits(self, solvent, current_comp, matrix_phase,
                                     temperature, extrapolation_func, model_params):
        """计算各溶质在溶剂相中的溶解度限"""
        extrap_name, act_model = model_params
        solubility_limits = {}
        solutes = [k for k in current_comp.keys() if k != solvent]

        print(f"  计算溶解度限:")
        for solute in solutes:
            proxy_base = {solvent: 1.0}
            try:
                res = self.calculate_solubility(
                    base_alloy_composition=proxy_base,
                    solute_element=solute,
                    solution_phase='SOLID' if 'LIQUID' not in matrix_phase else 'LIQUID',
                    temperature=temperature,
                    extrapolation_func=extrapolation_func,
                    extrapolation_model_name=extrap_name,
                    activity_model=act_model
                )
                limit = res.get('solubility_mole_fraction', 1.0)
                if limit is None or limit > 1.0:
                    limit = 1.0
                solubility_limits[solute] = limit
                print(f"    {solute}: {limit:.6f}")
            except Exception:
                print(f"    {solute}: 计算失败，假设完全互溶")
                solubility_limits[solute] = 1.0
        print()
        return solubility_limits

    def _build_saturated_composition(self, current_comp, solvent, solubility_limits):
        """构建饱和组成"""
        saturated_comp = {}
        sum_solutes = 0.0
        for solute in [k for k in current_comp.keys() if k != solvent]:
            sat_x = min(current_comp[solute], solubility_limits.get(solute, 1.0))
            saturated_comp[solute] = sat_x
            sum_solutes += sat_x
        saturated_comp[solvent] = max(0.0, 1.0 - sum_solutes)
        return saturated_comp

    def _adjust_to_stability(self, initial_comp, solvent, matrix_phase, temperature,
                             extrapolation_func, model_params, adjustment_factor=0.95):
        """迭代调整组成直至稳定"""
        extrap_name, act_model = model_params
        current_comp = initial_comp.copy()
        print(f"  调整组成至稳定:")

        for i in range(30):
            total = sum(current_comp.values())
            current_comp = {k: v / total for k, v in current_comp.items()}

            is_stable, issues = self._check_alloy_full_stability(
                composition=current_comp,
                temperature=temperature,
                tdb_phase=matrix_phase,
                extrapolation_func=extrapolation_func,
                extrapolation_model_name=extrap_name,
                activity_model=act_model
            )

            if is_stable:
                print(f"    → 第 {i + 1} 次调整后稳定\n")
                return current_comp

            most_unstable, max_deviation = self._find_most_unstable_element(issues)
            if most_unstable is None or most_unstable == solvent:
                print(f"    → 无法进一步调整，返回当前组成\n")
                return current_comp

            old_x = current_comp[most_unstable]
            current_comp[most_unstable] *= adjustment_factor
            print(f"    第 {i + 1} 次: 减少 {most_unstable} ({old_x:.6f} → {current_comp[most_unstable]:.6f})")

        print(f"    ⚠ 达到最大调整次数\n")
        return current_comp

    def _find_most_unstable_element(self, stability_issues):
        """找到最不稳定的元素"""
        max_deviation = 0.0
        most_unstable = None
        for issue in stability_issues:
            try:
                if '组分不稳定:' in issue and 'Δμ=' in issue:
                    parts = issue.split()
                    element = parts[1]
                    mu_part = issue.split('Δμ=')[1].split(')')[0]
                    deviation = abs(float(mu_part))
                    if deviation > max_deviation:
                        max_deviation = deviation
                        most_unstable = element
            except:
                continue
        return most_unstable, max_deviation

    def _calculate_phase_moles(self, current_moles_dict, saturated_comp):
        """计算相摩尔数"""
        max_moles = float('inf')
        limiting_element = None
        for element, x_element in saturated_comp.items():
            if x_element < 1e-12:
                continue
            n_available = current_moles_dict.get(element, 0.0)
            possible_moles = n_available / x_element
            if possible_moles < max_moles:
                max_moles = possible_moles
                limiting_element = element
        return max_moles, limiting_element

    def _find_lowest_energy_phase(self, composition, temperature):
        """找到能量最低的相"""
        solvent = max(composition.items(), key=lambda x: x[1])[0]
        phases = [p for p in self.tdb_parser.get_element_phases(solvent) if p != 'GAS']
        best_phase = 'FCC_A1'
        min_g = float('inf')
        for phase in phases:
            try:
                g_pure = self.tdb_parser.get_gibbs_energy(solvent, phase, temperature)
                if g_pure is not None and g_pure < min_g:
                    min_g = g_pure
                    best_phase = phase
            except:
                continue
        return best_phase

    def _format_comp(self, comp):
        """格式化输出组成"""
        return ", ".join([f"{k}:{v:.4f}" for k, v in comp.items() if v > 1e-4])

    def _print_results_summary(self, results):
        """打印结果摘要"""
        print(f"{'=' * 60}")
        print(f"相平衡计算完成")
        print(f"共形成 {len(results)} 个相:\n")
        total_fraction = 0.0
        for i, phase in enumerate(results, 1):
            frac = phase['mole_fraction']
            total_fraction += frac
            print(f"{i}. {phase['phase_name']}: {frac:.6f} ({frac * 100:.2f}%)")
            print(f"   组成: {self._format_comp(phase['composition'])}")
        print(f"\n总摩尔分数: {total_fraction:.6f}")
        print(f"{'=' * 60}\n")

    def calculate_phase_equilibrium_vs_temperature(self,
                                                    composition: Dict[str, float],
                                                    T_min: float,
                                                    T_max: float,
                                                    n_points: int,
                                                    extrapolation_func,
                                                    extrapolation_model_name: str,
                                                    activity_model: str,
                                                    progress_callback=None) -> Dict:
        """
        计算相平衡随温度的变化

        参数:
            composition: 合金组成 {元素: 摩尔分数}
            T_min: 最低温度 (K)
            T_max: 最高温度 (K)
            n_points: 计算点数
            extrapolation_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型
            progress_callback: 进度回调函数 (current, total)

        返回:
            Dict: {
                'temperatures': [温度列表],
                'phase_fractions': {相名称: [分数列表]}
            }
        """
        print(f"\n{'=' * 60}")
        print(f"相平衡随温度变化分析")
        print(f"合金组成: {self._format_comp(composition)}")
        print(f"温度范围: {T_min:.0f} - {T_max:.0f} K")
        print(f"计算点数: {n_points}")
        print(f"{'=' * 60}\n")

        temperatures = np.linspace(T_min, T_max, n_points)
        phase_fractions = {}  # {phase_name: [fractions at each temp]}

        for i, T in enumerate(temperatures):
            if progress_callback:
                progress_callback(i + 1, n_points)

            # 计算该温度下的相平衡
            try:
                phases = self.calculate_phase_equilibrium(
                    composition, T,
                    extrapolation_func, extrapolation_model_name, activity_model
                )

                # 收集各相分数
                temp_phases = {}
                for phase in phases:
                    phase_name = phase.get('phase_name', 'Unknown')
                    frac = phase.get('mole_fraction', 0.0)
                    temp_phases[phase_name] = frac

                # 更新 phase_fractions 字典
                all_phase_names = set(phase_fractions.keys()) | set(temp_phases.keys())
                for phase_name in all_phase_names:
                    if phase_name not in phase_fractions:
                        # 新发现的相，初始化为之前全为0
                        phase_fractions[phase_name] = [0.0] * i
                    phase_fractions[phase_name].append(temp_phases.get(phase_name, 0.0))

            except Exception as e:
                print(f"  温度 {T:.0f} K 计算失败: {e}")
                # 填充0
                for phase_name in phase_fractions:
                    phase_fractions[phase_name].append(0.0)

        # 确保所有相的列表长度一致
        for phase_name in phase_fractions:
            while len(phase_fractions[phase_name]) < n_points:
                phase_fractions[phase_name].append(0.0)

        return {
            'temperatures': temperatures.tolist(),
            'phase_fractions': phase_fractions
        }


# =============================================================================
# 增强版相平衡计算器 (化合物优先剥离法)
# =============================================================================

class CompoundAwarePhaseEquilibrium(PhaseDiagramCalculator):
    """
    基于"稳定性收缩-剥离法"的多相平衡计算器 (V6 - 化合物优先剥离版)。

    特点：
    当检测到化合物导致不稳定时，优先剥离化合物相，而不是强制剥离溶剂基体。
    这能正确模拟金属间化合物的消耗过程，避免溶剂过早耗尽。

    适用场景：
    - 含有金属间化合物析出的合金系统
    - 需要考虑化合物相的多相平衡
    """

    def __init__(self):
        super().__init__()
        # 延迟导入避免循环依赖
        self._miedema_model = None

    def _get_miedema_model(self, el1, el2):
        """获取Miedema模型实例"""
        from models.miedema_model import MiedemaModel
        return MiedemaModel((el1, el2), "SOLID")

    def calculate_phase_equilibrium(self,
                                    alloy_composition: Dict[str, float],
                                    temperature: float,
                                    extrapolation_model_func=None,
                                    extrapolation_model_name='UEM1',
                                    activity_model='Wagner',
                                    min_phase_fraction: float = 1e-4,
                                    max_iterations: int = 20) -> List[Dict]:
        """
        计算特定合金组成下的多相平衡（化合物感知版本）。

        参数:
            alloy_composition: 合金组成
            temperature: 温度 (K)
            extrapolation_model_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型
            min_phase_fraction: 最小相分数阈值
            max_iterations: 最大迭代次数

        返回:
            List[Dict]: 包含各稳定相信息的列表
        """
        # 自动加载默认模型
        if extrapolation_model_func is None:
            try:
                from models.extrapolation_models import BinaryModel
                extrapolation_model_func = BinaryModel().UEM1
            except ImportError:
                print("Error: Could not load BinaryModel.")
                return []

        results = []
        current_moles_dict = alloy_composition.copy()
        total_moles_system = sum(current_moles_dict.values())
        current_moles_dict = {k: v / total_moles_system for k, v in current_moles_dict.items()}

        print(f"--- 开始多相平衡计算 (化合物感知版, T={temperature}K) ---")

        for iteration in range(max_iterations):
            total_current_moles = sum(current_moles_dict.values())
            if total_current_moles < 1e-6:
                break

            current_comp_norm = {k: v / total_current_moles for k, v in current_moles_dict.items()}
            comp_str = self._format_comp(current_comp_norm)
            print(f"\n[Iteration {iteration + 1}] 当前对象 (总量 {total_current_moles:.4f}): {comp_str}")

            # 识别基础结构
            base_phase_struct = self._identify_stable_structure_tdb(current_comp_norm, temperature)
            solvent_name = max(current_comp_norm.items(), key=lambda x: x[1])[0]
            print(f"  -> 假定基体溶剂: {solvent_name}, 结构: {base_phase_struct}")

            # 判断稳定性
            is_stable, unstable_details = self._check_phase_stability_strict(
                current_comp_norm, base_phase_struct, temperature,
                extrapolation_model_func, extrapolation_model_name, activity_model,
                solvent_name=solvent_name
            )

            if is_stable:
                target_phase_name = self._generate_phase_name(current_comp_norm, base_phase_struct)
                print(f"  -> [判定] 成分稳定。识别为: {target_phase_name}")
                results.append({
                    'phase_name': target_phase_name,
                    'composition': current_comp_norm,
                    'mole_fraction': total_current_moles,
                    'type': 'Primary' if iteration == 0 else 'Residue'
                })
                break

            # 不稳定：分析原因并决定策略
            primary_cause = unstable_details[0]
            cause_type = primary_cause.get('type', 'pure')
            cause_info = primary_cause.get('info', 'Unknown')
            print(f"  -> [判定] 不稳定。诱因: {cause_info} (ΔG_drive={primary_cause['driving_force']:.1f})")

            if cause_type == 'compound':
                # 策略A: 剥离化合物
                print(f"  -> [策略] 优先形成并剥离金属间化合物: {cause_info}")
                target_composition = primary_cause['stoichiometry']
                try:
                    clean_name = cause_info.replace("Miedema_", "")
                    target_phase_name = f"{clean_name} (Intermetallic)"
                except:
                    target_phase_name = f"{cause_info} (Compound)"
                target_type = "Precipitate"
            else:
                # 策略B: 剥离基体
                print(f"  -> [策略] 收缩溶解度，剥离饱和基体")
                target_composition = self._find_stable_phase_composition(
                    base_alloy=current_comp_norm,
                    matrix_phase=base_phase_struct,
                    temperature=temperature,
                    extrap_func=extrapolation_model_func,
                    params=(extrapolation_model_name, activity_model),
                    solvent_name=solvent_name
                )
                target_phase_name = self._generate_phase_name(target_composition, base_phase_struct)
                target_type = "Matrix" if iteration == 0 else "Intermediate"

            print(f"  -> 目标成分: {self._format_comp(target_composition)}")

            phase_fraction_abs = self._calculate_max_phase_fraction(
                current_moles_dict, target_composition
            )
            print(f"  -> 剥离 {target_phase_name}: {phase_fraction_abs:.4f} mol")

            if phase_fraction_abs < min_phase_fraction:
                print("  -> 剥离量过小，停止迭代。")
                final_name = self._generate_phase_name(current_comp_norm, base_phase_struct)
                results.append({
                    'phase_name': final_name,
                    'composition': current_comp_norm,
                    'mole_fraction': total_current_moles,
                    'type': 'Residue'
                })
                break

            results.append({
                'phase_name': target_phase_name,
                'composition': target_composition,
                'mole_fraction': phase_fraction_abs,
                'type': target_type
            })

            # 更新剩余物质
            new_moles_dict = {}
            for el, mols in current_moles_dict.items():
                consumed = phase_fraction_abs * target_composition.get(el, 0.0)
                new_moles_dict[el] = max(0.0, mols - consumed)
            current_moles_dict = new_moles_dict

        return results

    def _identify_stable_structure_tdb(self, composition, temperature):
        """识别稳定结构"""
        solvent = max(composition.items(), key=lambda x: x[1])[0]
        try:
            ref = self.tdb_parser.get_stable_phase(solvent, temperature)
            if ref:
                return ref
        except:
            pass
        return 'FCC_A1'

    def _generate_phase_name(self, composition, base_struct):
        """生成相名称"""
        sorted_els = sorted(composition.items(), key=lambda x: x[1], reverse=True)
        major_el, major_frac = sorted_els[0]
        if major_frac > 0.90:
            return f"{base_struct} ({major_el} Matrix)"
        if len(sorted_els) >= 2:
            el1, x1 = sorted_els[0]
            el2, x2 = sorted_els[1]
            sub_total = x1 + x2
            p1 = x1 / sub_total
            ratios = [(2, 1, "2:1"), (1, 2, "1:2"), (3, 1, "3:1"), (1, 3, "1:3"),
                      (1, 1, "1:1"), (5, 1, "5:1"), (1, 5, "1:5"), (3, 2, "3:2"), (2, 3, "2:3")]
            for n1, n2, label in ratios:
                target_p1 = n1 / (n1 + n2)
                if abs(p1 - target_p1) < 0.05:
                    return f"{base_struct} ({el1}{n1}{el2}{n2}-like)"
        return f"{base_struct} (Solid Solution)"

    def _scan_miedema_compounds(self, composition, temperature, chemical_potentials, solvent_name=None):
        """使用Miedema模型扫描金属间化合物"""
        elements = [k for k in composition.keys() if composition[k] > 1e-6]
        if len(elements) < 2:
            return []
        potential_compounds = []
        ratios = [(1, 1), (1, 2), (1, 3), (2, 1), (3, 1), (2, 3), (3, 2), (1, 5), (5, 1)]

        for el1, el2 in combinations(elements, 2):
            try:
                miedema_model = self._get_miedema_model(el1, el2)
            except:
                continue

            g_pure1 = self.tdb_parser.get_gibbs_energy(el1, 'SER', temperature) or \
                      self.tdb_parser.get_gibbs_energy(el1, 'SER', 298.15)
            g_pure2 = self.tdb_parser.get_gibbs_energy(el2, 'SER', temperature) or \
                      self.tdb_parser.get_gibbs_energy(el2, 'SER', 298.15)
            if g_pure1 is None or g_pure2 is None:
                continue

            mu1, mu2 = chemical_potentials.get(el1), chemical_potentials.get(el2)
            if mu1 is None or mu2 is None:
                continue

            for n1, n2 in ratios:
                x1 = n1 / (n1 + n2)
                x2 = 1.0 - x1
                try:
                    h = miedema_model.getmixingEnthalpy_by_Miedema_Model(el1, x1, temperature, order_degree='IM')
                except:
                    continue

                g_cmp = h + (x1 * g_pure1 + x2 * g_pure2)
                drive = (x1 * mu1 + x2 * mu2) - g_cmp

                if drive > 100.0:
                    potential_compounds.append({
                        'element': el1,
                        'type': 'compound',
                        'driving_force': drive,
                        'info': f"Miedema_{el1}{n1}{el2}{n2}",
                        'stoichiometry': {el1: x1, el2: x2}
                    })
        return potential_compounds

    def _check_phase_stability_strict(self, comp, phase, T, func, model, act, solvent_name=None):
        """严格检查相稳定性"""
        details = []
        is_stable = True
        chemical_potentials = {}

        for el in comp:
            if comp[el] < 1e-10:
                continue
            mu = self._get_chemical_potential(comp, el, T, phase, func, model, act)
            if mu is None:
                continue
            chemical_potentials[el] = mu

            # 单质检查
            stable_phase = self.tdb_parser.get_stable_phase(el, T)
            g_ppt = self.tdb_parser.get_gibbs_energy(el, stable_phase, T) or \
                    self.tdb_parser.get_gibbs_energy(el, 'SER', T)
            if g_ppt is not None and (mu - g_ppt) > 50.0:
                if not solvent_name or el != solvent_name:
                    is_stable = False
                    details.append({
                        'element': el,
                        'type': 'pure',
                        'driving_force': mu - g_ppt,
                        'info': f"Pure {el}"
                    })

        # 化合物检查
        if len(chemical_potentials) >= 2:
            compounds = self._scan_miedema_compounds(comp, T, chemical_potentials, solvent_name)
            if compounds:
                is_stable = False
                details.extend(compounds)

        details.sort(key=lambda x: x['driving_force'], reverse=True)
        return is_stable, details

    def _find_stable_phase_composition(self, base_alloy, matrix_phase, temperature, extrap_func, params, solvent_name):
        """寻找稳定相组成"""
        model_name, act_model = params
        proxy_base = {solvent_name: 1.0}
        candidate_comp = {}
        sum_solutes = 0.0

        for el, original_x in base_alloy.items():
            if el == solvent_name:
                continue
            try:
                res = self.calculate_solubility_v2(proxy_base, el, 'SOLID', temperature, extrap_func, model_name,
                                                   act_model)
                limit = res.get('solubility_mole_fraction', 1.0) or 1.0
            except:
                limit = 1.0
            cx = min(original_x, limit)
            candidate_comp[el] = cx
            sum_solutes += cx

        candidate_comp[solvent_name] = 1.0 - sum_solutes

        for step in range(50):
            tot = sum(candidate_comp.values())
            candidate_comp = {k: v / tot for k, v in candidate_comp.items()}
            stable, details = self._check_phase_stability_strict(
                candidate_comp, matrix_phase, temperature, extrap_func, model_name, act_model, solvent_name
            )
            if stable:
                return candidate_comp

            target_el = None
            for d in details:
                if d.get('element') != solvent_name and d.get('element') in candidate_comp:
                    target_el = d['element']
                    break

            if target_el:
                candidate_comp[target_el] *= 0.8
                if candidate_comp[target_el] < 1e-10:
                    candidate_comp[target_el] = 1e-10
            else:
                break

        return candidate_comp

    def _calculate_max_phase_fraction(self, total_moles_dict, phase_comp_norm):
        """计算最大相分数"""
        max_frac = float('inf')
        for el, x_phase in phase_comp_norm.items():
            if x_phase < 1e-9:
                continue
            n_tot = total_moles_dict.get(el, 0.0)
            possible = n_tot / x_phase
            if possible < max_frac:
                max_frac = possible
        return max_frac

    def _format_comp(self, comp):
        """格式化输出组成"""
        return ", ".join([f"{k}:{v:.4f}" for k, v in comp.items() if v > 1e-5])


# =============================================================================
# 手动指定平衡相计算器
# =============================================================================

class ManualPhaseEquilibriumCalculator(PhaseDiagramCalculator):
    """
    手动指定平衡相的相平衡计算器。

    功能：
    1. 用户指定平衡相（化合物或溶体相）
    2. 如果是化合物，可以输入其吉布斯能
    3. 计算平衡相的数量和成分

    适用场景：
    - 用户已知平衡相类型，想要验证计算结果
    - 需要计算特定化合物的析出量
    - 研究溶体相的平衡组成
    """

    def __init__(self):
        super().__init__()
        # 常用化合物化学计量比数据库
        self.compound_database = {
            # 碳化物
            'Fe3C': {'Fe': 3, 'C': 1},
            'Cr23C6': {'Cr': 23, 'C': 6},
            'Cr7C3': {'Cr': 7, 'C': 3},
            'Cr3C2': {'Cr': 3, 'C': 2},
            'Mo2C': {'Mo': 2, 'C': 1},
            'VC': {'V': 1, 'C': 1},
            'TiC': {'Ti': 1, 'C': 1},
            'WC': {'W': 1, 'C': 1},
            'NbC': {'Nb': 1, 'C': 1},
            'SiC': {'Si': 1, 'C': 1},
            # 氮化物
            'TiN': {'Ti': 1, 'N': 1},
            'VN': {'V': 1, 'N': 1},
            'AlN': {'Al': 1, 'N': 1},
            'CrN': {'Cr': 1, 'N': 1},
            'Cr2N': {'Cr': 2, 'N': 1},
            'Si3N4': {'Si': 3, 'N': 4},
            # 金属间化合物
            'Fe2Al5': {'Fe': 2, 'Al': 5},
            'Fe3Al': {'Fe': 3, 'Al': 1},
            'FeAl': {'Fe': 1, 'Al': 1},
            'FeAl3': {'Fe': 1, 'Al': 3},
            'Ni3Al': {'Ni': 3, 'Al': 1},
            'NiAl': {'Ni': 1, 'Al': 1},
            'TiAl': {'Ti': 1, 'Al': 1},
            'Ti3Al': {'Ti': 3, 'Al': 1},
            'TiAl3': {'Ti': 1, 'Al': 3},
            'Mg2Si': {'Mg': 2, 'Si': 1},
            'MgZn2': {'Mg': 1, 'Zn': 2},
            'Al2Cu': {'Al': 2, 'Cu': 1},
            'Al3Ni': {'Al': 3, 'Ni': 1},
            'FeSi': {'Fe': 1, 'Si': 1},
            'FeSi2': {'Fe': 1, 'Si': 2},
            'Fe3Si': {'Fe': 3, 'Si': 1},
            'Fe5Si3': {'Fe': 5, 'Si': 3},
            # 氧化物
            'Al2O3': {'Al': 2, 'O': 3},
            'SiO2': {'Si': 1, 'O': 2},
            'FeO': {'Fe': 1, 'O': 1},
            'Fe2O3': {'Fe': 2, 'O': 3},
            'Fe3O4': {'Fe': 3, 'O': 4},
            'MnO': {'Mn': 1, 'O': 1},
            'Cr2O3': {'Cr': 2, 'O': 3},
            # Laves相
            'Fe2Nb': {'Fe': 2, 'Nb': 1},
            'Fe2Mo': {'Fe': 2, 'Mo': 1},
            'Fe2Ti': {'Fe': 2, 'Ti': 1},
            'Fe2W': {'Fe': 2, 'W': 1},
            # σ相
            'FeCr': {'Fe': 1, 'Cr': 1},
            # 硫化物
            'MnS': {'Mn': 1, 'S': 1},
            'FeS': {'Fe': 1, 'S': 1},
        }

        # 溶体相类型
        self.solution_phases = ['LIQUID', 'BCC_A2', 'FCC_A1', 'HCP_A3', 'BCC_B2', 'L12_FCC']

    def parse_compound_formula(self, formula: str) -> Dict[str, float]:
        """
        解析化合物化学式，返回摩尔分数组成。

        支持格式:
        - 数据库中的化合物: "Fe3C", "TiC", "Ni3Al"
        - 自定义格式: "Fe3C1" (元素后跟数字)
        - 带括号: "(Fe)3(C)1"

        返回: {元素: 摩尔分数}
        """
        import re

        formula = formula.strip()

        # 首先检查数据库
        if formula in self.compound_database:
            stoich = self.compound_database[formula]
            total = sum(stoich.values())
            return {el.upper(): n / total for el, n in stoich.items()}

        # 解析自定义格式
        # 正则表达式匹配: 元素符号(1-2个字母) + 可选的数字
        pattern = r'([A-Z][a-z]?)(\d*\.?\d*)'
        matches = re.findall(pattern, formula)

        if not matches:
            raise ValueError(f"无法解析化合物化学式: {formula}")

        stoichiometry = {}
        for element, count_str in matches:
            if not element:
                continue
            count = float(count_str) if count_str else 1.0
            element_upper = element.upper()
            stoichiometry[element_upper] = stoichiometry.get(element_upper, 0) + count

        if not stoichiometry:
            raise ValueError(f"无法解析化合物化学式: {formula}")

        # 转换为摩尔分数
        total = sum(stoichiometry.values())
        return {el: n / total for el, n in stoichiometry.items()}

    def is_solution_phase(self, phase_name: str) -> bool:
        """判断是否为溶体相"""
        phase_upper = phase_name.upper().replace(' ', '_')
        # 必须完全匹配溶体相名称，避免 "C" 被误判为 "FCC_A1" 的一部分
        if phase_upper in self.solution_phases:
            return True
        # 检查是否以溶体相名称开头（如 "BCC_A2#1"）
        for sol_phase in self.solution_phases:
            if phase_upper.startswith(sol_phase):
                return True
        return False

    def is_pure_element(self, phase_name: str) -> bool:
        """判断是否为纯元素相（如 C, Si, Fe 等）"""
        import re
        # 纯元素：1-2个字母，可选的数字1
        pattern = r'^([A-Z][a-z]?)1?$'
        return bool(re.match(pattern, phase_name.strip()))

    def calculate_manual_equilibrium(self,
                                     alloy_composition: Dict[str, float],
                                     equilibrium_phase: str,
                                     temperature: float,
                                     compound_gibbs_energy: Optional[float] = None,
                                     extrapolation_func=None,
                                     extrapolation_model_name: str = 'UEM1',
                                     activity_model: str = 'Wagner') -> Dict:
        """
        计算手动指定平衡相的相平衡。

        参数:
            alloy_composition: 合金总组成 {元素: 摩尔分数}
            equilibrium_phase: 平衡相名称 (如 "Fe3C", "BCC_A2", "LIQUID")
            temperature: 温度 (K)
            compound_gibbs_energy: 化合物的吉布斯能 (J/mol)，仅对化合物有效
            extrapolation_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型

        返回:
            {
                'status': 'success' | 'error',
                'message': str,
                'equilibrium_phase': {
                    'name': str,
                    'type': 'compound' | 'solution',
                    'composition': Dict[str, float],  # 相组成
                    'mole_fraction': float,           # 相的摩尔分数
                    'mass_fraction': float,           # 相的质量分数
                    'gibbs_energy': float             # 相的吉布斯能
                },
                'matrix_phase': {
                    'name': str,
                    'composition': Dict[str, float],  # 基体相组成
                    'mole_fraction': float
                },
                'calculation_details': Dict          # 计算细节
            }
        """
        print(f"\n{'=' * 60}")
        print(f"手动指定平衡相计算")
        print(f"合金组成: {self._format_comp(alloy_composition)}")
        print(f"平衡相: {equilibrium_phase}")
        print(f"温度: {temperature} K")
        if compound_gibbs_energy is not None:
            print(f"化合物吉布斯能: {compound_gibbs_energy} J/mol")
        print(f"{'=' * 60}\n")

        # 归一化合金组成
        total = sum(alloy_composition.values())
        alloy_composition = {k.upper(): v / total for k, v in alloy_composition.items()}

        # 判断平衡相类型
        if self.is_solution_phase(equilibrium_phase):
            return self._calculate_solution_phase_equilibrium(
                alloy_composition, equilibrium_phase, temperature,
                extrapolation_func, extrapolation_model_name, activity_model
            )
        else:
            return self._calculate_compound_phase_equilibrium(
                alloy_composition, equilibrium_phase, temperature,
                compound_gibbs_energy, extrapolation_func,
                extrapolation_model_name, activity_model
            )

    def _calculate_compound_phase_equilibrium(self,
                                               alloy_composition: Dict[str, float],
                                               compound_formula: str,
                                               temperature: float,
                                               compound_gibbs_energy: Optional[float],
                                               extrapolation_func,
                                               extrapolation_model_name: str,
                                               activity_model: str) -> Dict:
        """计算化合物相或纯元素相的平衡"""
        # 判断是否为纯元素
        is_element = self.is_pure_element(compound_formula)
        phase_type = 'element' if is_element else 'compound'

        if is_element:
            print(f"[计算纯元素相平衡: {compound_formula}]")
        else:
            print(f"[计算化合物相平衡: {compound_formula}]")

        try:
            # 解析化合物/元素组成
            compound_comp = self.parse_compound_formula(compound_formula)
            print(f"  组成: {self._format_comp(compound_comp)}")
        except ValueError as e:
            return {
                'status': 'error',
                'message': str(e),
                'equilibrium_phase': None,
                'matrix_phase': None
            }

        # 检查合金中是否含有化合物所需的所有元素
        missing_elements = [el for el in compound_comp if el not in alloy_composition or alloy_composition[el] < 1e-10]
        if missing_elements:
            return {
                'status': 'error',
                'message': f"合金中缺少化合物所需元素: {', '.join(missing_elements)}",
                'equilibrium_phase': None,
                'matrix_phase': None
            }

        # 计算形成能 ΔG_f（不含参考态）
        # 对于纯元素，形成能为 0
        if compound_gibbs_energy is not None:
            g_compound = compound_gibbs_energy
            print(f"  使用用户输入的形成能 ΔG_f: {g_compound:.2f} J/mol")
        else:
            g_compound = self._estimate_compound_gibbs_energy(
                compound_comp, compound_formula, temperature
            )
            if is_element:
                print(f"  纯元素形成能 ΔG_f: {g_compound:.2f} J/mol (按定义为0)")
            else:
                print(f"  估算的形成能 ΔG_f: {g_compound:.2f} J/mol")

        # ============ 关键：检查是否热力学稳定 ============
        is_stable, driving_force = self._check_compound_stability(
            alloy_composition, compound_comp, compound_formula, temperature,
            g_compound, extrapolation_func, extrapolation_model_name, activity_model
        )

        phase_desc = "纯元素" if is_element else "化合物"
        if not is_stable:
            print(f"  ⚠ {phase_desc} {compound_formula} 热力学不稳定，不会析出")
            print(f"  驱动力: {driving_force:.2f} J/mol (负值表示不析出)")
            return {
                'status': 'unstable',
                'message': f'{phase_desc} {compound_formula} 在当前条件下热力学不稳定，不会析出',
                'equilibrium_phase': {
                    'name': compound_formula,
                    'type': phase_type,
                    'composition': compound_comp,
                    'mole_fraction': 0.0,
                    'mass_fraction': 0.0,
                    'gibbs_energy': g_compound,
                    'is_stable': False,
                    'driving_force': driving_force
                },
                'matrix_phase': {
                    'name': self._find_lowest_energy_phase(alloy_composition, temperature),
                    'composition': alloy_composition,
                    'mole_fraction': 1.0
                },
                'calculation_details': {
                    'stability_check': 'failed',
                    'driving_force': driving_force,
                    'temperature': temperature
                }
            }

        print(f"  ✓ {phase_desc} {compound_formula} 热力学稳定，驱动力: {driving_force:.2f} J/mol (正值表示可析出)")

        # 计算最大生成量（受限元素约束）
        max_compound_fraction = float('inf')
        limiting_element = None

        for element, x_in_compound in compound_comp.items():
            x_in_alloy = alloy_composition.get(element, 0)
            if x_in_compound > 0:
                possible_fraction = x_in_alloy / x_in_compound
                if possible_fraction < max_compound_fraction:
                    max_compound_fraction = possible_fraction
                    limiting_element = element

        print(f"  受限元素: {limiting_element}")
        print(f"  最大{phase_desc}摩尔分数: {max_compound_fraction:.6f}")

        # 计算基体相（剩余组成）
        if max_compound_fraction >= 1.0:
            # 化合物完全消耗所有组分
            compound_fraction = 1.0
            matrix_comp = {}
            matrix_fraction = 0.0
        else:
            # 计算平衡化合物量（基于化学势平衡）
            compound_fraction, matrix_comp = self._solve_compound_equilibrium(
                alloy_composition, compound_comp, temperature,
                g_compound, max_compound_fraction,
                extrapolation_func, extrapolation_model_name, activity_model
            )
            matrix_fraction = 1.0 - compound_fraction

        print(f"\n  平衡{phase_desc}量: {compound_fraction:.6f} ({compound_fraction*100:.2f}%)")
        if matrix_comp:
            print(f"  基体相组成: {self._format_comp(matrix_comp)}")

        # 计算质量分数
        atomic_masses = self._get_atomic_masses()
        compound_mass = sum(compound_comp.get(el, 0) * atomic_masses.get(el, 50)
                          for el in compound_comp)
        alloy_mass = sum(alloy_composition.get(el, 0) * atomic_masses.get(el, 50)
                        for el in alloy_composition)
        mass_fraction = (compound_fraction * compound_mass) / alloy_mass if alloy_mass > 0 else 0

        # 确定基体相类型
        if matrix_comp:
            solvent = max(matrix_comp.items(), key=lambda x: x[1])[0]
            matrix_phase_name = self._find_lowest_energy_phase(matrix_comp, temperature)
        else:
            matrix_phase_name = "N/A"
            solvent = None

        return {
            'status': 'success',
            'message': f'成功计算{phase_desc} {compound_formula} 的平衡量',
            'equilibrium_phase': {
                'name': compound_formula,
                'type': phase_type,
                'composition': compound_comp,
                'mole_fraction': compound_fraction,
                'mass_fraction': mass_fraction,
                'gibbs_energy': g_compound,
                'is_stable': True,
                'driving_force': driving_force
            },
            'matrix_phase': {
                'name': matrix_phase_name,
                'composition': matrix_comp,
                'mole_fraction': matrix_fraction
            },
            'calculation_details': {
                'limiting_element': limiting_element,
                'max_possible_fraction': max_compound_fraction,
                'temperature': temperature,
                'compound_gibbs_energy_source': 'user_input' if compound_gibbs_energy is not None else 'estimated',
                'stability_check': 'passed',
                'driving_force': driving_force
            }
        }

    def _check_compound_stability(self,
                                   alloy_composition: Dict[str, float],
                                   compound_comp: Dict[str, float],
                                   compound_formula: str,
                                   temperature: float,
                                   g_compound: float,
                                   extrapolation_func,
                                   extrapolation_model_name: str,
                                   activity_model: str) -> Tuple[bool, float]:
        """
        检查化合物在当前条件下是否热力学稳定

        热力学原理:
        驱动力 ΔG = Σ(xᵢ · RT·ln(aᵢ)) - ΔG_f

        其中:
        - aᵢ = γᵢ·xᵢ 是元素在基体相中的活度
        - ΔG_f 是化合物的形成能（由 g_compound 参数传入）
        - RT·ln(aᵢ) 表示元素从标准态到溶液态的化学势变化

        这个公式直接使用活度项，避免了参考态的复杂处理。
        参考态能量（G°ᵢ）在化学势和化合物能量中相同，会自动抵消。

        判定:
        - ΔG > 0: 元素在基体中活度高，倾向形成化合物 → 可析出
        - ΔG < 0: 元素在基体中活度低，化合物不稳定 → 不析出
        - ΔG = 0: 平衡状态

        参数:
            g_compound: 化合物的形成能 ΔG_f (J/mol)，不含参考态

        返回:
            (is_stable, driving_force)
        """
        R = 8.314  # J/(mol·K)

        # 计算活度项的加权和: Σ(xᵢ · RT·ln(aᵢ))
        activity_term_sum = 0.0

        for element, x_in_compound in compound_comp.items():
            x_el = alloy_composition.get(element, 0)
            if x_el < 1e-15:
                # 元素不存在于合金中，无法形成化合物
                return False, float('-inf')

            # 计算活度系数 ln(γ)
            try:
                ln_gamma = self.calculate_ln_activity_coefficient(
                    alloy_composition, element, temperature,
                    'solid',  # 固态
                    extrapolation_func, extrapolation_model_name, activity_model
                )
                if ln_gamma is None:
                    ln_gamma = 0.0
            except Exception:
                ln_gamma = 0.0

            # 活度 a = γ·x, 所以 ln(a) = ln(γ) + ln(x)
            ln_activity = ln_gamma + math.log(x_el)

            # 累加: x_in_compound * RT * ln(a)
            activity_term_sum += x_in_compound * R * temperature * ln_activity

        # 驱动力 = 活度项 - 形成能
        # ΔG = Σ(xᵢ · RT·ln(aᵢ)) - ΔG_f
        driving_force = activity_term_sum - g_compound

        # 如果驱动力 > 0，化合物可以析出
        is_stable = driving_force > 0

        return is_stable, driving_force

    def _get_chemical_potential(self,
                                 composition: Dict[str, float],
                                 element: str,
                                 temperature: float,
                                 phase: str,
                                 extrapolation_func,
                                 extrapolation_model_name: str,
                                 activity_model: str) -> Optional[float]:
        """计算组分在溶液中的化学势"""
        x_el = composition.get(element, 0)
        if x_el < 1e-15:
            return None

        # 获取纯组分Gibbs能
        g_pure = self.tdb_parser.get_gibbs_energy(element, phase, temperature)
        if g_pure is None:
            g_pure = self.tdb_parser.get_gibbs_energy(element, 'SER', temperature)
        if g_pure is None:
            return None

        # 计算活度系数
        try:
            ln_gamma = self.calculate_ln_activity_coefficient(
                composition, element, temperature,
                'liquid' if phase == 'LIQUID' else 'solid',
                extrapolation_func, extrapolation_model_name, activity_model
            )
            if ln_gamma is None:
                ln_gamma = 0.0
        except:
            ln_gamma = 0.0

        # 化学势 μ = G° + RT*ln(γ*x)
        mu = g_pure + 8.314 * temperature * (math.log(x_el) + ln_gamma)
        return mu

    def _calculate_solution_phase_equilibrium(self,
                                               alloy_composition: Dict[str, float],
                                               solution_phase: str,
                                               temperature: float,
                                               extrapolation_func,
                                               extrapolation_model_name: str,
                                               activity_model: str) -> Dict:
        """计算溶体相的平衡组成"""
        print(f"[计算溶体相平衡: {solution_phase}]")

        # 确定溶剂
        solvent = max(alloy_composition.items(), key=lambda x: x[1])[0]
        print(f"  溶剂元素: {solvent}")

        # 获取标准相名称
        phase_mapping = {
            'LIQUID': 'LIQUID',
            'BCC': 'BCC_A2',
            'BCC_A2': 'BCC_A2',
            'FCC': 'FCC_A1',
            'FCC_A1': 'FCC_A1',
            'HCP': 'HCP_A3',
            'HCP_A3': 'HCP_A3',
        }
        tdb_phase = phase_mapping.get(solution_phase.upper(), solution_phase)

        # 计算各溶质的溶解度限
        solubility_limits = {}
        solution_comp = {solvent: 1.0}  # 从纯溶剂开始

        proxy_base = {solvent: 1.0}
        for element, x_alloy in alloy_composition.items():
            if element == solvent or x_alloy < 1e-10:
                continue

            try:
                sol_type = 'LIQUID' if 'LIQUID' in tdb_phase.upper() else 'SOLID'
                res = self.calculate_solubility(
                    base_alloy_composition=proxy_base,
                    solute_element=element,
                    solution_phase=sol_type,
                    temperature=temperature,
                    extrapolation_func=extrapolation_func,
                    extrapolation_model_name=extrapolation_model_name,
                    activity_model=activity_model
                )
                limit = res.get('solubility_mole_fraction', 1.0)
                if limit is None or limit > 1.0:
                    limit = 1.0
                solubility_limits[element] = limit
                print(f"  {element} 溶解度限: {limit:.6f}")
            except Exception as e:
                print(f"  {element} 溶解度计算失败: {e}")
                solubility_limits[element] = 1.0

        # 计算平衡溶体相组成
        # 考虑溶解度限制，计算实际溶入的量
        equilibrium_comp = {}
        sum_solutes = 0.0
        excess_elements = {}  # 超出溶解度的元素

        for element, x_alloy in alloy_composition.items():
            if element == solvent:
                continue

            limit = solubility_limits.get(element, 1.0)
            if x_alloy <= limit:
                # 全部溶入
                equilibrium_comp[element] = x_alloy
                sum_solutes += x_alloy
            else:
                # 部分溶入，有剩余
                equilibrium_comp[element] = limit
                sum_solutes += limit
                excess_elements[element] = x_alloy - limit

        equilibrium_comp[solvent] = 1.0 - sum_solutes

        # 归一化
        total_eq = sum(equilibrium_comp.values())
        equilibrium_comp = {k: v / total_eq for k, v in equilibrium_comp.items()}

        # 计算溶体相的摩尔分数
        # 如果有元素超出溶解度，则溶体相不是100%
        if excess_elements:
            # 计算溶体相分数
            solution_fraction = self._calculate_solution_fraction(
                alloy_composition, equilibrium_comp, excess_elements
            )
        else:
            solution_fraction = 1.0

        print(f"\n  溶体相组成: {self._format_comp(equilibrium_comp)}")
        print(f"  溶体相摩尔分数: {solution_fraction:.6f}")

        # 计算溶体相的吉布斯能
        g_solution = self._calculate_solution_gibbs_energy(
            equilibrium_comp, tdb_phase, temperature,
            extrapolation_func, extrapolation_model_name, activity_model
        )

        # 计算质量分数
        atomic_masses = self._get_atomic_masses()
        solution_mass = sum(equilibrium_comp.get(el, 0) * atomic_masses.get(el, 50)
                          for el in equilibrium_comp)
        alloy_mass = sum(alloy_composition.get(el, 0) * atomic_masses.get(el, 50)
                        for el in alloy_composition)
        mass_fraction = (solution_fraction * solution_mass) / alloy_mass if alloy_mass > 0 else solution_fraction

        return {
            'status': 'success',
            'message': f'成功计算溶体相 {solution_phase} 的平衡组成',
            'equilibrium_phase': {
                'name': tdb_phase,
                'type': 'solution',
                'composition': equilibrium_comp,
                'mole_fraction': solution_fraction,
                'mass_fraction': mass_fraction,
                'gibbs_energy': g_solution
            },
            'matrix_phase': None,  # 对于溶体相，本身就是基体
            'calculation_details': {
                'solubility_limits': solubility_limits,
                'excess_elements': excess_elements,
                'temperature': temperature,
                'solvent': solvent
            }
        }

    def _estimate_compound_gibbs_energy(self, compound_comp: Dict[str, float],
                                         compound_formula: str,
                                         temperature: float) -> float:
        """
        使用Miedema模型估算化合物的形成吉布斯能（ΔG_f）

        注意：返回的是形成能，不包含参考态能量。
        参考态能量会在 _check_compound_stability 中统一添加。

        对于纯元素（如 C, Si），形成能为 0（按定义）。
        对于多元化合物，使用二元交互作用的加权求和近似。
        """
        from itertools import combinations

        elements = list(compound_comp.keys())

        # 纯元素的形成能为 0
        if len(elements) == 1:
            return 0.0

        if len(elements) == 2:
            el1, el2 = elements
            x1 = compound_comp[el1]

            try:
                from models.miedema_model import MiedemaModel
                miedema = MiedemaModel((el1, el2), "SOLID")
                h_mix = miedema.getmixingEnthalpy_by_Miedema_Model(
                    el1, x1, temperature, order_degree='IM'
                )
                return h_mix
            except Exception as e:
                print(f"  警告: Miedema模型计算 {el1}-{el2} 失败: {e}")
                raise ValueError(f"无法计算 {compound_formula} 的形成能，请手动输入")

        # 多元化合物：使用二元交互作用的加权求和
        # ΔH_f ≈ Σ(xᵢ·xⱼ/(xᵢ+xⱼ) · ΔH_ij) 对所有 i<j 对
        total_h_mix = 0.0
        calculated_pairs = 0

        for el1, el2 in combinations(elements, 2):
            x1 = compound_comp[el1]
            x2 = compound_comp[el2]

            if x1 < 1e-10 or x2 < 1e-10:
                continue

            try:
                from models.miedema_model import MiedemaModel
                # 计算二元子系统中的摩尔分数
                x1_binary = x1 / (x1 + x2)
                miedema = MiedemaModel((el1, el2), "SOLID")
                h_binary = miedema.getmixingEnthalpy_by_Miedema_Model(
                    el1, x1_binary, temperature, order_degree='IM'
                )

                # 加权因子：考虑该二元对在多元体系中的贡献
                weight = (x1 * x2) / (x1 + x2)
                total_h_mix += weight * h_binary * 4  # 因子4来自正规溶液模型
                calculated_pairs += 1

            except Exception as e:
                print(f"  警告: Miedema模型计算 {el1}-{el2} 子系统失败: {e}")
                continue

        if calculated_pairs == 0:
            raise ValueError(f"无法计算 {compound_formula} 的形成能，请手动输入")

        return total_h_mix

    def _solve_compound_equilibrium(self, alloy_composition, compound_comp,
                                     temperature, g_compound, max_fraction,
                                     extrapolation_func, model_name, activity_model):
        """
        求解化合物平衡量

        热力学原理：
        - 通过二分法找到驱动力为零的平衡点
        - 驱动力 = Σ(xᵢ·μᵢ_matrix) - G_compound
        - 驱动力 > 0: 需要更多化合物析出
        - 驱动力 < 0: 化合物析出过多
        - 驱动力 = 0: 平衡状态
        """
        best_fraction = 0.0
        best_matrix_comp = alloy_composition.copy()

        # 二分法搜索平衡化合物量（驱动力为零的点）
        low, high = 0.0, min(max_fraction, 0.9999)

        # 首先检查初始驱动力
        initial_df = self._calculate_driving_force_for_fraction(
            alloy_composition, compound_comp, 0.0,
            temperature, g_compound, extrapolation_func, model_name, activity_model
        )

        # 如果初始驱动力为负，不析出
        if initial_df <= 0:
            return 0.0, alloy_composition.copy()

        # 检查最大析出量时的驱动力
        max_df = self._calculate_driving_force_for_fraction(
            alloy_composition, compound_comp, high,
            temperature, g_compound, extrapolation_func, model_name, activity_model
        )

        # 如果最大析出量时驱动力仍为正，使用最大析出量
        if max_df >= 0:
            # 计算最大析出量时的基体组成
            remaining = {}
            for el in alloy_composition:
                consumed = high * compound_comp.get(el, 0)
                remaining[el] = max(0, alloy_composition[el] - consumed)
            total_remaining = sum(remaining.values())
            if total_remaining > 1e-10:
                best_matrix_comp = {k: v / total_remaining for k, v in remaining.items()}
            return high, best_matrix_comp

        # 二分法搜索驱动力为零的平衡点
        for iteration in range(30):
            mid = (low + high) / 2.0

            # 计算该析出量下的驱动力
            df = self._calculate_driving_force_for_fraction(
                alloy_composition, compound_comp, mid,
                temperature, g_compound, extrapolation_func, model_name, activity_model
            )

            if abs(df) < 100:  # 驱动力足够小，认为达到平衡
                best_fraction = mid
                break

            if df > 0:
                # 驱动力为正，需要更多化合物析出
                low = mid
                best_fraction = mid
            else:
                # 驱动力为负，化合物析出过多
                high = mid

        # 计算最终基体组成
        remaining = {}
        for el in alloy_composition:
            consumed = best_fraction * compound_comp.get(el, 0)
            remaining[el] = max(0, alloy_composition[el] - consumed)

        total_remaining = sum(remaining.values())
        if total_remaining > 1e-10:
            best_matrix_comp = {k: v / total_remaining for k, v in remaining.items()}
        else:
            best_matrix_comp = {}

        return best_fraction, best_matrix_comp

    def _calculate_driving_force_for_fraction(self, alloy_composition, compound_comp,
                                               fraction, temperature, g_compound,
                                               extrapolation_func, model_name, activity_model):
        """
        计算给定析出量下的驱动力

        参数:
            g_compound: 化合物的形成能 ΔG_f (J/mol)，不含参考态

        驱动力 = Σ(xᵢ·RT·ln(aᵢ)) - ΔG_f
        其中 aᵢ = γᵢ·xᵢ 是元素在基体中的活度
        """
        R = 8.314  # J/(mol·K)

        # 计算剩余基体组成
        if fraction <= 0:
            matrix_comp = alloy_composition.copy()
        else:
            remaining = {}
            for el in alloy_composition:
                consumed = fraction * compound_comp.get(el, 0)
                remaining[el] = max(1e-15, alloy_composition[el] - consumed)

            total_remaining = sum(remaining.values())
            if total_remaining < 1e-10:
                return float('-inf')  # 所有元素都被消耗

            matrix_comp = {k: v / total_remaining for k, v in remaining.items()}

        # 计算活度项的加权和: Σ(xᵢ · RT·ln(aᵢ))
        activity_term_sum = 0.0

        for element, x_in_compound in compound_comp.items():
            x_el = matrix_comp.get(element, 0)
            if x_el < 1e-15:
                return float('-inf')  # 元素耗尽，不可能继续析出

            # 计算活度系数 ln(γ)
            try:
                ln_gamma = self.calculate_ln_activity_coefficient(
                    matrix_comp, element, temperature,
                    'solid',
                    extrapolation_func, model_name, activity_model
                )
                if ln_gamma is None:
                    ln_gamma = 0.0
            except Exception:
                ln_gamma = 0.0

            # 活度 a = γ·x, ln(a) = ln(γ) + ln(x)
            ln_activity = ln_gamma + math.log(x_el)

            # 累加: x_in_compound * RT * ln(a)
            activity_term_sum += x_in_compound * R * temperature * ln_activity

        # 驱动力 = 活度项 - 形成能
        return activity_term_sum - g_compound

    def _calculate_solution_fraction(self, alloy_composition, solution_comp, excess_elements):
        """计算溶体相的摩尔分数"""
        if not excess_elements:
            return 1.0

        # 简化：假设超出的元素形成析出相
        total_excess = sum(excess_elements.values())
        return 1.0 - total_excess

    def _calculate_solution_gibbs_energy(self, composition, phase, temperature,
                                          extrapolation_func, model_name, activity_model):
        """计算溶体相的吉布斯能"""
        g_total = 0.0

        # 参考态能量
        for el, x in composition.items():
            if x < 1e-10:
                continue
            g_pure = self.tdb_parser.get_gibbs_energy(el, phase, temperature)
            if g_pure is None:
                g_pure = self.tdb_parser.get_gibbs_energy(el, 'SER', temperature)
            if g_pure is not None:
                g_total += x * g_pure

        # 混合熵贡献
        R = 8.314
        for x in composition.values():
            if x > 1e-10:
                g_total += R * temperature * x * math.log(x)

        # 过剩吉布斯能（简化处理）
        # 实际应该通过外推模型计算

        return g_total

    def _find_lowest_energy_phase(self, composition, temperature):
        """找到能量最低的相"""
        solvent = max(composition.items(), key=lambda x: x[1])[0]
        phases = [p for p in self.tdb_parser.get_element_phases(solvent) if p != 'GAS']
        best_phase = 'FCC_A1'
        min_g = float('inf')
        for phase in phases:
            try:
                g_pure = self.tdb_parser.get_gibbs_energy(solvent, phase, temperature)
                if g_pure is not None and g_pure < min_g:
                    min_g = g_pure
                    best_phase = phase
            except:
                continue
        return best_phase

    def _get_atomic_masses(self):
        """获取原子质量表"""
        return {
            'FE': 55.845, 'C': 12.011, 'SI': 28.085, 'MN': 54.938,
            'CR': 51.996, 'NI': 58.693, 'MO': 95.94, 'CU': 63.546,
            'AL': 26.982, 'TI': 47.867, 'V': 50.942, 'W': 183.84,
            'CO': 58.933, 'N': 14.007, 'P': 30.974, 'S': 32.065,
            'NB': 92.906, 'ZR': 91.224, 'B': 10.81, 'O': 15.999,
            'MG': 24.305, 'ZN': 65.38, 'SN': 118.71, 'PB': 207.2
        }

    def _format_comp(self, comp):
        """格式化输出组成"""
        if not comp:
            return "N/A"
        return ", ".join([f"{k}:{v:.4f}" for k, v in comp.items() if v > 1e-6])


# =============================================================================
# 便捷函数
# =============================================================================

def calculate_phase_equilibrium(alloy_composition: Dict[str, float],
                                temperature: float,
                                method: str = 'solubility',
                                **kwargs) -> List[Dict]:
    """
    便捷函数：计算相平衡

    参数:
        alloy_composition: 合金组成
        temperature: 温度 (K)
        method: 计算方法
            - 'solubility': 溶解度约束法（默认）
            - 'compound': 化合物感知法
        **kwargs: 传递给计算器的其他参数

    返回:
        相平衡结果列表
    """
    if method == 'compound':
        calculator = CompoundAwarePhaseEquilibrium()
    else:
        calculator = PhaseEquilibriumCalculator()

    return calculator.calculate_phase_equilibrium(alloy_composition, temperature, **kwargs)


# =============================================================================
# 测试入口
# =============================================================================
if __name__ == '__main__':
    from models.extrapolation_models import BinaryModel

    model_func = BinaryModel().UEM1

    # 测试案例
    my_alloy = {'AL': 0.70, 'FE': 0.14, 'MG': 0.16}
    T_test = 400.0

    print("=" * 70)
    print("测试溶解度约束法")
    print("=" * 70)
    calc1 = PhaseEquilibriumCalculator()
    results1 = calc1.calculate_phase_equilibrium(my_alloy, T_test, extrapolation_model_func=model_func)

    print("\n" + "=" * 70)
    print("测试化合物感知法")
    print("=" * 70)
    calc2 = CompoundAwarePhaseEquilibrium()
    results2 = calc2.calculate_phase_equilibrium(my_alloy, T_test, extrapolation_model_func=model_func)
