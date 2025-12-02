"""
化合物溶解度积计算模块 (Compound Solubility Product Calculator)
================================================================
基于UEM-Miedema模型框架计算化合物（如碳化物、氮化物、氧化物）的溶解度积

核心热力学原理：
-----------------
对于化合物 MₘXₙ 在溶液中的溶解平衡：

    MₘXₙ(s) ⇌ m·M(溶解) + n·X(溶解)

溶解度积定义为：
    Ksp = aₘ^m · aₓ^n = (γₘ·xₘ)^m · (γₓ·xₓ)^n

标准状态下的平衡条件：
    ΔG°_dissolution = m·μₘ° + n·μₓ° - G°_MₘXₙ = -RT·ln(Ksp)

因此：
    ln(Ksp) = -ΔG°_dissolution / (RT)
            = [G°_MₘXₙ - m·μₘ°(solution) - n·μₓ°(solution)] / (RT)

应用：
------
1. 碳化物溶解度：如 Fe₃C, TiC, NbC, VC 等
2. 氮化物溶解度：如 TiN, AlN, VN, BN 等
3. 氧化物溶解度：如 Al₂O₃, SiO₂ 等
4. 硫化物溶解度：如 MnS, CaS 等

"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from scipy.optimize import brentq, fsolve
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations.thermodynamic_properties import ThermodynamicProperties


@dataclass
class CompoundData:
    """化合物热力学数据"""
    formula: str              # 化学式，如 "TiC"
    metal_element: str        # 金属元素，如 "Ti"
    nonmetal_element: str     # 非金属元素，如 "C"
    metal_stoich: int         # 金属计量数，如 1
    nonmetal_stoich: int      # 非金属计量数，如 1

    # 标准生成Gibbs能表达式：ΔG°f = A + B*T (J/mol)
    delta_gf_A: float         # 常数项 A (J/mol)
    delta_gf_B: float         # 温度系数 B (J/mol/K)

    # 可选：溶解度积实验数据
    log_ksp_expression: str = None  # log(Ksp) = f(T) 表达式

    # 备注
    reference: str = ""
    notes: str = ""


# ============================================================================
# 常见化合物热力学数据库
# 数据来源：SGTE, Thermocalc, 文献综合
# ============================================================================

COMPOUND_DATABASE: Dict[str, CompoundData] = {
    # --------------------- 碳化物 Carbides ---------------------
    "TiC": CompoundData(
        formula="TiC",
        metal_element="TI", nonmetal_element="C",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-184000,  # J/mol
        delta_gf_B=22.0,     # J/mol/K
        log_ksp_expression="-7000/T-2.75",  # 液态Fe中
        reference="SGTE, Turkdogan",
        notes="液态Fe中的溶解度积"
    ),

    "NbC": CompoundData(
        formula="NbC",
        metal_element="NB", nonmetal_element="C",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-140000,
        delta_gf_B=20.0,
        log_ksp_expression="-6770/T-2.26",
        reference="Turkdogan",
        notes="液态Fe中"
    ),

    "VC": CompoundData(
        formula="VC",
        metal_element="V", nonmetal_element="C",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-102000,
        delta_gf_B=18.0,
        log_ksp_expression="-6560/T-3.28",
        reference="Turkdogan",
        notes="液态Fe中"
    ),

    "Fe3C": CompoundData(
        formula="Fe3C",
        metal_element="FE", nonmetal_element="C",
        metal_stoich=3, nonmetal_stoich=1,
        delta_gf_A=27000,  # 正值表示亚稳相
        delta_gf_B=-5.0,
        reference="SGTE",
        notes="渗碳体，亚稳相"
    ),

    "Cr7C3": CompoundData(
        formula="Cr7C3",
        metal_element="CR", nonmetal_element="C",
        metal_stoich=7, nonmetal_stoich=3,
        delta_gf_A=-186000,
        delta_gf_B=45.0,
        reference="SGTE",
        notes="铬碳化物"
    ),

    "Cr23C6": CompoundData(
        formula="Cr23C6",
        metal_element="CR", nonmetal_element="C",
        metal_stoich=23, nonmetal_stoich=6,
        delta_gf_A=-380000,
        delta_gf_B=110.0,
        reference="SGTE",
        notes="铬碳化物"
    ),

    "Mo2C": CompoundData(
        formula="Mo2C",
        metal_element="MO", nonmetal_element="C",
        metal_stoich=2, nonmetal_stoich=1,
        delta_gf_A=-46000,
        delta_gf_B=12.0,
        reference="SGTE",
        notes="钼碳化物"
    ),

    "WC": CompoundData(
        formula="WC",
        metal_element="W", nonmetal_element="C",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-40000,
        delta_gf_B=8.0,
        reference="SGTE",
        notes="碳化钨"
    ),

    # --------------------- 氮化物 Nitrides ---------------------
    "TiN": CompoundData(
        formula="TiN",
        metal_element="TI", nonmetal_element="N",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-337000,
        delta_gf_B=87.0,
        log_ksp_expression="-15200/T-3.82",
        reference="SGTE, Turkdogan",
        notes="液态Fe中"
    ),

    "AlN": CompoundData(
        formula="AlN",
        metal_element="AL", nonmetal_element="N",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-318000,
        delta_gf_B=115.0,
        log_ksp_expression="-6770/T-1.03",
        reference="SGTE",
        notes="液态Fe中"
    ),

    "VN": CompoundData(
        formula="VN",
        metal_element="V", nonmetal_element="N",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-217000,
        delta_gf_B=75.0,
        log_ksp_expression="-8700/T-2.86",
        reference="Turkdogan",
        notes="液态Fe中"
    ),

    "CrN": CompoundData(
        formula="CrN",
        metal_element="CR", nonmetal_element="N",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-117000,
        delta_gf_B=42.0,
        reference="SGTE",
        notes="氮化铬"
    ),

    "BN": CompoundData(
        formula="BN",
        metal_element="B", nonmetal_element="N",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-254000,
        delta_gf_B=89.0,
        log_ksp_expression="-13970/T-5.24",
        reference="SGTE",
        notes="氮化硼"
    ),

    # --------------------- 氧化物 Oxides ---------------------
    "Al2O3": CompoundData(
        formula="Al2O3",
        metal_element="AL", nonmetal_element="O",
        metal_stoich=2, nonmetal_stoich=3,
        delta_gf_A=-1675000,
        delta_gf_B=313.0,
        reference="SGTE",
        notes="氧化铝"
    ),

    "SiO2": CompoundData(
        formula="SiO2",
        metal_element="SI", nonmetal_element="O",
        metal_stoich=1, nonmetal_stoich=2,
        delta_gf_A=-910000,
        delta_gf_B=175.0,
        reference="SGTE",
        notes="二氧化硅"
    ),

    "MnO": CompoundData(
        formula="MnO",
        metal_element="MN", nonmetal_element="O",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-385000,
        delta_gf_B=73.0,
        reference="SGTE",
        notes="氧化锰"
    ),

    "FeO": CompoundData(
        formula="FeO",
        metal_element="FE", nonmetal_element="O",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-264000,
        delta_gf_B=65.0,
        reference="SGTE",
        notes="氧化亚铁"
    ),

    # --------------------- 硫化物 Sulfides ---------------------
    "MnS": CompoundData(
        formula="MnS",
        metal_element="MN", nonmetal_element="S",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-277000,
        delta_gf_B=65.0,
        log_ksp_expression="-9020/T-2.93",
        reference="Turkdogan",
        notes="液态Fe中"
    ),

    "CaS": CompoundData(
        formula="CaS",
        metal_element="CA", nonmetal_element="S",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-473000,
        delta_gf_B=97.0,
        reference="SGTE",
        notes="硫化钙"
    ),

    "FeS": CompoundData(
        formula="FeS",
        metal_element="FE", nonmetal_element="S",
        metal_stoich=1, nonmetal_stoich=1,
        delta_gf_A=-100000,
        delta_gf_B=50.0,
        reference="SGTE",
        notes="硫化亚铁"
    ),
}


class CompoundSolubilityCalculator(ThermodynamicProperties):
    """
    化合物溶解度积计算器

    功能：
    1. 计算化合物溶解度积 Ksp
    2. 计算给定成分下的过饱和度
    3. 计算平衡溶质含量
    4. 预测析出驱动力
    """

    def __init__(self):
        super().__init__()
        self.compound_db = COMPOUND_DATABASE

    def get_available_compounds(self) -> List[str]:
        """获取数据库中所有可用的化合物"""
        return list(self.compound_db.keys())

    def get_compound_info(self, compound: str) -> Optional[CompoundData]:
        """获取化合物信息"""
        return self.compound_db.get(compound.upper())

    def add_compound(self, data: CompoundData):
        """向数据库添加化合物"""
        self.compound_db[data.formula.upper()] = data

    def calculate_standard_gibbs_formation(
        self,
        compound: str,
        temperature: float
    ) -> Optional[float]:
        """
        计算化合物的标准生成Gibbs能

        ΔG°f(T) = A + B*T (J/mol)
        """
        data = self.get_compound_info(compound)
        if data is None:
            return None

        return data.delta_gf_A + data.delta_gf_B * temperature

    def calculate_solubility_product_ideal(
        self,
        compound: str,
        temperature: float,
        solution_phase: str = 'LIQUID'
    ) -> dict:
        """
        计算理想溶解度积（假设活度系数为1）

        理论基础：
        ---------
        对于 MₘXₙ(s) ⇌ m·M + n·X

        平衡条件：
        ΔG°_diss = m·G°_M(sol) + n·G°_X(sol) - G°_MₘXₙ = -RT·ln(Ksp,ideal)

        Ksp,ideal = x_M^m · x_X^n (理想情况，γ=1)
        """
        data = self.get_compound_info(compound)
        if data is None:
            return {
                'status': 'error',
                'message': f'化合物 {compound} 不在数据库中'
            }

        M = data.metal_element
        X = data.nonmetal_element
        m = data.metal_stoich
        n = data.nonmetal_stoich

        # 计算化合物标准Gibbs能
        G_compound = self.calculate_standard_gibbs_formation(compound, temperature)

        # 获取溶液中元素的标准Gibbs能
        if solution_phase.upper() == 'LIQUID':
            tdb_phase = 'LIQUID'
        else:
            # 对于固相，使用参考相
            tdb_phase = self.tdb_parser.get_reference_phase(M) or 'BCC_A2'

        G_M = self.tdb_parser.get_gibbs_energy(M, tdb_phase, temperature)
        G_X = self.tdb_parser.get_gibbs_energy(X, tdb_phase, temperature)

        # 如果G_X获取失败，尝试估算
        if G_X is None:
            G_X = self._estimate_lattice_stability(X, tdb_phase, temperature)

        if G_M is None or G_X is None:
            return {
                'status': 'error',
                'message': f'无法获取 {M} 或 {X} 在 {tdb_phase} 中的Gibbs能'
            }

        # 计算溶解Gibbs能变
        # ΔG°_diss = m·G°_M + n·G°_X - G°_compound
        # 注意：这里G_compound是生成Gibbs能（从元素生成化合物）
        # 所以溶解反应的ΔG = -ΔG_formation
        delta_G_diss = m * G_M + n * G_X - G_compound

        # 计算理想溶解度积
        # ln(Ksp) = -ΔG°_diss / RT
        ln_Ksp = -delta_G_diss / (self.R * temperature)

        # 防止溢出
        if ln_Ksp > 100:
            Ksp = float('inf')
            log_Ksp = ln_Ksp / 2.303
        elif ln_Ksp < -100:
            Ksp = 0.0
            log_Ksp = ln_Ksp / 2.303
        else:
            Ksp = math.exp(ln_Ksp)
            log_Ksp = ln_Ksp / 2.303

        return {
            'status': 'success',
            'compound': compound,
            'temperature': temperature,
            'temperature_celsius': temperature - 273.15,
            'Ksp_ideal': Ksp,
            'ln_Ksp': ln_Ksp,
            'log_Ksp': log_Ksp,
            'delta_G_dissolution': delta_G_diss,
            'G_compound': G_compound,
            'G_metal': G_M,
            'G_nonmetal': G_X,
            'metal': M,
            'nonmetal': X,
            'm': m,
            'n': n,
            'model': 'ideal (gamma=1)'
        }

    def calculate_solubility_product_real(
        self,
        compound: str,
        base_composition: Dict[str, float],
        temperature: float,
        solution_phase: str,
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner'
    ) -> dict:
        """
        计算实际溶解度积（考虑活度系数）

        Ksp = (γ_M·x_M)^m · (γ_X·x_X)^n = a_M^m · a_X^n

        在极稀溶液中的简化处理：
        - 使用无限稀释活度系数 γ°
        - Ksp ≈ (γ°_M)^m · (γ°_X)^n · x_M^m · x_X^n
        """
        data = self.get_compound_info(compound)
        if data is None:
            return {
                'status': 'error',
                'message': f'化合物 {compound} 不在数据库中'
            }

        M = data.metal_element
        X = data.nonmetal_element
        m = data.metal_stoich
        n = data.nonmetal_stoich

        # 归一化基础成分
        total = sum(base_composition.values())
        base_comp = {k.upper(): v / total for k, v in base_composition.items()}

        # 确定溶剂
        solvent = max(base_comp.items(), key=lambda item: item[1])[0]

        # 确定相
        if solution_phase.upper() == 'LIQUID':
            tdb_phase = 'LIQUID'
            activity_phase = 'liquid'
        else:
            ref = self.tdb_parser.get_stable_phase(solvent, temperature)
            tdb_phase = ref if ref else 'BCC_A2'
            activity_phase = 'solid'

        # 计算理想溶解度积
        ideal_result = self.calculate_solubility_product_ideal(
            compound, temperature, solution_phase
        )

        if ideal_result['status'] != 'success':
            return ideal_result

        # 在稀溶液中计算活度系数
        # 构建一个包含微量M和X的成分
        test_comp = base_comp.copy()
        x_trace = 0.001  # 微量溶质

        remaining = 1.0 - 2 * x_trace
        test_comp = {el: base_comp[el] * remaining for el in base_comp}
        test_comp[M] = x_trace
        test_comp[X] = x_trace

        # 计算活度系数
        ln_gamma_M = self.calculate_ln_activity_coefficient(
            test_comp, M, temperature, activity_phase,
            extrapolation_func, extrapolation_model_name, activity_model
        )

        ln_gamma_X = self.calculate_ln_activity_coefficient(
            test_comp, X, temperature, activity_phase,
            extrapolation_func, extrapolation_model_name, activity_model
        )

        if ln_gamma_M is None:
            ln_gamma_M = 0.0  # 默认理想
        if ln_gamma_X is None:
            ln_gamma_X = 0.0

        gamma_M = math.exp(ln_gamma_M)
        gamma_X = math.exp(ln_gamma_X)

        # 活度系数校正因子
        gamma_correction = (gamma_M ** m) * (gamma_X ** n)

        # 实际溶解度积
        # Ksp_real = Ksp_ideal * (gamma_M^m * gamma_X^n)^(-1)
        # 因为 Ksp = a^m * a^n = (gamma*x)^m * (gamma*x)^n
        # 而 Ksp_ideal 基于 x 计算，所以：
        Ksp_ideal = ideal_result['Ksp_ideal']

        # 对于溶解反应，活度系数越大，实际溶解度越低
        Ksp_real = Ksp_ideal / gamma_correction if gamma_correction > 0 else Ksp_ideal

        # 计算对数
        if Ksp_real > 0:
            ln_Ksp_real = math.log(Ksp_real)
            log_Ksp_real = ln_Ksp_real / 2.303
        else:
            ln_Ksp_real = float('-inf')
            log_Ksp_real = float('-inf')

        return {
            'status': 'success',
            'compound': compound,
            'temperature': temperature,
            'temperature_celsius': temperature - 273.15,
            'Ksp_real': Ksp_real,
            'Ksp_ideal': Ksp_ideal,
            'ln_Ksp_real': ln_Ksp_real,
            'log_Ksp_real': log_Ksp_real,
            'gamma_M': gamma_M,
            'gamma_X': gamma_X,
            'gamma_correction': gamma_correction,
            'delta_G_dissolution': ideal_result['delta_G_dissolution'],
            'metal': M,
            'nonmetal': X,
            'm': m,
            'n': n,
            'extrapolation_model': extrapolation_model_name,
            'activity_model': activity_model,
            'model': 'real (with activity coefficients)'
        }

    def calculate_supersaturation(
        self,
        compound: str,
        alloy_composition: Dict[str, float],
        temperature: float,
        solution_phase: str,
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner'
    ) -> dict:
        """
        计算过饱和度

        过饱和度 S 定义：
        S = (a_M^m · a_X^n) / Ksp = Q / Ksp

        其中 Q 是实际活度积（离子积）

        - S > 1: 过饱和，倾向析出
        - S = 1: 平衡
        - S < 1: 欠饱和，倾向溶解

        过饱和析出驱动力：
        ΔG_precip = RT·ln(S)
        """
        data = self.get_compound_info(compound)
        if data is None:
            return {
                'status': 'error',
                'message': f'化合物 {compound} 不在数据库中'
            }

        M = data.metal_element
        X = data.nonmetal_element
        m = data.metal_stoich
        n = data.nonmetal_stoich

        # 归一化成分
        total = sum(alloy_composition.values())
        composition = {k.upper(): v / total for k, v in alloy_composition.items()}

        # 检查成分
        if M not in composition or X not in composition:
            return {
                'status': 'error',
                'message': f'合金成分中必须包含 {M} 和 {X}'
            }

        x_M = composition[M]
        x_X = composition[X]

        # 确定溶剂和相
        solvent = max(composition.items(), key=lambda item: item[1])[0]

        if solution_phase.upper() == 'LIQUID':
            tdb_phase = 'LIQUID'
            activity_phase = 'liquid'
        else:
            ref = self.tdb_parser.get_stable_phase(solvent, temperature)
            tdb_phase = ref if ref else 'BCC_A2'
            activity_phase = 'solid'

        # 计算活度系数
        ln_gamma_M = self.calculate_ln_activity_coefficient(
            composition, M, temperature, activity_phase,
            extrapolation_func, extrapolation_model_name, activity_model
        )

        ln_gamma_X = self.calculate_ln_activity_coefficient(
            composition, X, temperature, activity_phase,
            extrapolation_func, extrapolation_model_name, activity_model
        )

        if ln_gamma_M is None:
            ln_gamma_M = 0.0
        if ln_gamma_X is None:
            ln_gamma_X = 0.0

        gamma_M = math.exp(ln_gamma_M)
        gamma_X = math.exp(ln_gamma_X)

        # 计算活度
        a_M = gamma_M * x_M
        a_X = gamma_X * x_X

        # 计算实际活度积 Q
        Q = (a_M ** m) * (a_X ** n)

        # 获取溶解度积
        ksp_result = self.calculate_solubility_product_ideal(compound, temperature, solution_phase)

        if ksp_result['status'] != 'success':
            return ksp_result

        Ksp = ksp_result['Ksp_ideal']

        # 计算过饱和度
        if Ksp > 0:
            S = Q / Ksp
        else:
            S = float('inf')

        # 析出驱动力
        if S > 0:
            delta_G_precip = self.R * temperature * math.log(S)
        else:
            delta_G_precip = float('-inf')

        # 判断状态
        if S > 1.0:
            state = 'supersaturated'
            state_desc = '过饱和，倾向析出'
        elif S < 1.0:
            state = 'undersaturated'
            state_desc = '欠饱和，溶液稳定'
        else:
            state = 'equilibrium'
            state_desc = '平衡状态'

        return {
            'status': 'success',
            'compound': compound,
            'temperature': temperature,
            'supersaturation': S,
            'log_supersaturation': math.log10(S) if S > 0 else float('-inf'),
            'driving_force': delta_G_precip,  # J/mol
            'driving_force_kJ': delta_G_precip / 1000,  # kJ/mol
            'state': state,
            'state_description': state_desc,
            'activity_product_Q': Q,
            'Ksp': Ksp,
            'x_M': x_M,
            'x_X': x_X,
            'a_M': a_M,
            'a_X': a_X,
            'gamma_M': gamma_M,
            'gamma_X': gamma_X,
            'metal': M,
            'nonmetal': X
        }

    def calculate_equilibrium_content(
        self,
        compound: str,
        base_composition: Dict[str, float],
        fixed_element: str,
        fixed_content: float,
        temperature: float,
        solution_phase: str,
        extrapolation_func,
        extrapolation_model_name: str = 'UEM1',
        activity_model: str = 'Wagner'
    ) -> dict:
        """
        计算平衡溶质含量

        给定一种元素的含量，计算另一种元素在平衡时的含量

        例如：给定 [C]，计算平衡时的 [Ti] 含量
        """
        data = self.get_compound_info(compound)
        if data is None:
            return {
                'status': 'error',
                'message': f'化合物 {compound} 不在数据库中'
            }

        M = data.metal_element
        X = data.nonmetal_element
        m = data.metal_stoich
        n = data.nonmetal_stoich

        fixed_element = fixed_element.upper()

        if fixed_element == M:
            variable_element = X
            fixed_stoich = m
            variable_stoich = n
        elif fixed_element == X:
            variable_element = M
            fixed_stoich = n
            variable_stoich = m
        else:
            return {
                'status': 'error',
                'message': f'{fixed_element} 不是化合物 {compound} 的组成元素'
            }

        # 获取溶解度积
        ksp_result = self.calculate_solubility_product_ideal(compound, temperature, solution_phase)

        if ksp_result['status'] != 'success':
            return ksp_result

        Ksp = ksp_result['Ksp_ideal']

        # 在理想情况下：Ksp = x_M^m * x_X^n
        # 给定一个，求另一个
        # x_variable = (Ksp / x_fixed^fixed_stoich)^(1/variable_stoich)

        if fixed_content <= 0:
            return {
                'status': 'error',
                'message': '固定元素含量必须大于0'
            }

        try:
            x_variable_ideal = (Ksp / (fixed_content ** fixed_stoich)) ** (1.0 / variable_stoich)
        except:
            x_variable_ideal = 0.0

        # 限制在合理范围
        x_variable_ideal = max(0.0, min(1.0, x_variable_ideal))

        return {
            'status': 'success',
            'compound': compound,
            'temperature': temperature,
            'fixed_element': fixed_element,
            'fixed_content': fixed_content,
            'variable_element': variable_element,
            'equilibrium_content_ideal': x_variable_ideal,
            'equilibrium_content_ppm': x_variable_ideal * 1e6,
            'Ksp': Ksp,
            'model': 'ideal (for estimation)'
        }

    def _estimate_lattice_stability(self, component: str, target_phase: str, T: float) -> Optional[float]:
        """估算晶格稳定性"""
        comp_upper = component.upper()

        stability_config = {
            'C': {'stable_phase': 'GRAPHITE', 'fixed_diff': 77000.0},
            'N': {'stable_phase': 'GAS', 'fixed_diff': 240000.0},
            'O': {'stable_phase': 'GAS', 'fixed_diff': 250000.0},
            'S': {'stable_phase': 'ORTHORHOMBIC_S', 'fixed_diff': 50000.0},
            'SI': {'stable_phase': 'DIAMOND_A4', 'fixed_diff': 33000.0},
            'B': {'stable_phase': 'RHOMBO_B', 'fixed_diff': 45000.0},
        }

        if comp_upper not in stability_config:
            return None

        config = stability_config[comp_upper]
        ref_phase = config['stable_phase']
        g_stable = self.tdb_parser.get_gibbs_energy(comp_upper, ref_phase, T)

        if g_stable is None:
            ref = self.tdb_parser.get_reference_phase(comp_upper)
            if ref:
                g_stable = self.tdb_parser.get_gibbs_energy(comp_upper, ref, T)

        if g_stable is None:
            return None

        return g_stable + config['fixed_diff']


# 便捷函数
def get_ksp(compound: str, temperature: float) -> Optional[float]:
    """快速获取化合物溶解度积"""
    calc = CompoundSolubilityCalculator()
    result = calc.calculate_solubility_product_ideal(compound, temperature)
    if result['status'] == 'success':
        return result['Ksp_ideal']
    return None


# 测试代码
if __name__ == '__main__':
    from models.extrapolation_models import BinaryModel

    calc = CompoundSolubilityCalculator()
    bm = BinaryModel()

    print("=" * 60)
    print("化合物溶解度积计算测试")
    print("=" * 60)

    # 测试1：TiC溶解度积
    print("\n1. TiC 在液态Fe中的溶解度积 (1873K)")
    result = calc.calculate_solubility_product_ideal("TiC", 1873, "LIQUID")
    if result['status'] == 'success':
        print(f"   log(Ksp) = {result['log_Ksp']:.2f}")
        print(f"   ΔG_dissolution = {result['delta_G_dissolution']/1000:.1f} kJ/mol")

    # 测试2：计算过饱和度
    print("\n2. Fe-0.5%Ti-0.1%C 合金的TiC过饱和度 (1873K)")
    result = calc.calculate_supersaturation(
        compound="TiC",
        alloy_composition={'FE': 0.994, 'TI': 0.005, 'C': 0.001},
        temperature=1873,
        solution_phase='LIQUID',
        extrapolation_func=bm.UEM1
    )
    if result['status'] == 'success':
        print(f"   过饱和度 S = {result['supersaturation']:.2e}")
        print(f"   状态: {result['state_description']}")
        print(f"   析出驱动力 = {result['driving_force_kJ']:.2f} kJ/mol")

    # 测试3：列出可用化合物
    print("\n3. 数据库中的化合物:")
    for comp in calc.get_available_compounds():
        info = calc.get_compound_info(comp)
        print(f"   {comp}: {info.metal_element}{info.metal_stoich}{info.nonmetal_element}{info.nonmetal_stoich}")
