"""
析出温度计算模块 (Precipitation Temperature Calculator)
=======================================================
基于UEM-Miedema模型框架计算溶质的析出温度

核心热力学原理：
-----------------
在温度T下，当溶质i的化学势等于析出相的标准Gibbs能时，达到相平衡：

    μᵢ(solution) = Gᵢ°(precipitate)

其中：
    μᵢ = Gᵢ°(solution) + RT·ln(aᵢ)
    aᵢ = γᵢ · xᵢ  (活度 = 活度系数 × 摩尔分数)

平衡条件展开为：
    Gᵢ°(solution, T) + RT·ln(γᵢ·xᵢ) = Gᵢ°(precipitate, T)

当xᵢ已知时，求解满足此方程的T即为析出温度。

物理意义：
- T < T_precipitation: 溶质过饱和，析出相热力学稳定
- T > T_precipitation: 溶质欠饱和，溶液相热力学稳定
- T = T_precipitation: 两相平衡共存

"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple
from scipy.optimize import brentq, minimize_scalar
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations.thermodynamic_properties import ThermodynamicProperties


class PrecipitationTemperatureCalculator(ThermodynamicProperties):
    """
    析出温度计算器

    基于热力学平衡条件：μ_solute(solution) = G°(precipitate)

    支持的计算模式：
    1. 单点计算：给定合金成分，计算析出温度
    2. 成分曲线：给定基础合金，计算析出温度随溶质含量的变化
    3. 多溶质系统：计算多种溶质各自的析出温度
    """

    # 相稳定性判断阈值 (J/mol)
    PHASE_EXCLUSION_THRESHOLD = 200.0

    def __init__(self):
        super().__init__()

    def _determine_matrix_phase(
        self,
        composition: Dict[str, float],
        temperature: float,
        extrapolation_func,
        extrapolation_model_name: str,
        activity_model: str
    ) -> Tuple[str, str, List[str]]:
        """
        自动判断基体相态

        热力学原理：
        -----------
        1. 首先获取溶剂元素在给定温度下的稳定相作为参考
        2. 基于溶剂的稳定相筛选候选相（排除能量差过大的不稳定相）
        3. 计算合金在各候选相中的总Gibbs能量
        4. 选择能量最低的相作为基体相

        参数：
        -----
        composition : 合金成分（摩尔分数）
        temperature : 温度 (K)
        extrapolation_func : 外推模型函数
        extrapolation_model_name : 外推模型名称
        activity_model : 活度模型

        返回：
        -----
        Tuple[str, str, List[str]]:
            - 基体相名称（如 'BCC_A2', 'FCC_A1', 'LIQUID'）
            - 相态描述（如 '固相 (BCC_A2)', '液相'）
            - 警告信息列表
        """
        warnings = []

        # 找出溶剂元素
        solvent = max(composition.items(), key=lambda item: item[1])[0]

        # 获取溶剂的稳定相
        solvent_stable_phase = self.tdb_parser.get_stable_phase(solvent, temperature)
        if not solvent_stable_phase:
            solvent_stable_phase = self.tdb_parser.get_reference_phase(solvent)
            warnings.append(f"无法获取 {solvent} 在 {temperature}K 的稳定相，使用参考相 {solvent_stable_phase}")

        g_solvent_stable = self.tdb_parser.get_gibbs_energy(solvent, solvent_stable_phase, temperature)

        # 获取所有候选相
        all_phases = self.tdb_parser.get_element_phases(solvent)
        if not all_phases:
            # 使用默认相列表
            all_phases = ['BCC_A2', 'FCC_A1', 'HCP_A3', 'LIQUID']
            warnings.append(f"无法获取 {solvent} 的相列表，使用默认相")

        # 排除GAS相，保留其他相
        candidate_phases = [p for p in all_phases if p != 'GAS']
        if 'LIQUID' not in candidate_phases:
            candidate_phases.append('LIQUID')

        # 基于溶剂稳定性筛选候选相
        filtered_phases = []
        for phase in candidate_phases:
            g_solvent_phase = self.tdb_parser.get_gibbs_energy(solvent, phase, temperature)
            if g_solvent_phase is None:
                g_solvent_phase = self._estimate_lattice_stability(solvent, phase, temperature)

            if g_solvent_phase is not None and g_solvent_stable is not None:
                energy_diff = g_solvent_phase - g_solvent_stable
                if energy_diff <= self.PHASE_EXCLUSION_THRESHOLD:
                    filtered_phases.append(phase)
            else:
                # 无法计算能量时，保守地保留该相
                filtered_phases.append(phase)

        # 确保溶剂稳定相在列表中
        if solvent_stable_phase not in filtered_phases:
            filtered_phases.insert(0, solvent_stable_phase)

        # 计算各相的总Gibbs能量，选择最低的
        best_phase = solvent_stable_phase
        min_energy = float('inf')

        for phase in filtered_phases:
            current_energy = 0.0
            valid = True

            for el, x_el in composition.items():
                if x_el < 1e-12:
                    continue

                mu = self._get_chemical_potential_extended(
                    composition=composition,
                    component=el,
                    temperature=temperature,
                    tdb_phase=phase,
                    extrapolation_func=extrapolation_func,
                    extrapolation_model=extrapolation_model_name,
                    activity_model=activity_model
                )

                if mu is None:
                    valid = False
                    break
                current_energy += x_el * mu

            if valid and current_energy < min_energy:
                min_energy = current_energy
                best_phase = phase

        # 生成相态描述
        if best_phase == 'LIQUID':
            phase_desc = "液相"
        else:
            phase_desc = f"固相 ({best_phase})"

        return best_phase, phase_desc, warnings

    def calculate_precipitation_temperature_auto(
        self,
        alloy_composition: Dict[str, float],
        solute_element: str,
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner',
        T_min: float = 300.0,
        T_max: float = 3000.0,
        tolerance: float = 1.0
    ) -> dict:
        """
        自动判断基体相态的析出温度计算（推荐使用）

        热力学原理：
        -----------
        1. 在每个温度T下，自动判断基体相态（固相/液相）
        2. 计算溶质在当前相中的化学势 μ_solute
        3. 比较 μ_solute 与析出相的 G°
        4. 找到 μ_solute = G°_precipitate 的温度即为析出温度

        特点：
        ------
        - 无需人为指定基体相，自动根据温度和成分判断
        - 严格遵循热力学平衡原理
        - 通用性强，适用于任意合金体系
        - 数据缺失时给出明确提示

        参数：
        -----
        alloy_composition : Dict[str, float]
            合金成分（摩尔分数），如 {'FE': 0.95, 'C': 0.02, 'SI': 0.03}
        solute_element : str
            溶质元素符号，如 'C', 'N', 'TI'
        extrapolation_func : callable
            外推模型函数
        extrapolation_model_name : str
            外推模型名称: 'UEM1', 'UEM2', 'GSM', 'Muggianu'
        activity_model : str
            活度模型: 'Wagner', 'Darken', 'Elliott'
        T_min, T_max : float
            温度搜索范围 (K)
        tolerance : float
            温度求解精度 (K)

        返回：
        -----
        dict : 完整的计算结果
        """
        # ==================== 1. 预处理与验证 ====================
        solute = solute_element.upper()
        warnings = []
        data_issues = []

        # 归一化成分
        total = sum(alloy_composition.values())
        if total <= 0:
            return {
                'status': 'error',
                'message': '合金成分不能为空',
                'precipitation_temperature': None
            }

        composition = {k.upper(): v / total for k, v in alloy_composition.items()}

        # 验证溶质
        if solute not in composition:
            return {
                'status': 'error',
                'message': f'溶质 {solute} 不在合金成分中',
                'precipitation_temperature': None,
                'hint': f'当前成分包含: {list(composition.keys())}'
            }

        x_solute = composition[solute]
        if x_solute <= 0:
            return {
                'status': 'error',
                'message': f'溶质 {solute} 含量必须大于0',
                'precipitation_temperature': None
            }

        # 确定溶剂
        solvent = max(composition.items(), key=lambda item: item[1])[0]

        # ==================== 2. 检查热力学数据可用性 ====================
        # 检查析出相数据
        precipitating_phase = self.tdb_parser.get_stable_phase(solute, T_min)
        if not precipitating_phase:
            precipitating_phase = self.tdb_parser.get_reference_phase(solute)
            if not precipitating_phase:
                data_issues.append(f"无法获取溶质 {solute} 的稳定相信息")

        # 尝试获取析出相Gibbs能量（仅当析出相已确定时）
        if precipitating_phase is not None:
            g_test = self.tdb_parser.get_gibbs_energy(solute, precipitating_phase, (T_min + T_max) / 2)
            if g_test is None:
                # 尝试晶格稳定性估算
                g_test = self._estimate_lattice_stability(solute, precipitating_phase, (T_min + T_max) / 2)
                if g_test is None:
                    data_issues.append(f"无法获取 {solute} 在 {precipitating_phase} 相的Gibbs能量")

        # 如果存在严重的数据问题，返回错误并给出提示
        if data_issues:
            return {
                'status': 'data_missing',
                'message': '热力学数据不完整，无法完成计算',
                'precipitation_temperature': None,
                'data_issues': data_issues,
                'hint': '请检查TDB数据库是否包含所需元素和相的数据',
                'solute': solute,
                'solute_content': x_solute
            }

        # ==================== 3. 定义驱动力函数 ====================
        phase_at_T = {}  # 记录每个温度下的基体相

        def driving_force(T: float) -> Optional[float]:
            """
            计算析出驱动力：ΔG = μ_solute - G°_precipitate

            - ΔG > 0: 溶质在溶液中化学势高于析出相，过饱和（析出倾向）
            - ΔG < 0: 溶质在溶液中化学势低于析出相，欠饱和（稳定）
            - ΔG = 0: 平衡状态（析出温度）
            """
            # 自动判断当前温度下的基体相
            matrix_phase, _, _ = self._determine_matrix_phase(
                composition, T, extrapolation_func,
                extrapolation_model_name, activity_model
            )
            phase_at_T[T] = matrix_phase

            # 计算溶质的化学势
            mu_solute = self._get_chemical_potential_extended(
                composition=composition,
                component=solute,
                temperature=T,
                tdb_phase=matrix_phase,
                extrapolation_func=extrapolation_func,
                extrapolation_model=extrapolation_model_name,
                activity_model=activity_model
            )

            if mu_solute is None:
                return None

            # 获取当前温度下析出相的Gibbs能量
            current_precip_phase = self.tdb_parser.get_stable_phase(solute, T)
            if not current_precip_phase:
                current_precip_phase = precipitating_phase

            g_precipitate = self.tdb_parser.get_gibbs_energy(solute, current_precip_phase, T)
            if g_precipitate is None:
                g_precipitate = self._estimate_lattice_stability(solute, current_precip_phase, T)

            if g_precipitate is None:
                return None

            return mu_solute - g_precipitate

        # ==================== 4. 评估边界条件 ====================
        df_min = driving_force(T_min)
        df_max = driving_force(T_max)

        if df_min is None or df_max is None:
            return {
                'status': 'calculation_error',
                'message': '无法计算驱动力，请检查热力学数据',
                'precipitation_temperature': None,
                'solute': solute,
                'solute_content': x_solute,
                'hint': '可能是活度系数计算失败或Gibbs能量数据缺失'
            }

        # ==================== 5. 分析并求解 ====================
        result = {
            'solute': solute,
            'solute_content': x_solute,
            'solvent': solvent,
            'precipitating_phase': precipitating_phase,
            'driving_force_at_T_min': df_min,
            'driving_force_at_T_max': df_max,
            'composition': composition,
            'method': 'thermodynamic_equilibrium',
            'phase_determination': 'automatic'
        }

        # 情况1: 两边同号 - 无析出温度
        # ΔG > 0: 过饱和（析出倾向）; ΔG < 0: 欠饱和（稳定）
        if df_min > 0 and df_max > 0:
            result['status'] = 'always_supersaturated'
            result['precipitation_temperature'] = None
            result['precipitation_temperature_celsius'] = None
            result['message'] = f'在 {T_min}-{T_max}K 范围内，溶质始终过饱和'
            result['hint'] = '析出温度可能高于搜索范围上限，请尝试增大T_max'
            result['matrix_phase_at_T_min'] = phase_at_T.get(T_min, 'Unknown')
            result['matrix_phase_at_T_max'] = phase_at_T.get(T_max, 'Unknown')
            return result

        if df_min < 0 and df_max < 0:
            result['status'] = 'always_undersaturated'
            result['precipitation_temperature'] = None
            result['precipitation_temperature_celsius'] = None
            result['message'] = f'在 {T_min}-{T_max}K 范围内，溶质始终欠饱和，不会析出'
            result['matrix_phase_at_T_min'] = phase_at_T.get(T_min, 'Unknown')
            result['matrix_phase_at_T_max'] = phase_at_T.get(T_max, 'Unknown')
            return result

        # 情况2: 两边异号 - 存在析出温度
        try:
            def solve_func(T):
                df = driving_force(T)
                return df if df is not None else 1e10

            T_precip = brentq(solve_func, T_min, T_max, xtol=tolerance)

            # 获取析出温度处的基体相
            matrix_phase_at_Tp, phase_desc, phase_warnings = self._determine_matrix_phase(
                composition, T_precip, extrapolation_func,
                extrapolation_model_name, activity_model
            )
            warnings.extend(phase_warnings)

            # 验证结果
            df_check = driving_force(T_precip)

            result['status'] = 'success'
            result['precipitation_temperature'] = float(T_precip)
            result['precipitation_temperature_celsius'] = float(T_precip - 273.15)
            result['matrix_phase'] = matrix_phase_at_Tp
            result['matrix_phase_description'] = phase_desc
            result['message'] = '析出温度计算成功'
            result['residual'] = df_check
            result['warnings'] = warnings if warnings else None

            # 计算析出温度处的活度系数
            activity_phase = 'liquid' if matrix_phase_at_Tp == 'LIQUID' else 'solid'
            ln_gamma = self.calculate_ln_activity_coefficient(
                composition, solute, T_precip, activity_phase,
                extrapolation_func, extrapolation_model_name, activity_model
            )
            if ln_gamma is not None:
                result['activity_coefficient_at_Tp'] = math.exp(ln_gamma)
                result['activity_at_Tp'] = x_solute * math.exp(ln_gamma)

            return result

        except ValueError as e:
            result['status'] = 'numerical_error'
            result['precipitation_temperature'] = None
            result['precipitation_temperature_celsius'] = None
            result['message'] = f'数值求解失败: {str(e)}'
            result['hint'] = '驱动力函数可能不单调，尝试缩小温度搜索范围'
            return result

    def calculate_precipitation_temperature(
        self,
        alloy_composition: Dict[str, float],
        solute_element: str,
        solution_phase: str,  # 'LIQUID' 或 'SOLID'
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner',
        T_min: float = 300.0,
        T_max: float = 3000.0,
        tolerance: float = 1.0
    ) -> dict:
        """
        计算指定成分合金中溶质的析出温度

        热力学依据：
        -----------
        在析出温度T_p处，溶质的化学势等于析出相的Gibbs能：

            μ_solute(T_p) = G°_precipitate(T_p)

        定义残差函数：
            f(T) = μ_solute(T) - G°_precipitate(T)

        当 f(T) = 0 时，T 即为析出温度

        参数：
        -----
        alloy_composition : Dict[str, float]
            合金成分（摩尔分数），如 {'FE': 0.95, 'C': 0.02, 'SI': 0.03}
        solute_element : str
            溶质元素符号，如 'C'
        solution_phase : str
            溶液相类型：'LIQUID' 或 'SOLID'
        extrapolation_func : callable
            外推模型函数
        extrapolation_model_name : str
            外推模型名称
        activity_model : str
            活度模型：'Wagner', 'Darken', 'Elliott'
        T_min, T_max : float
            温度搜索范围 (K)
        tolerance : float
            温度求解精度 (K)

        返回：
        -----
        dict : 包含以下键的结果字典
            - status: 'success', 'always_supersaturated', 'always_undersaturated', 'error'
            - precipitation_temperature: 析出温度 (K)，仅当 status='success' 时有效
            - precipitation_temperature_celsius: 析出温度 (°C)
            - solute: 溶质元素
            - solute_content: 溶质摩尔分数
            - precipitating_phase: 析出相名称
            - solution_phase: 溶液相名称
            - driving_force_at_T_min: T_min处的过饱和驱动力 (J/mol)
            - driving_force_at_T_max: T_max处的过饱和驱动力 (J/mol)
        """
        # ==================== 1. 预处理 ====================
        solute = solute_element.upper()

        # 归一化成分
        total = sum(alloy_composition.values())
        if total <= 0:
            return {
                'status': 'error',
                'message': '合金成分不能为空',
                'precipitation_temperature': None
            }

        composition = {k.upper(): v / total for k, v in alloy_composition.items()}

        # 检查溶质是否在成分中
        if solute not in composition:
            return {
                'status': 'error',
                'message': f'溶质 {solute} 不在合金成分中',
                'precipitation_temperature': None
            }

        x_solute = composition[solute]
        if x_solute <= 0:
            return {
                'status': 'error',
                'message': f'溶质 {solute} 含量必须大于0',
                'precipitation_temperature': None
            }

        # 确定溶剂
        solvent = max(composition.items(), key=lambda item: item[1])[0]

        # ==================== 2. 确定相名称 ====================
        # 析出相：使用T_min温度下溶质的稳定相
        precipitating_phase = self.tdb_parser.get_stable_phase(solute, T_min)
        if not precipitating_phase:
            precipitating_phase = self.tdb_parser.get_reference_phase(solute)

        # 溶液相
        if solution_phase.upper() == 'LIQUID':
            tdb_solution_phase = 'LIQUID'
        else:
            ref_phase = self.tdb_parser.get_stable_phase(solvent, (T_min + T_max) / 2)
            tdb_solution_phase = ref_phase if ref_phase else 'BCC_A2'

        # ==================== 3. 定义残差函数 ====================
        def driving_force(T: float) -> Optional[float]:
            """
            计算析出驱动力：ΔG = μ_solute - G°_precipitate

            - ΔG > 0: 溶质在溶液中化学势高于析出相，过饱和（析出倾向）
            - ΔG < 0: 溶质在溶液中化学势低于析出相，欠饱和（稳定）
            - ΔG = 0: 平衡状态（析出温度）
            """
            # 计算溶质在溶液中的化学势
            mu_solute = self._get_chemical_potential_extended(
                composition=composition,
                component=solute,
                temperature=T,
                tdb_phase=tdb_solution_phase,
                extrapolation_func=extrapolation_func,
                extrapolation_model=extrapolation_model_name,
                activity_model=activity_model
            )

            if mu_solute is None:
                return None

            # 获取当前温度下析出相的Gibbs能
            current_precip_phase = self.tdb_parser.get_stable_phase(solute, T)
            if not current_precip_phase:
                current_precip_phase = precipitating_phase

            g_precipitate = self.tdb_parser.get_gibbs_energy(solute, current_precip_phase, T)

            if g_precipitate is None:
                return None

            return mu_solute - g_precipitate

        # ==================== 4. 评估边界条件 ====================
        df_min = driving_force(T_min)
        df_max = driving_force(T_max)

        if df_min is None or df_max is None:
            return {
                'status': 'error',
                'message': '无法计算驱动力，请检查热力学数据',
                'precipitation_temperature': None,
                'solute': solute,
                'solute_content': x_solute
            }

        # ==================== 5. 分析并求解 ====================
        result = {
            'solute': solute,
            'solute_content': x_solute,
            'solution_phase': tdb_solution_phase,
            'precipitating_phase': precipitating_phase,
            'driving_force_at_T_min': df_min,
            'driving_force_at_T_max': df_max,
            'solvent': solvent,
            'composition': composition
        }

        # 情况1: 两边同号 - 无法找到析出温度
        # ΔG > 0: 过饱和（析出倾向）; ΔG < 0: 欠饱和（稳定）
        if df_min > 0 and df_max > 0:
            # 在整个温度范围内都过饱和（析出相稳定）
            result['status'] = 'always_supersaturated'
            result['precipitation_temperature'] = None
            result['precipitation_temperature_celsius'] = None
            result['message'] = f'在 {T_min}-{T_max}K 范围内，溶质始终过饱和'
            result['hint'] = '析出温度可能高于搜索范围上限，请尝试增大T_max'
            return result

        if df_min < 0 and df_max < 0:
            # 在整个温度范围内都欠饱和（溶液稳定）
            result['status'] = 'always_undersaturated'
            result['precipitation_temperature'] = None
            result['precipitation_temperature_celsius'] = None
            result['message'] = f'在 {T_min}-{T_max}K 范围内，溶质始终欠饱和，不会析出'
            return result

        # 情况2: 两边异号 - 存在析出温度
        try:
            # 定义求解函数（处理None返回值）
            def solve_func(T):
                df = driving_force(T)
                return df if df is not None else 1e10

            T_precip = brentq(solve_func, T_min, T_max, xtol=tolerance)

            # 验证结果
            df_check = driving_force(T_precip)

            result['status'] = 'success'
            result['precipitation_temperature'] = float(T_precip)
            result['precipitation_temperature_celsius'] = float(T_precip - 273.15)
            result['message'] = '析出温度计算成功'
            result['residual'] = df_check

            # 计算析出温度处的活度系数
            ln_gamma = self.calculate_ln_activity_coefficient(
                composition, solute, T_precip,
                'liquid' if tdb_solution_phase == 'LIQUID' else 'solid',
                extrapolation_func, extrapolation_model_name, activity_model
            )
            if ln_gamma is not None:
                result['activity_coefficient_at_Tp'] = math.exp(ln_gamma)
                result['activity_at_Tp'] = x_solute * math.exp(ln_gamma)

            return result

        except ValueError as e:
            result['status'] = 'numerical_error'
            result['precipitation_temperature'] = None
            result['precipitation_temperature_celsius'] = None
            result['message'] = f'数值求解失败: {str(e)}'
            return result

    def _get_chemical_potential_extended(
        self,
        composition: Dict[str, float],
        component: str,
        temperature: float,
        tdb_phase: str,
        extrapolation_func,
        extrapolation_model: str,
        activity_model: str
    ) -> Optional[float]:
        """
        计算组分的化学势（扩展版，支持晶格稳定性估算）

        μᵢ = Gᵢ°(phase) + RT·ln(γᵢ·xᵢ)
        """
        # 确定相态
        if tdb_phase == 'LIQUID':
            activity_phase = 'liquid'
            lookup_phase = 'LIQUID'
        else:
            activity_phase = 'solid'
            lookup_phase = tdb_phase

        # 获取标准Gibbs能
        mu_0 = self.tdb_parser.get_gibbs_energy(component, lookup_phase, temperature)

        # 如果TDB没有数据，尝试晶格稳定性估算
        if mu_0 is None and lookup_phase != 'LIQUID':
            mu_0 = self._estimate_lattice_stability(component, lookup_phase, temperature)

        if mu_0 is None:
            return None

        # 计算活度系数
        ln_gamma = self.calculate_ln_activity_coefficient(
            composition, component, temperature, activity_phase,
            extrapolation_func, extrapolation_model, activity_model
        )

        if ln_gamma is None:
            return None

        # 计算化学势
        x_i = max(composition.get(component, 0.0), 1e-15)
        mu = mu_0 + self.R * temperature * (math.log(x_i) + ln_gamma)

        return mu

    def _estimate_lattice_stability(self, component: str, target_phase: str, T: float) -> Optional[float]:
        """
        估算晶格稳定性参数（针对非金属元素溶解于金属相）
        """
        comp_upper = component.upper()

        stability_config = {
            'C': {'stable_phase': 'GRAPHITE', 'fixed_diff': 77000.0},  # C: 77 kJ/mol
            'N': {'stable_phase': 'GAS', 'fixed_diff': 240000.0},      # N: 240 kJ/mol
            'SI': {'stable_phase': 'DIAMOND_A4', 'fixed_diff': 33000.0},  # Si: 33 kJ/mol
            'GE': {'stable_phase': 'DIAMOND_A4', 'fixed_diff': 25000.0},  # Ge: 25 kJ/mol
            'H': {'stable_phase': 'GAS', 'fixed_diff': 100000.0},      # H: 100 kJ/mol
            'O': {'stable_phase': 'GAS', 'fixed_diff': 250000.0},      # O: 250 kJ/mol
            'S': {'stable_phase': 'ORTHORHOMBIC_S', 'fixed_diff': 50000.0},  # S: 50 kJ/mol
            'B': {'stable_phase': 'RHOMBO_B', 'fixed_diff': 45000.0},  # B: 45 kJ/mol
        }

        if comp_upper not in stability_config:
            return None

        config = stability_config[comp_upper]

        # 获取稳定态能量
        ref_phase = config['stable_phase']
        g_stable = self.tdb_parser.get_gibbs_energy(comp_upper, ref_phase, T)

        if g_stable is None:
            # 尝试使用参考相
            ref = self.tdb_parser.get_reference_phase(comp_upper)
            if ref:
                g_stable = self.tdb_parser.get_gibbs_energy(comp_upper, ref, T)

        if g_stable is None:
            return None

        return g_stable + config['fixed_diff']

    def calculate_precipitation_curve(
        self,
        base_alloy_composition: Dict[str, float],
        solute_element: str,
        x_min: float,
        x_max: float,
        n_points: int,
        solution_phase: str,
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner',
        progress_callback=None
    ) -> dict:
        """
        计算析出温度随溶质含量变化的曲线

        参数：
        -----
        base_alloy_composition : Dict[str, float]
            基础合金成分（不含溶质或溶质含量为0）
        solute_element : str
            溶质元素
        x_min, x_max : float
            溶质摩尔分数范围
        n_points : int
            计算点数
        其他参数同 calculate_precipitation_temperature

        返回：
        -----
        dict : 包含曲线数据
        """
        solute = solute_element.upper()

        # 归一化基础成分
        total_base = sum(base_alloy_composition.values())
        base_comp = {k.upper(): v / total_base for k, v in base_alloy_composition.items()}

        # 生成溶质含量数组
        x_values = np.linspace(x_min, x_max, n_points)

        results = {
            'x_solute': [],
            'T_precipitation': [],
            'T_precipitation_celsius': [],
            'status': [],
            'details': []
        }

        for i, x_sol in enumerate(x_values):
            if progress_callback:
                progress_callback(i + 1, n_points)

            # 构建当前成分
            remaining = 1.0 - x_sol
            current_comp = {el: base_comp[el] * remaining for el in base_comp}
            current_comp[solute] = x_sol

            # 计算析出温度
            result = self.calculate_precipitation_temperature(
                alloy_composition=current_comp,
                solute_element=solute,
                solution_phase=solution_phase,
                extrapolation_func=extrapolation_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model
            )

            results['x_solute'].append(x_sol)
            results['status'].append(result['status'])
            results['details'].append(result)

            if result['status'] == 'success':
                results['T_precipitation'].append(result['precipitation_temperature'])
                results['T_precipitation_celsius'].append(result['precipitation_temperature_celsius'])
            else:
                results['T_precipitation'].append(None)
                results['T_precipitation_celsius'].append(None)

        return results

    def calculate_precipitation_curve_auto(
        self,
        base_alloy_composition: Dict[str, float],
        solute_element: str,
        x_min: float,
        x_max: float,
        n_points: int,
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner',
        progress_callback=None
    ) -> dict:
        """
        计算析出温度曲线（自动相态检测版本）

        基于热力学自动判断每个温度点的基体相态，无需人为指定

        参数：
        -----
        base_alloy_composition : Dict[str, float]
            基础合金成分（不含溶质或溶质含量为0）
        solute_element : str
            溶质元素
        x_min, x_max : float
            溶质摩尔分数范围
        n_points : int
            计算点数

        返回：
        -----
        dict : 包含曲线数据和相态信息
        """
        solute = solute_element.upper()

        # 归一化基础成分
        total_base = sum(base_alloy_composition.values())
        base_comp = {k.upper(): v / total_base for k, v in base_alloy_composition.items()}

        # 生成溶质含量数组
        x_values = np.linspace(x_min, x_max, n_points)

        results = {
            'x_solute': [],
            'T_precipitation': [],
            'T_precipitation_celsius': [],
            'matrix_phase': [],
            'status': [],
            'details': []
        }

        for i, x_sol in enumerate(x_values):
            if progress_callback:
                progress_callback(i + 1, n_points)

            # 构建当前成分
            remaining = 1.0 - x_sol
            current_comp = {el: base_comp[el] * remaining for el in base_comp}
            current_comp[solute] = x_sol

            # 使用自动相态检测计算析出温度
            result = self.calculate_precipitation_temperature_auto(
                alloy_composition=current_comp,
                solute_element=solute,
                extrapolation_func=extrapolation_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model
            )

            results['x_solute'].append(x_sol)
            results['status'].append(result['status'])
            results['details'].append(result)

            if result['status'] == 'success':
                results['T_precipitation'].append(result['precipitation_temperature'])
                results['T_precipitation_celsius'].append(result['precipitation_temperature_celsius'])
                results['matrix_phase'].append(result.get('matrix_phase', 'Unknown'))
            else:
                results['T_precipitation'].append(None)
                results['T_precipitation_celsius'].append(None)
                results['matrix_phase'].append(None)

        return results

    def calculate_liquidus_temperature(
        self,
        alloy_composition: Dict[str, float],
        solute_element: str,
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner',
        T_min: float = 300.0,
        T_max: float = 3000.0,
        tolerance: float = 1.0
    ) -> dict:
        """
        计算液相线温度（从液相中析出固相的温度）

        热力学原理：
        -----------
        液相线是液体开始凝固的温度。对于二元系统：
        - 纯溶剂的熔点为 T_m
        - 加入溶质后，液相线温度通常降低（冰点降低/共晶效应）

        平衡条件：μ_solvent(liquid) = μ_solvent(solid)

        参数：
        -----
        alloy_composition : Dict[str, float]
            合金成分（摩尔分数）
        solute_element : str
            溶质元素符号
        extrapolation_func : callable
            外推模型函数

        返回：
        -----
        dict : 包含液相线温度的结果字典
        """
        solute = solute_element.upper()
        warnings = []

        # 归一化成分
        total = sum(alloy_composition.values())
        if total <= 0:
            return {
                'status': 'error',
                'message': '合金成分不能为空',
                'liquidus_temperature': None
            }

        composition = {k.upper(): v / total for k, v in alloy_composition.items()}

        # 确定溶剂（含量最高的组元）
        solvent = max(composition.items(), key=lambda item: item[1])[0]
        x_solvent = composition[solvent]
        x_solute = composition.get(solute, 0)

        if x_solute <= 0:
            return {
                'status': 'error',
                'message': f'溶质 {solute} 含量必须大于0',
                'liquidus_temperature': None
            }

        # 获取溶剂的固相（用于液相线计算）
        solid_phase = self.tdb_parser.get_stable_phase(solvent, T_min)
        if not solid_phase or solid_phase == 'LIQUID':
            solid_phase = self.tdb_parser.get_reference_phase(solvent)
        if not solid_phase:
            solid_phase = 'BCC_A2'  # 默认

        def liquidus_driving_force(T: float) -> Optional[float]:
            """
            计算液相线驱动力：ΔG = μ_solvent(liquid) - μ_solvent(solid)

            当 ΔG = 0 时，液相和固相平衡（液相线温度）
            - ΔG > 0: 液相不稳定，应凝固
            - ΔG < 0: 液相稳定
            """
            # 溶剂在液相中的化学势
            mu_liquid = self._get_chemical_potential_extended(
                composition=composition,
                component=solvent,
                temperature=T,
                tdb_phase='LIQUID',
                extrapolation_func=extrapolation_func,
                extrapolation_model=extrapolation_model_name,
                activity_model=activity_model
            )

            if mu_liquid is None:
                return None

            # 溶剂在固相中的化学势（假设固相为纯溶剂或接近纯溶剂）
            # 对于液相线，固相中溶质含量很低，近似为纯溶剂
            g_solid = self.tdb_parser.get_gibbs_energy(solvent, solid_phase, T)
            if g_solid is None:
                g_solid = self._estimate_lattice_stability(solvent, solid_phase, T)

            if g_solid is None:
                return None

            return mu_liquid - g_solid

        # 评估边界条件
        df_min = liquidus_driving_force(T_min)
        df_max = liquidus_driving_force(T_max)

        if df_min is None or df_max is None:
            return {
                'status': 'calculation_error',
                'message': '无法计算液相线驱动力，请检查热力学数据',
                'liquidus_temperature': None
            }

        result = {
            'solute': solute,
            'solvent': solvent,
            'solute_content': x_solute,
            'solvent_content': x_solvent,
            'solid_phase': solid_phase,
            'driving_force_at_T_min': df_min,
            'driving_force_at_T_max': df_max,
            'method': 'liquidus_equilibrium'
        }

        # 检查是否存在液相线温度
        if df_min > 0 and df_max > 0:
            result['status'] = 'always_solid'
            result['liquidus_temperature'] = None
            result['message'] = f'在 {T_min}-{T_max}K 范围内，始终为固相'
            return result

        if df_min < 0 and df_max < 0:
            result['status'] = 'always_liquid'
            result['liquidus_temperature'] = None
            result['message'] = f'在 {T_min}-{T_max}K 范围内，始终为液相'
            return result

        # 求解液相线温度
        try:
            def solve_func(T):
                df = liquidus_driving_force(T)
                return df if df is not None else 1e10

            T_liquidus = brentq(solve_func, T_min, T_max, xtol=tolerance)

            result['status'] = 'success'
            result['liquidus_temperature'] = float(T_liquidus)
            result['liquidus_temperature_celsius'] = float(T_liquidus - 273.15)
            result['message'] = '液相线温度计算成功'

            # 计算纯溶剂熔点以对比
            T_melt_pure = self._get_melting_point(solvent)
            if T_melt_pure:
                result['pure_solvent_melting_point'] = T_melt_pure
                result['melting_point_depression'] = T_melt_pure - T_liquidus

            return result

        except ValueError as e:
            result['status'] = 'numerical_error'
            result['liquidus_temperature'] = None
            result['message'] = f'数值求解失败: {str(e)}'
            return result

    def _get_melting_point(self, element: str) -> Optional[float]:
        """
        获取元素的熔点

        通过找到 G_liquid = G_solid 的温度
        """
        element = element.upper()

        # 常见元素熔点数据 (K)
        melting_points = {
            'FE': 1811.0,
            'NI': 1728.0,
            'CO': 1768.0,
            'CU': 1358.0,
            'AL': 933.5,
            'TI': 1941.0,
            'CR': 2180.0,
            'MN': 1519.0,
            'V': 2183.0,
            'MO': 2896.0,
            'W': 3695.0,
            'NB': 2750.0,
            'TA': 3290.0,
            'ZR': 2128.0,
            'HF': 2506.0,
            'SI': 1687.0,
            'C': 3823.0,  # 石墨升华点
            'B': 2349.0,
        }

        return melting_points.get(element)

    def calculate_liquidus_curve(
        self,
        base_alloy_composition: Dict[str, float],
        solute_element: str,
        x_min: float,
        x_max: float,
        n_points: int,
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner',
        progress_callback=None
    ) -> dict:
        """
        计算液相线曲线（液相线温度随溶质含量的变化）

        用于展示共晶效应：随着溶质含量增加，液相线温度降低

        参数：
        -----
        base_alloy_composition : 基础合金成分
        solute_element : 溶质元素
        x_min, x_max : 溶质摩尔分数范围
        n_points : 计算点数

        返回：
        -----
        dict : 液相线曲线数据
        """
        solute = solute_element.upper()

        # 归一化基础成分
        total_base = sum(base_alloy_composition.values())
        base_comp = {k.upper(): v / total_base for k, v in base_alloy_composition.items()}

        # 生成溶质含量数组
        x_values = np.linspace(x_min, x_max, n_points)

        results = {
            'x_solute': [],
            'T_liquidus': [],
            'T_liquidus_celsius': [],
            'melting_point_depression': [],
            'status': [],
            'details': []
        }

        # 获取纯溶剂熔点
        solvent = max(base_comp.items(), key=lambda item: item[1])[0]
        T_melt_pure = self._get_melting_point(solvent)

        for i, x_sol in enumerate(x_values):
            if progress_callback:
                progress_callback(i + 1, n_points)

            # 构建当前成分
            remaining = 1.0 - x_sol
            current_comp = {el: base_comp[el] * remaining for el in base_comp}
            current_comp[solute] = x_sol

            # 计算液相线温度
            result = self.calculate_liquidus_temperature(
                alloy_composition=current_comp,
                solute_element=solute,
                extrapolation_func=extrapolation_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model
            )

            results['x_solute'].append(x_sol)
            results['status'].append(result['status'])
            results['details'].append(result)

            if result['status'] == 'success':
                T_liq = result['liquidus_temperature']
                results['T_liquidus'].append(T_liq)
                results['T_liquidus_celsius'].append(T_liq - 273.15)
                if T_melt_pure:
                    results['melting_point_depression'].append(T_melt_pure - T_liq)
                else:
                    results['melting_point_depression'].append(None)
            else:
                results['T_liquidus'].append(None)
                results['T_liquidus_celsius'].append(None)
                results['melting_point_depression'].append(None)

        results['solvent'] = solvent
        results['pure_melting_point'] = T_melt_pure

        return results

    def calculate_phase_diagram_curves(
        self,
        base_alloy_composition: Dict[str, float],
        solute_element: str,
        x_min: float,
        x_max: float,
        n_points: int,
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner',
        progress_callback=None
    ) -> dict:
        """
        计算完整的相图曲线（液相线 + 固溶线）

        同时计算：
        1. 液相线（Liquidus）：液体开始凝固的温度，随溶质增加而降低
        2. 固溶线（Solvus）：固溶体开始析出第二相的温度，随溶质增加而升高

        这两条曲线的交点附近即为共晶点

        参数：
        -----
        base_alloy_composition : 基础合金成分
        solute_element : 溶质元素
        x_min, x_max : 溶质摩尔分数范围
        n_points : 计算点数

        返回：
        -----
        dict : 包含液相线和固溶线数据的字典
        """
        # 计算液相线
        liquidus_results = self.calculate_liquidus_curve(
            base_alloy_composition=base_alloy_composition,
            solute_element=solute_element,
            x_min=x_min,
            x_max=x_max,
            n_points=n_points,
            extrapolation_func=extrapolation_func,
            extrapolation_model_name=extrapolation_model_name,
            activity_model=activity_model,
            progress_callback=lambda i, n: progress_callback(i, n * 2) if progress_callback else None
        )

        # 计算固溶线（使用自动相态检测）
        solvus_results = self.calculate_precipitation_curve_auto(
            base_alloy_composition=base_alloy_composition,
            solute_element=solute_element,
            x_min=x_min,
            x_max=x_max,
            n_points=n_points,
            extrapolation_func=extrapolation_func,
            extrapolation_model_name=extrapolation_model_name,
            activity_model=activity_model,
            progress_callback=lambda i, n: progress_callback(n + i, n * 2) if progress_callback else None
        )

        return {
            'x_solute': liquidus_results['x_solute'],
            'liquidus': {
                'T_K': liquidus_results['T_liquidus'],
                'T_C': liquidus_results['T_liquidus_celsius'],
                'status': liquidus_results['status'],
                'melting_point_depression': liquidus_results['melting_point_depression']
            },
            'solvus': {
                'T_K': solvus_results['T_precipitation'],
                'T_C': solvus_results['T_precipitation_celsius'],
                'status': solvus_results['status'],
                'matrix_phase': solvus_results['matrix_phase']
            },
            'solvent': liquidus_results.get('solvent'),
            'pure_melting_point': liquidus_results.get('pure_melting_point'),
            'solute': solute_element.upper()
        }

    def calculate_multi_solute_precipitation(
        self,
        alloy_composition: Dict[str, float],
        solute_elements: List[str],
        solution_phase: str,
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner'
    ) -> dict:
        """
        计算多溶质系统中各溶质的析出温度

        返回各溶质的析出温度，按析出温度从高到低排序（先析出的排前面）
        """
        results = {
            'solutes': [],
            'precipitation_temperatures': [],
            'precipitation_sequence': [],
            'details': {}
        }

        for solute in solute_elements:
            solute_upper = solute.upper()

            result = self.calculate_precipitation_temperature(
                alloy_composition=alloy_composition,
                solute_element=solute_upper,
                solution_phase=solution_phase,
                extrapolation_func=extrapolation_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model
            )

            results['details'][solute_upper] = result

            if result['status'] == 'success':
                results['solutes'].append(solute_upper)
                results['precipitation_temperatures'].append(result['precipitation_temperature'])

        # 按析出温度排序（降序，高温先析出）
        if results['solutes']:
            sorted_pairs = sorted(
                zip(results['solutes'], results['precipitation_temperatures']),
                key=lambda x: x[1],
                reverse=True
            )
            results['precipitation_sequence'] = [p[0] for p in sorted_pairs]
            results['sorted_temperatures'] = [p[1] for p in sorted_pairs]

        return results

    # ========================================================================
    # Turkdogan溶解度积法计算析出温度 (基于经验公式)
    # ========================================================================

    def calculate_precipitation_temperature_turkdogan(
        self,
        alloy_composition: Dict[str, float],
        compound: str,
        phase: str = 'AUSTENITE',
        use_weight_percent: bool = False
    ) -> dict:
        """
        使用Turkdogan溶解度积公式计算析出温度

        基于经验公式: log[%M][%X]^n = A - B/T
        析出温度: T = B / (A - log[%M][%X]^n)

        参数：
        -----
        alloy_composition : Dict[str, float]
            合金成分 (摩尔分数或质量百分数，取决于use_weight_percent)
        compound : str
            析出物名称: 'TiN', 'TiC', 'NbC', 'NbN', 'VC', 'VN', 'AlN', 'MnS'
        phase : str
            母相: 'AUSTENITE', 'FERRITE', 'LIQUID'
        use_weight_percent : bool
            True: 输入为质量百分数; False: 输入为摩尔分数

        返回：
        -----
        dict : 包含析出温度和相关信息的字典
        """
        try:
            from database.solubility_product_database import (
                get_solubility_product_data,
                calculate_precipitation_temperature_from_product,
                mole_to_weight_percent
            )
        except ImportError:
            return {
                'status': 'error',
                'message': '无法导入溶解度积数据库',
                'precipitation_temperature': None
            }

        # 获取溶解度积数据
        sp_data = get_solubility_product_data(compound, phase)
        if sp_data is None:
            return {
                'status': 'error',
                'message': f'未找到 {compound} 在 {phase} 中的溶解度积数据',
                'precipitation_temperature': None
            }

        metal = sp_data['metal']
        nonmetal = sp_data['nonmetal']

        # 获取成分
        comp_upper = {k.upper(): v for k, v in alloy_composition.items()}

        metal_content = comp_upper.get(metal, 0)
        nonmetal_content = comp_upper.get(nonmetal, 0)

        if metal_content <= 0:
            return {
                'status': 'error',
                'message': f'合金中不含 {metal} 元素',
                'precipitation_temperature': None
            }

        if nonmetal_content <= 0:
            return {
                'status': 'error',
                'message': f'合金中不含 {nonmetal} 元素',
                'precipitation_temperature': None
            }

        # 如果是摩尔分数，转换为质量百分数
        if not use_weight_percent:
            metal_wt = mole_to_weight_percent(metal_content, metal)
            nonmetal_wt = mole_to_weight_percent(nonmetal_content, nonmetal)
        else:
            metal_wt = metal_content
            nonmetal_wt = nonmetal_content

        # 计算析出温度
        T_precip = calculate_precipitation_temperature_from_product(
            compound, phase, metal_wt, nonmetal_wt
        )

        if T_precip is None:
            return {
                'status': 'always_undersaturated',
                'message': f'{compound} 溶解度积过大，在常规温度范围内不会析出',
                'precipitation_temperature': None,
                'compound': compound,
                'phase': phase,
                'metal_wt_pct': metal_wt,
                'nonmetal_wt_pct': nonmetal_wt
            }

        # 检查温度是否在有效范围内
        T_min = sp_data.get('T_min', 773)
        T_max = sp_data.get('T_max', 1873)

        warning = None
        if T_precip < T_min:
            warning = f'析出温度 {T_precip:.1f}K 低于公式有效范围 ({T_min}K)'
        elif T_precip > T_max:
            warning = f'析出温度 {T_precip:.1f}K 高于公式有效范围 ({T_max}K)'

        # 计算log Ks
        A = sp_data['A']
        B = sp_data['B']
        n = sp_data.get('n', 1.0)
        log_product = math.log10(metal_wt) + n * math.log10(nonmetal_wt)
        log_Ks = A - B / T_precip

        return {
            'status': 'success',
            'method': 'Turkdogan_solubility_product',
            'compound': compound,
            'phase': phase,
            'precipitation_temperature': T_precip,
            'precipitation_temperature_celsius': T_precip - 273.15,
            'metal_element': metal,
            'nonmetal_element': nonmetal,
            'metal_wt_pct': metal_wt,
            'nonmetal_wt_pct': nonmetal_wt,
            'log_product': log_product,
            'log_Ks_at_Tp': log_Ks,
            'equation_A': A,
            'equation_B': B,
            'stoichiometry_n': n,
            'reference': sp_data.get('reference', ''),
            'notes': sp_data.get('notes', ''),
            'warning': warning
        }

    def calculate_all_precipitates_turkdogan(
        self,
        alloy_composition: Dict[str, float],
        phase: str = 'AUSTENITE',
        use_weight_percent: bool = False
    ) -> dict:
        """
        计算合金中所有可能析出物的析出温度，并按温度排序

        参数：
        -----
        alloy_composition : 合金成分
        phase : 母相
        use_weight_percent : 是否使用质量百分数

        返回：
        -----
        dict : 包含所有析出物及其析出温度的字典
        """
        try:
            from database.solubility_product_database import SOLUBILITY_PRODUCTS
        except ImportError:
            return {
                'status': 'error',
                'message': '无法导入溶解度积数据库'
            }

        phase_upper = phase.upper()
        phase_map = {
            'FCC_A1': 'AUSTENITE', 'FCC': 'AUSTENITE', 'GAMMA': 'AUSTENITE',
            'BCC_A2': 'FERRITE', 'BCC': 'FERRITE', 'ALPHA': 'FERRITE',
        }
        phase_key = phase_map.get(phase_upper, phase_upper)

        if phase_key not in SOLUBILITY_PRODUCTS:
            return {
                'status': 'error',
                'message': f'不支持的相: {phase}'
            }

        results = []
        details = {}

        for compound in SOLUBILITY_PRODUCTS[phase_key].keys():
            result = self.calculate_precipitation_temperature_turkdogan(
                alloy_composition=alloy_composition,
                compound=compound,
                phase=phase,
                use_weight_percent=use_weight_percent
            )

            details[compound] = result

            if result['status'] == 'success':
                results.append({
                    'compound': compound,
                    'T_K': result['precipitation_temperature'],
                    'T_C': result['precipitation_temperature_celsius'],
                    'metal': result['metal_element'],
                    'nonmetal': result['nonmetal_element']
                })

        # 按析出温度排序（高温先析出）
        results.sort(key=lambda x: x['T_K'], reverse=True)

        return {
            'status': 'success',
            'phase': phase_key,
            'precipitation_sequence': results,
            'details': details,
            'summary': [(r['compound'], r['T_K'], r['T_C']) for r in results]
        }

    def calculate_carbonitride_precipitation(
        self,
        alloy_composition: Dict[str, float],
        phase: str = 'AUSTENITE',
        use_weight_percent: bool = False
    ) -> dict:
        """
        专门计算碳氮化物（Ti, Nb, V的碳化物和氮化物）的析出温度

        用于微合金钢的析出行为分析

        参数：
        -----
        alloy_composition : 合金成分（需包含Ti/Nb/V和C/N）
        phase : 母相
        use_weight_percent : 是否使用质量百分数

        返回：
        -----
        dict : 包含碳氮化物析出信息的字典
        """
        carbonitrides = ['TiN', 'TiC', 'NbN', 'NbC', 'VN', 'VC']

        results = []
        details = {}

        for compound in carbonitrides:
            result = self.calculate_precipitation_temperature_turkdogan(
                alloy_composition=alloy_composition,
                compound=compound,
                phase=phase,
                use_weight_percent=use_weight_percent
            )

            details[compound] = result

            if result['status'] == 'success':
                results.append({
                    'compound': compound,
                    'T_K': result['precipitation_temperature'],
                    'T_C': result['precipitation_temperature_celsius'],
                    'metal': result['metal_element'],
                    'nonmetal': result['nonmetal_element'],
                    'metal_wt_pct': result['metal_wt_pct'],
                    'nonmetal_wt_pct': result['nonmetal_wt_pct']
                })

        # 按析出温度排序
        results.sort(key=lambda x: x['T_K'], reverse=True)

        # 分析析出顺序
        analysis = []
        if results:
            analysis.append(f"首先析出: {results[0]['compound']} at {results[0]['T_C']:.0f}°C")
            if len(results) > 1:
                analysis.append(f"最后析出: {results[-1]['compound']} at {results[-1]['T_C']:.0f}°C")

        return {
            'status': 'success',
            'phase': phase,
            'carbonitride_sequence': results,
            'details': details,
            'analysis': analysis,
            'total_precipitates': len(results)
        }

    # ========================================================================
    # 手动指定析出相的析出温度计算
    # ========================================================================

    # 常用化合物化学计量比数据库（与ManualPhaseEquilibriumCalculator共享）
    COMPOUND_DATABASE = {
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

    def _parse_compound_formula(self, formula: str) -> Dict[str, float]:
        """
        解析化合物化学式，返回摩尔分数组成。

        支持格式:
        - 数据库中的化合物: "Fe3C", "TiC", "Ni3Al"
        - 自定义格式: "Fe3C1" (元素后跟数字)

        返回: {元素: 摩尔分数}
        """
        import re

        formula = formula.strip()

        # 首先检查数据库
        if formula in self.COMPOUND_DATABASE:
            stoich = self.COMPOUND_DATABASE[formula]
            total = sum(stoich.values())
            return {el.upper(): n / total for el, n in stoich.items()}

        # 解析自定义格式
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

    def _estimate_compound_formation_energy(
        self,
        compound_comp: Dict[str, float],
        compound_name: str,
        temperature: float
    ) -> Optional[float]:
        """
        估算化合物的生成能（J/mol）

        使用Miedema模型估算，或使用经验值
        """
        # 常见化合物的生成焓估算值（J/mol）
        formation_enthalpies = {
            'Fe3C': -25000,      # 渗碳体
            'TiC': -185000,     # 碳化钛（非常稳定）
            'TiN': -337000,     # 氮化钛（极其稳定）
            'VC': -102000,      # 碳化钒
            'VN': -217000,      # 氮化钒
            'NbC': -140000,     # 碳化铌
            'NbN': -234000,     # 氮化铌
            'Cr23C6': -70000,   # 铬碳化物
            'Cr7C3': -50000,
            'Mo2C': -45000,
            'WC': -40000,
            'AlN': -318000,     # 氮化铝
            'SiC': -73000,
            'Si3N4': -750000,
            'Ni3Al': -45000,
            'NiAl': -60000,
            'Fe3Al': -25000,
            'FeAl': -30000,
            'TiAl': -40000,
            'Ti3Al': -25000,
            'MnS': -110000,
            'FeS': -60000,
        }

        if compound_name in formation_enthalpies:
            H_f = formation_enthalpies[compound_name]
            # 简化处理：G ≈ H - T*S，假设 S_f ≈ 0 for 稳定化合物
            return H_f

        # 对于未知化合物，尝试用Miedema模型
        elements = list(compound_comp.keys())
        if len(elements) == 2:
            try:
                from models.miedema_model import MiedemaModel
                mm = MiedemaModel(tuple(elements), "SOLID")
                x_A = compound_comp[elements[0]]
                H_mix = mm.calc_enthalpy_formation(x_A)
                return H_mix * 1000  # kJ/mol -> J/mol
            except Exception:
                pass

        # 默认返回一个保守估计
        return -50000  # 默认 -50 kJ/mol

    def calculate_manual_precipitate_temperature(
        self,
        alloy_composition: Dict[str, float],
        precipitate_phase: str,
        solution_phase: str = 'SOLID',
        compound_gibbs_energy: Optional[float] = None,
        extrapolation_func=None,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner',
        T_min: float = 300.0,
        T_max: float = 3000.0,
        tolerance: float = 1.0
    ) -> dict:
        """
        计算手动指定析出相与基体相之间的平衡温度（析出温度）

        热力学原理：
        -----------
        找到温度T，使得析出相与基体相处于平衡状态。
        对于化合物析出相，平衡条件为：
            Σ(xᵢ · μᵢ_matrix) = G_compound

        其中：
        - xᵢ: 化合物中各元素的摩尔分数
        - μᵢ_matrix: 元素i在基体相中的化学势
        - G_compound: 化合物的吉布斯能

        参数：
        -----
        alloy_composition : Dict[str, float]
            合金成分（摩尔分数）
        precipitate_phase : str
            析出相名称（化合物化学式，如 "Fe3C", "TiC"）
        solution_phase : str
            基体相类型：'LIQUID' 或 'SOLID'
        compound_gibbs_energy : Optional[float]
            化合物的吉布斯能 (J/mol)，如果为None则自动估算
        extrapolation_func : callable
            外推模型函数
        extrapolation_model_name : str
            外推模型名称
        activity_model : str
            活度模型
        T_min, T_max : float
            温度搜索范围 (K)
        tolerance : float
            温度求解精度 (K)

        返回：
        -----
        dict : 包含析出温度和相关信息的结果字典
        """
        # 解析化合物组成
        try:
            compound_comp = self._parse_compound_formula(precipitate_phase)
        except ValueError as e:
            return {
                'status': 'error',
                'message': str(e),
                'precipitation_temperature': None
            }

        # 归一化合金组成
        total = sum(alloy_composition.values())
        if total <= 0:
            return {
                'status': 'error',
                'message': '合金成分不能为空',
                'precipitation_temperature': None
            }
        composition = {k.upper(): v / total for k, v in alloy_composition.items()}

        # 检查合金中是否含有化合物所需的元素
        missing_elements = [el for el in compound_comp if el not in composition or composition[el] < 1e-10]
        if missing_elements:
            return {
                'status': 'error',
                'message': f"合金中缺少析出相所需元素: {', '.join(missing_elements)}",
                'precipitation_temperature': None,
                'compound_composition': compound_comp
            }

        # 确定溶剂
        solvent = max(composition.items(), key=lambda item: item[1])[0]

        # 确定基体相
        if solution_phase.upper() == 'LIQUID':
            tdb_solution_phase = 'LIQUID'
        else:
            ref_phase = self.tdb_parser.get_stable_phase(solvent, (T_min + T_max) / 2)
            tdb_solution_phase = ref_phase if ref_phase else 'BCC_A2'

        # 获取或估算化合物的生成能
        if compound_gibbs_energy is not None:
            g_compound_base = compound_gibbs_energy
        else:
            g_compound_base = self._estimate_compound_formation_energy(
                compound_comp, precipitate_phase, (T_min + T_max) / 2
            )

        def precipitation_driving_force(T: float) -> Optional[float]:
            """
            计算析出驱动力：ΔG = Σ(xᵢ · μᵢ_matrix) - G_compound

            - ΔG > 0: 元素在基体中化学势高于化合物，过饱和（析出倾向）
            - ΔG < 0: 元素在基体中化学势低于化合物，欠饱和（不析出）
            - ΔG = 0: 两相平衡（析出温度）
            """
            # 计算各元素在基体中的化学势加权和
            weighted_mu_sum = 0.0
            for element, x_in_compound in compound_comp.items():
                mu_element = self._get_chemical_potential_extended(
                    composition=composition,
                    component=element,
                    temperature=T,
                    tdb_phase=tdb_solution_phase,
                    extrapolation_func=extrapolation_func,
                    extrapolation_model=extrapolation_model_name,
                    activity_model=activity_model
                )
                if mu_element is None:
                    return None
                weighted_mu_sum += x_in_compound * mu_element

            # 化合物的吉布斯能（考虑温度效应）
            # G_compound(T) ≈ H_f + 纯元素参考态能量的加权和
            g_compound = g_compound_base
            for element, x_in_compound in compound_comp.items():
                g_ref = self.tdb_parser.get_gibbs_energy(element, tdb_solution_phase, T)
                if g_ref is None:
                    g_ref = self._estimate_lattice_stability(element, tdb_solution_phase, T)
                if g_ref is not None:
                    g_compound += x_in_compound * g_ref

            return weighted_mu_sum - g_compound

        # 评估边界条件
        df_min = precipitation_driving_force(T_min)
        df_max = precipitation_driving_force(T_max)

        if df_min is None or df_max is None:
            return {
                'status': 'calculation_error',
                'message': '无法计算析出驱动力，请检查热力学数据',
                'precipitation_temperature': None,
                'precipitate_phase': precipitate_phase,
                'compound_composition': compound_comp
            }

        result = {
            'precipitate_phase': precipitate_phase,
            'compound_composition': compound_comp,
            'solution_phase': tdb_solution_phase,
            'solvent': solvent,
            'composition': composition,
            'driving_force_at_T_min': df_min,
            'driving_force_at_T_max': df_max,
            'compound_gibbs_energy_base': g_compound_base,
            'method': 'manual_precipitate_equilibrium'
        }

        # 分析驱动力符号
        # ΔG > 0: 过饱和（析出倾向）; ΔG < 0: 欠饱和（稳定）
        if df_min > 0 and df_max > 0:
            result['status'] = 'always_supersaturated'
            result['precipitation_temperature'] = None
            result['precipitation_temperature_celsius'] = None
            result['message'] = f'在 {T_min}-{T_max}K 范围内，{precipitate_phase} 始终过饱和'
            result['hint'] = '析出温度可能高于搜索范围上限，请尝试增大T_max'
            return result

        if df_min < 0 and df_max < 0:
            result['status'] = 'always_undersaturated'
            result['precipitation_temperature'] = None
            result['precipitation_temperature_celsius'] = None
            result['message'] = f'在 {T_min}-{T_max}K 范围内，{precipitate_phase} 始终欠饱和，不会析出'
            return result

        # 存在析出温度，使用二分法求解
        try:
            def solve_func(T):
                df = precipitation_driving_force(T)
                return df if df is not None else 1e10

            T_precip = brentq(solve_func, T_min, T_max, xtol=tolerance)

            # 验证结果
            df_check = precipitation_driving_force(T_precip)

            result['status'] = 'success'
            result['precipitation_temperature'] = float(T_precip)
            result['precipitation_temperature_celsius'] = float(T_precip - 273.15)
            result['message'] = f'{precipitate_phase} 的析出温度计算成功'
            result['residual'] = df_check

            return result

        except ValueError as e:
            result['status'] = 'numerical_error'
            result['precipitation_temperature'] = None
            result['precipitation_temperature_celsius'] = None
            result['message'] = f'数值求解失败: {str(e)}'
            return result

    def calculate_multi_precipitate_temperature(
        self,
        alloy_composition: Dict[str, float],
        precipitate_phases: List[str],
        solution_phase: str = 'SOLID',
        compound_gibbs_energies: Optional[List[Optional[float]]] = None,
        extrapolation_func=None,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner'
    ) -> dict:
        """
        计算多个手动指定析出相的析出温度，并按温度排序

        参数：
        -----
        alloy_composition : 合金成分
        precipitate_phases : 析出相列表（化合物化学式）
        solution_phase : 基体相类型
        compound_gibbs_energies : 各化合物的吉布斯能（可选）
        extrapolation_func : 外推模型函数
        extrapolation_model_name : 外推模型名称
        activity_model : 活度模型

        返回：
        -----
        dict : 包含各析出相析出温度的字典
        """
        if compound_gibbs_energies is None:
            compound_gibbs_energies = [None] * len(precipitate_phases)

        results = {
            'precipitates': [],
            'precipitation_temperatures': [],
            'precipitation_sequence': [],
            'details': {}
        }

        for i, phase in enumerate(precipitate_phases):
            gibbs = compound_gibbs_energies[i] if i < len(compound_gibbs_energies) else None

            result = self.calculate_manual_precipitate_temperature(
                alloy_composition=alloy_composition,
                precipitate_phase=phase,
                solution_phase=solution_phase,
                compound_gibbs_energy=gibbs,
                extrapolation_func=extrapolation_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model
            )

            results['details'][phase] = result

            if result['status'] == 'success':
                results['precipitates'].append(phase)
                results['precipitation_temperatures'].append(result['precipitation_temperature'])

        # 按析出温度排序（降序，高温先析出）
        if results['precipitates']:
            sorted_pairs = sorted(
                zip(results['precipitates'], results['precipitation_temperatures']),
                key=lambda x: x[1],
                reverse=True
            )
            results['precipitation_sequence'] = [p[0] for p in sorted_pairs]
            results['sorted_temperatures'] = [p[1] for p in sorted_pairs]

        return results


# 便捷接口
def calculate_precipitation_temp(
    composition: Dict[str, float],
    solute: str,
    phase: str = 'SOLID',
    model: str = 'UEM1'
) -> Optional[float]:
    """
    便捷函数：快速计算析出温度

    用法：
        T_p = calculate_precipitation_temp({'FE': 0.98, 'C': 0.02}, 'C')
    """
    from models.extrapolation_models import BinaryModel

    bm = BinaryModel()
    model_map = {
        'UEM1': bm.UEM1, 'UEM2': bm.UEM2, 'UEM2-Adv': bm.UEM2_Adv,
        'GSM': bm.GSM, 'Muggianu': bm.Muggianu
    }

    calc = PrecipitationTemperatureCalculator()
    result = calc.calculate_precipitation_temperature(
        alloy_composition=composition,
        solute_element=solute,
        solution_phase=phase,
        extrapolation_func=model_map.get(model, bm.UEM1),
        extrapolation_model_name=model
    )

    if result['status'] == 'success':
        return result['precipitation_temperature']
    return None


# 测试代码
if __name__ == '__main__':
    from models.extrapolation_models import BinaryModel

    calc = PrecipitationTemperatureCalculator()
    bm = BinaryModel()

    # 测试：Fe-C合金中C的析出温度
    print("=" * 60)
    print("测试：Fe-2%C 合金中 C 的析出温度")
    print("=" * 60)

    result = calc.calculate_precipitation_temperature(
        alloy_composition={'FE': 0.98, 'C': 0.02},
        solute_element='C',
        solution_phase='SOLID',
        extrapolation_func=bm.UEM1,
        extrapolation_model_name='UEM1',
        activity_model='Wagner'
    )

    print(f"状态: {result['status']}")
    if result['status'] == 'success':
        print(f"析出温度: {result['precipitation_temperature']:.1f} K")
        print(f"析出温度: {result['precipitation_temperature_celsius']:.1f} °C")
        print(f"析出相: {result['precipitating_phase']}")
        print(f"溶液相: {result['solution_phase']}")
    else:
        print(f"消息: {result.get('message', 'N/A')}")

    print("\n" + "=" * 60)
    print("测试：计算析出温度-成分曲线")
    print("=" * 60)

    curve_result = calc.calculate_precipitation_curve(
        base_alloy_composition={'FE': 1.0},
        solute_element='C',
        x_min=0.001,
        x_max=0.05,
        n_points=10,
        solution_phase='SOLID',
        extrapolation_func=bm.UEM1
    )

    print(f"{'X_C':<10} {'T_precip (K)':<15} {'T_precip (°C)':<15} {'状态'}")
    print("-" * 55)
    for i in range(len(curve_result['x_solute'])):
        x = curve_result['x_solute'][i]
        T = curve_result['T_precipitation'][i]
        T_c = curve_result['T_precipitation_celsius'][i]
        status = curve_result['status'][i]

        T_str = f"{T:.1f}" if T else "N/A"
        T_c_str = f"{T_c:.1f}" if T_c else "N/A"
        print(f"{x:<10.4f} {T_str:<15} {T_c_str:<15} {status}")
