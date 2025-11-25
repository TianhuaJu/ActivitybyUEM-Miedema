"""
Phase Equilibrium Calculator v2.0 - Recursive Phase Separation Algorithm
==========================================================================
相平衡计算模块 - 递归相分离算法

算法原理（完全按照用户描述实现）：

步骤1：判断给定合金组成的相稳定性
    - 如果稳定 → 单一相，算法结束
    - 如果不稳定 → 进入步骤2

步骤2：找出吉布斯自由能最小的相作为基础相
    - 计算该合金在所有候选相中的吉布斯能量
    - 选择能量最低的相作为"主相"

步骤3：计算其他元素在主相中的最大溶解度
    - 对主相中除溶剂外的每个元素，计算其最大溶解度
    - 按最大溶解度固定主相组成
    - 记录析出的元素和数量

步骤4：处理剩余成分（递归）
    - 剩余成分构成新的基础合金
    - 递归执行步骤1-3
    - 直至所有成分都处于稳定相中

步骤5：根据物质守恒计算各相的相分数

作者: Claude
版本: v2.0
日期: 2025-11-23
"""

import math
import sys
import os
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from copy import deepcopy

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations.phase_diagram import PhaseDiagramCalculator
from models.extrapolation_models import BinaryModel


@dataclass
class PhaseInfo:
    """相信息数据类"""
    name: str  # 相名称
    composition: Dict[str, float] = field(default_factory=dict)  # 相组成（摩尔分数）
    absolute_moles: float = 0.0  # 该相的绝对摩尔数（用于计算相分数）
    gibbs_energy: float = 0.0  # 摩尔吉布斯能量 (J/mol)
    fraction: float = 0.0  # 相分数（在物质守恒计算后填充）


