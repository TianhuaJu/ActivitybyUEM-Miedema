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