class RecursivePhaseEquilibriumCalculator(PhaseDiagramCalculator):
    """
    递归相平衡计算器

    完全按照用户描述的算法实现：
    1. 判断稳定性
    2. 找能量最低的相
    3. 计算溶解度
    4. 递归处理剩余成分
    5. 物质守恒计算相分数
    """

    def __init__(self):
        super().__init__()
        self.binary_model = BinaryModel()

        # 候选相列表
        self.candidate_phases = ['LIQUID', 'BCC_A2', 'FCC_A1', 'HCP_A3']

        # 算法参数
        self.max_recursion_depth = 20  # 最大递归深度
        self.min_mole_threshold = 1e-9  # 最小摩尔数阈值
        self.stability_tolerance = 10.0  # 稳定性判据容差 (J/mol)

    def calculate_phase_equilibrium(self,
                                    total_composition: Dict[str, float],
                                    temperature: float,
                                    extrapolation_model_func: Callable = None,
                                    extrapolation_model_name: str = 'UEM1',
                                    activity_model: str = 'Wagner') -> Dict:
        """
        计算相平衡的主入口函数

        参数:
            total_composition: 总组成 {元素: 摩尔分数}
            temperature: 温度 (K)
            extrapolation_model_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型

        返回:
            {
                'status': 状态,
                'temperature': 温度,
                'total_composition': 总组成,
                'phases': [PhaseInfo, ...],
                'message': 消息,
                'calculation_log': 计算日志
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

        # 初始化计算日志
        calc_log = []
        calc_log.append(f"=== 开始相平衡计算 ===")
        calc_log.append(f"总组成: {comp_norm}")
        calc_log.append(f"温度: {temperature} K")
        calc_log.append("")

        # 递归相分离
        phases = []
        try:
            self._recursive_phase_separation(
                remaining_composition=comp_norm,
                total_moles=1.0,  # 初始总摩尔数为1
                temperature=temperature,
                extrapolation_model_func=extrapolation_model_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model,
                depth=0,
                phases=phases,
                calc_log=calc_log
            )
        except Exception as e:
            calc_log.append(f"错误: {str(e)}")
            return {
                'status': 'error',
                'message': f'计算失败: {str(e)}',
                'phases': [],
                'calculation_log': calc_log
            }

        # 计算相分数（物质守恒）
        self._calculate_phase_fractions(phases, calc_log)

        # 计算总吉布斯能量
        total_gibbs = sum(p.fraction * p.gibbs_energy for p in phases)

        calc_log.append("")
        calc_log.append(f"=== 计算完成 ===")
        calc_log.append(f"平衡相数: {len(phases)}")
        calc_log.append(f"总吉布斯能量: {total_gibbs:.2f} J/mol")

        return {
            'status': 'success',
            'temperature': temperature,
            'total_composition': comp_norm,
            'phases': phases,
            'total_gibbs_energy': total_gibbs,
            'message': f'成功计算出 {len(phases)} 个平衡相',
            'calculation_log': calc_log
        }

    def _recursive_phase_separation(self,
                                    remaining_composition: Dict[str, float],
                                    total_moles: float,
                                    temperature: float,
                                    extrapolation_model_func: Callable,
                                    extrapolation_model_name: str,
                                    activity_model: str,
                                    depth: int,
                                    phases: List[PhaseInfo],
                                    calc_log: List[str]):
        """
        递归相分离核心函数

        参数:
            remaining_composition: 剩余组成
            total_moles: 剩余总摩尔数
            temperature: 温度
            extrapolation_model_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型
            depth: 当前递归深度
            phases: 相列表（输出）
            calc_log: 计算日志（输出）
        """

        # 递归深度检查
        if depth >= self.max_recursion_depth:
            calc_log.append(f"  [警告] 达到最大递归深度 {self.max_recursion_depth}")
            return

        # 摩尔数检查
        if total_moles < self.min_mole_threshold:
            calc_log.append(f"  [信息] 剩余摩尔数过小，忽略")
            return

        indent = "  " * depth
        calc_log.append(f"{indent}>>> 递归深度 {depth}")
        calc_log.append(f"{indent}剩余组成: {remaining_composition}")
        calc_log.append(f"{indent}剩余摩尔数: {total_moles:.6f}")

        # ===== 步骤1: 判断相稳定性 =====
        is_stable, stable_phase, issues = self._check_composition_stability(
            remaining_composition, temperature,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )

        if is_stable:
            # 稳定 → 单一相，递归结束
            calc_log.append(f"{indent}[稳定] 组成在 {stable_phase} 相中稳定")

            # 计算该相的吉布斯能量
            G = self.calculate_single_phase_energy(
                remaining_composition, temperature, stable_phase,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )

            phase_info = PhaseInfo(
                name=stable_phase,
                composition=remaining_composition.copy(),
                absolute_moles=total_moles,
                gibbs_energy=G if G is not None else 0.0
            )
            phases.append(phase_info)
            calc_log.append(f"{indent}添加相: {stable_phase}, G={G:.2f} J/mol")
            calc_log.append("")
            return

        # 不稳定 → 需要相分离
        calc_log.append(f"{indent}[不稳定] 需要相分离")
        calc_log.append(f"{indent}原因: {'; '.join(issues[:3])}")

        # ===== 步骤2: 找吉布斯自由能最小的相作为基础相 =====
        best_phase, best_energy = self._find_lowest_energy_phase(
            remaining_composition, temperature,
            extrapolation_model_func, extrapolation_model_name, activity_model,
            calc_log, indent
        )

        if best_phase is None:
            calc_log.append(f"{indent}[错误] 无法找到合适的基础相")
            return

        calc_log.append(f"{indent}选择基础相: {best_phase} (G={best_energy:.2f} J/mol)")

        # ===== 步骤3: 计算其他元素在基础相中的最大溶解度 =====
        # 确定溶剂（含量最多的元素）
        solvent = max(remaining_composition.items(), key=lambda x: x[1])[0]
        solutes = [elem for elem in remaining_composition if elem != solvent]

        calc_log.append(f"{indent}溶剂: {solvent}")
        calc_log.append(f"{indent}溶质: {solutes}")

        # 计算每个溶质的最大溶解度
        phase_composition = {solvent: 1.0}  # 初始只有溶剂
        precipitated_amounts = {}  # 析出的元素及数量

        for solute in solutes:
            calc_log.append(f"{indent}  计算 {solute} 在 {best_phase} 中的溶解度...")

            # 构建基础合金（溶剂 + 已溶解的其他元素）
            base_alloy = phase_composition.copy()

            # 确定相态
            solution_phase_type = 'LIQUID' if best_phase == 'LIQUID' else 'SOLID'

            # 计算溶解度
            solubility_result = self.calculate_solubility(
                base_alloy_composition=base_alloy,
                solute_element=solute,
                solution_phase=solution_phase_type,
                temperature=temperature,
                extrapolation_func=extrapolation_model_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model
            )

            if solubility_result['status'] in ['success', 'fully_soluble']:
                max_solubility = solubility_result['solubility_mole_fraction']
                calc_log.append(f"{indent}    最大溶解度: {max_solubility:.6f}")

                # 可用的溶质摩尔数（相对于总组成）
                available_solute = remaining_composition[solute]

                # 实际溶解量（取最小值）
                dissolved = min(max_solubility, available_solute)

                if dissolved < available_solute:
                    # 有析出
                    precipitated = available_solute - dissolved
                    precipitated_amounts[solute] = precipitated
                    calc_log.append(f"{indent}    溶解: {dissolved:.6f}, 析出: {precipitated:.6f}")
                else:
                    # 完全溶解
                    calc_log.append(f"{indent}    完全溶解")

                # 更新相组成
                phase_composition[solute] = dissolved
            else:
                # 溶解度计算失败，假设不溶
                calc_log.append(f"{indent}    [警告] 溶解度计算失败，假设不溶")
                precipitated_amounts[solute] = remaining_composition[solute]

        # 归一化相组成
        total_in_phase = sum(phase_composition.values())
        if total_in_phase > 0:
            phase_composition = {k: v/total_in_phase for k, v in phase_composition.items()}

        # 计算该相的实际摩尔数（基于物质平衡）
        # 该相包含的总摩尔分数（相对于剩余组成）
        phase_mole_fraction = sum(phase_composition.get(elem, 0) * remaining_composition.get(elem, 0)
                                   for elem in phase_composition)
        phase_moles = total_moles * phase_mole_fraction

        # 计算该相的吉布斯能量
        G = self.calculate_single_phase_energy(
            phase_composition, temperature, best_phase,
            extrapolation_model_func, extrapolation_model_name, activity_model
        )

        # 添加相
        phase_info = PhaseInfo(
            name=best_phase,
            composition=phase_composition,
            absolute_moles=phase_moles,
            gibbs_energy=G if G is not None else 0.0
        )
        phases.append(phase_info)
        calc_log.append(f"{indent}添加相: {best_phase}, 组成: {phase_composition}")
        calc_log.append(f"{indent}该相摩尔数: {phase_moles:.6f}, G={G:.2f} J/mol")

        # ===== 步骤4: 处理剩余成分（递归） =====
        if len(precipitated_amounts) > 0:
            calc_log.append(f"{indent}析出元素: {precipitated_amounts}")

            # 计算剩余组成
            remaining_total = sum(precipitated_amounts.values())
            if remaining_total > self.min_mole_threshold:
                new_remaining_composition = {k: v/remaining_total for k, v in precipitated_amounts.items()}
                new_total_moles = total_moles - phase_moles

                calc_log.append(f"{indent}递归处理剩余成分...")
                calc_log.append("")

                # 递归调用
                self._recursive_phase_separation(
                    remaining_composition=new_remaining_composition,
                    total_moles=new_total_moles,
                    temperature=temperature,
                    extrapolation_model_func=extrapolation_model_func,
                    extrapolation_model_name=extrapolation_model_name,
                    activity_model=activity_model,
                    depth=depth + 1,
                    phases=phases,
                    calc_log=calc_log
                )
            else:
                calc_log.append(f"{indent}剩余量过小，忽略")
        else:
            calc_log.append(f"{indent}所有元素完全溶解，无需进一步递归")

        calc_log.append("")

    def _check_composition_stability(self,
                                     composition: Dict[str, float],
                                     temperature: float,
                                     extrapolation_model_func: Callable,
                                     extrapolation_model_name: str,
                                     activity_model: str) -> Tuple[bool, Optional[str], List[str]]:
        """
        检查给定组成的相稳定性

        返回:
            (is_stable, stable_phase_name, issues)
        """

        # 对每个候选相检查稳定性
        for phase_name in self.candidate_phases:
            stable, issues = self._check_alloy_full_stability(
                composition=composition,
                temperature=temperature,
                tdb_phase=phase_name,
                extrapolation_func=extrapolation_model_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model,
                tolerance=self.stability_tolerance
            )

            if stable:
                return True, phase_name, []

        # 所有相都不稳定
        return False, None, issues if 'issues' in locals() else ['所有候选相都不稳定']

    def _find_lowest_energy_phase(self,
                                   composition: Dict[str, float],
                                   temperature: float,
                                   extrapolation_model_func: Callable,
                                   extrapolation_model_name: str,
                                   activity_model: str,
                                   calc_log: List[str],
                                   indent: str) -> Tuple[Optional[str], float]:
        """
        找出吉布斯自由能最小的相

        返回:
            (phase_name, gibbs_energy)
        """

        best_phase = None
        best_energy = float('inf')

        for phase_name in self.candidate_phases:
            G = self.calculate_single_phase_energy(
                composition, temperature, phase_name,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )

            if G is not None:
                calc_log.append(f"{indent}  {phase_name}: G={G:.2f} J/mol")
                if G < best_energy:
                    best_energy = G
                    best_phase = phase_name

        return best_phase, best_energy

    def calculate_single_phase_energy(self,
                                      composition: Dict[str, float],
                                      temperature: float,
                                      phase_name: str,
                                      extrapolation_model_func: Callable,
                                      extrapolation_model_name: str,
                                      activity_model: str) -> Optional[float]:
        """
        计算单相的摩尔吉布斯自由能

        G = Σ(xᵢ × μᵢ)
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

                # 获取化学势
                mu_i = self._get_chemical_potential_phase(
                    comp_norm, element, temperature, phase_name,
                    extrapolation_model_func, extrapolation_model_name, activity_model
                )

                if mu_i is None:
                    return None

                G_total += x_i * mu_i

            return G_total

        except Exception:
            return None

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

    def _calculate_phase_fractions(self, phases: List[PhaseInfo], calc_log: List[str]):
        """
        根据物质守恒计算各相的相分数

        f_α = n_α / Σn_i
        """
        calc_log.append("=== 计算相分数（物质守恒） ===")

        total_moles = sum(p.absolute_moles for p in phases)

        if total_moles > 0:
            for phase in phases:
                phase.fraction = phase.absolute_moles / total_moles
                calc_log.append(f"  {phase.name}: {phase.fraction:.4f} ({phase.fraction*100:.2f}%)")
        else:
            calc_log.append("  [警告] 总摩尔数为0")

    # ===== 温度/组分变化分析（复用之前的实现） =====

    def calculate_phase_equilibrium_vs_temperature(self,
                                                   total_composition: Dict[str, float],
                                                   T_min: float,
                                                   T_max: float,
                                                   n_points: int = 50,
                                                   extrapolation_model_func: Callable = None,
                                                   extrapolation_model_name: str = 'UEM1',
                                                   activity_model: str = 'Wagner',
                                                   progress_callback: Callable = None) -> Dict:
        """计算相平衡随温度的变化"""

        if extrapolation_model_func is None:
            extrapolation_model_func = self.binary_model.UEM1

        import numpy as np
        temperatures = np.linspace(T_min, T_max, n_points)
        results = []
        phase_fractions = {}

        for i, T in enumerate(temperatures):
            if progress_callback:
                progress_callback(i + 1, n_points)

            result = self.calculate_phase_equilibrium(
                total_composition, T,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )

            results.append(result)

            # 记录相分数
            if result['status'] == 'success':
                for phase_info in result['phases']:
                    if phase_info.name not in phase_fractions:
                        phase_fractions[phase_info.name] = []
                    phase_fractions[phase_info.name].append(phase_info.fraction)

                # 填充缺失的相
                for phase_name in self.candidate_phases:
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
        """计算相平衡随组分的变化"""

        if extrapolation_model_func is None:
            extrapolation_model_func = self.binary_model.UEM1

        import numpy as np
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

            result = self.calculate_phase_equilibrium(
                current_comp, temperature,
                extrapolation_model_func, extrapolation_model_name, activity_model
            )

            results.append(result)

            # 记录相分数
            if result['status'] == 'success':
                for phase_info in result['phases']:
                    if phase_info.name not in phase_fractions:
                        phase_fractions[phase_info.name] = []
                    phase_fractions[phase_info.name].append(phase_info.fraction)

                # 填充缺失的相
                for phase_name in self.candidate_phases:
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
