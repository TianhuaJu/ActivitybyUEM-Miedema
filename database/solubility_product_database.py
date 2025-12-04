"""
Solubility Product Database for Carbides and Nitrides in Steel
================================================================
Based on Turkdogan's "Fundamentals of Steelmaking" and related literature.

溶解度积数据库
用于计算钢中碳化物和氮化物的析出温度

数据来源：
- Turkdogan E.T., "Fundamentals of Steelmaking", Institute of Materials, 1996
- ISIJ International publications on solubility products
- Metallurgical and Materials Transactions research papers

溶解度积表达式: log[%M][%X]^n = A - B/T
其中:
    [%M] = 金属元素的质量百分数 (如 Ti, Nb, V, Al)
    [%X] = 非金属元素的质量百分数 (如 C, N)
    n = 化学计量系数 (通常为1，NbC为0.87)
    A, B = 经验常数
    T = 温度 (K)

析出温度计算:
    T_precip = B / (A - log[%M][%X]^n)
"""

from typing import Dict, Optional, Tuple
import math


# ============================================================================
# 溶解度积常数数据库
# ============================================================================

SOLUBILITY_PRODUCTS = {
    # ========================================
    # 奥氏体 (Austenite, γ-Fe) 中的溶解度积
    # ========================================
    'AUSTENITE': {
        # TiN - 氮化钛 (最稳定的析出物之一)
        # Turkdogan: log[%Ti][%N] = 4.35 - 14890/T
        'TiN': {
            'A': 4.35,
            'B': 14890,
            'n': 1.0,  # [Ti][N]
            'metal': 'TI',
            'nonmetal': 'N',
            'T_min': 1073,  # 800°C
            'T_max': 1673,  # 1400°C
            'reference': 'Turkdogan (1987), ISIJ Int. 38(1998)991',
            'notes': 'Most stable precipitate in austenite'
        },

        # TiC - 碳化钛
        # log[%Ti][%C] = 2.75 - 7000/T
        'TiC': {
            'A': 2.75,
            'B': 7000,
            'n': 1.0,
            'metal': 'TI',
            'nonmetal': 'C',
            'T_min': 1173,
            'T_max': 1673,
            'reference': 'Narita (1975), ISIJ Trans.',
            'notes': 'Less stable than TiN by ~3 orders of magnitude'
        },

        # NbC - 碳化铌
        # Turkdogan/Narita: log[%Nb][%C]^0.87 = 3.42 - 7920/T
        'NbC': {
            'A': 3.42,
            'B': 7920,
            'n': 0.87,  # [Nb][C]^0.87 - 非化学计量
            'metal': 'NB',
            'nonmetal': 'C',
            'T_min': 1073,
            'T_max': 1573,
            'reference': 'Nordberg & Aronsson (1968), JISI 206:1263',
            'notes': 'Non-stoichiometric (NbC0.87)'
        },

        # NbN - 氮化铌
        # log[%Nb][%N] = 2.80 - 8500/T
        'NbN': {
            'A': 2.80,
            'B': 8500,
            'n': 1.0,
            'metal': 'NB',
            'nonmetal': 'N',
            'T_min': 1073,
            'T_max': 1573,
            'reference': 'Irvine et al. (1967), JISI',
            'notes': 'More stable than NbC'
        },

        # VC - 碳化钒
        # log[%V][%C] = 4.70 - 7041/T
        'VC': {
            'A': 4.70,
            'B': 7041,
            'n': 1.0,
            'metal': 'V',
            'nonmetal': 'C',
            'T_min': 973,
            'T_max': 1473,
            'reference': 'Turkdogan (1989), Met. Trans.',
            'notes': 'High solubility, precipitates at lower temperatures'
        },

        # VN - 氮化钒
        # log[%V][%N] = 3.33 - 8278/T
        'VN': {
            'A': 3.33,
            'B': 8278,
            'n': 1.0,
            'metal': 'V',
            'nonmetal': 'N',
            'T_min': 973,
            'T_max': 1473,
            'reference': 'Turkdogan (1989), Met. Trans.',
            'notes': 'More stable than VC'
        },

        # AlN - 氮化铝
        # log[%Al][%N] = 1.79 - 7184/T
        'AlN': {
            'A': 1.79,
            'B': 7184,
            'n': 1.0,
            'metal': 'AL',
            'nonmetal': 'N',
            'T_min': 1073,
            'T_max': 1573,
            'reference': 'Darken et al. (1951), Leslie (1981)',
            'notes': 'Important for grain refinement'
        },

        # Cr23C6 - 铬碳化物 (大约)
        'Cr23C6': {
            'A': 8.87,
            'B': 8800,
            'n': 1.0,  # 简化为 [Cr][C]
            'metal': 'CR',
            'nonmetal': 'C',
            'T_min': 773,
            'T_max': 1173,
            'reference': 'Estimated from Fe-Cr-C diagrams',
            'notes': 'Complex carbide, simplified equation'
        },

        # MnS - 硫化锰
        'MnS': {
            'A': 2.93,
            'B': 9020,
            'n': 1.0,
            'metal': 'MN',
            'nonmetal': 'S',
            'T_min': 1073,
            'T_max': 1673,
            'reference': 'Turkdogan',
            'notes': 'Important inclusion former'
        },
    },

    # ========================================
    # 铁素体 (Ferrite, α-Fe) 中的溶解度积
    # ========================================
    'FERRITE': {
        # TiN in ferrite
        # log[%Ti][%N] = 4.65 - 16310/T
        'TiN': {
            'A': 4.65,
            'B': 16310,
            'n': 1.0,
            'metal': 'TI',
            'nonmetal': 'N',
            'T_min': 773,
            'T_max': 1173,
            'reference': 'Kunze (1995), Steel Research 66:466',
            'notes': 'Even lower solubility than in austenite'
        },

        # TiC in ferrite
        'TiC': {
            'A': 2.90,
            'B': 7070,
            'n': 1.0,
            'metal': 'TI',
            'nonmetal': 'C',
            'T_min': 773,
            'T_max': 1173,
            'reference': 'Derived from austenite data',
            'notes': ''
        },

        # NbC in ferrite
        # log[%Nb][%C] = 3.11 - 7290/T
        'NbC': {
            'A': 3.11,
            'B': 7290,
            'n': 0.87,
            'metal': 'NB',
            'nonmetal': 'C',
            'T_min': 773,
            'T_max': 1173,
            'reference': 'Taylor (1995), ISIJ Int.',
            'notes': 'Lower solubility than in austenite'
        },

        # NbN in ferrite
        'NbN': {
            'A': 2.35,
            'B': 8400,
            'n': 1.0,
            'metal': 'NB',
            'nonmetal': 'N',
            'T_min': 773,
            'T_max': 1173,
            'reference': 'Estimated',
            'notes': ''
        },

        # VC in ferrite
        'VC': {
            'A': 3.88,
            'B': 6560,
            'n': 1.0,
            'metal': 'V',
            'nonmetal': 'C',
            'T_min': 773,
            'T_max': 1173,
            'reference': 'Gustafson (1990)',
            'notes': 'Significant solubility in ferrite'
        },

        # VN in ferrite
        # log[%V][%N] = 3.02 - 7840/T
        'VN': {
            'A': 3.02,
            'B': 7840,
            'n': 1.0,
            'metal': 'V',
            'nonmetal': 'N',
            'T_min': 773,
            'T_max': 1173,
            'reference': 'Thermodynamic calculation',
            'notes': ''
        },

        # AlN in ferrite
        'AlN': {
            'A': 1.35,
            'B': 7400,
            'n': 1.0,
            'metal': 'AL',
            'nonmetal': 'N',
            'T_min': 773,
            'T_max': 1173,
            'reference': 'Leslie (1981)',
            'notes': 'Very low solubility'
        },
    },

    # ========================================
    # 液相 (Liquid) 中的溶解度积
    # ========================================
    'LIQUID': {
        # TiN in liquid iron
        # log[%Ti][%N] = 4.46 - 13500/T
        'TiN': {
            'A': 4.46,
            'B': 13500,
            'n': 1.0,
            'metal': 'TI',
            'nonmetal': 'N',
            'T_min': 1773,
            'T_max': 2073,
            'reference': 'Turkdogan (1987)',
            'notes': 'Higher solubility than in solid phases'
        },

        # TiC in liquid
        'TiC': {
            'A': 3.10,
            'B': 7140,
            'n': 1.0,
            'metal': 'TI',
            'nonmetal': 'C',
            'T_min': 1773,
            'T_max': 2073,
            'reference': 'Estimated',
            'notes': ''
        },

        # NbC in liquid
        'NbC': {
            'A': 3.90,
            'B': 8200,
            'n': 0.87,
            'metal': 'NB',
            'nonmetal': 'C',
            'T_min': 1773,
            'T_max': 2073,
            'reference': 'Estimated from austenite data',
            'notes': ''
        },

        # VN in liquid
        'VN': {
            'A': 3.85,
            'B': 8200,
            'n': 1.0,
            'metal': 'V',
            'nonmetal': 'N',
            'T_min': 1773,
            'T_max': 2073,
            'reference': 'Estimated',
            'notes': ''
        },

        # AlN in liquid
        'AlN': {
            'A': 2.30,
            'B': 7300,
            'n': 1.0,
            'metal': 'AL',
            'nonmetal': 'N',
            'T_min': 1773,
            'T_max': 2073,
            'reference': 'Turkdogan',
            'notes': ''
        },

        # MnS in liquid
        'MnS': {
            'A': 3.20,
            'B': 8500,
            'n': 1.0,
            'metal': 'MN',
            'nonmetal': 'S',
            'T_min': 1773,
            'T_max': 2073,
            'reference': 'Turkdogan',
            'notes': ''
        },
    }
}


# ============================================================================
# 相互作用系数数据 (用于修正多元系统的活度)
# ============================================================================

# Wagner相互作用系数 e_i^j (在1873K液态铁中)
# e_i^j = ∂(log f_i) / ∂[%j]
# 参考: Turkdogan, "Fundamentals of Steelmaking", Table 4.8

INTERACTION_COEFFICIENTS_LIQUID_1873K = {
    'C': {
        'C': 0.14,
        'SI': 0.08,
        'MN': -0.012,
        'CR': -0.024,
        'NI': 0.012,
        'TI': -0.19,
        'NB': -0.06,
        'V': -0.077,
        'AL': 0.043,
        'N': 0.11,
        'S': 0.046,
        'O': -0.34,
    },
    'N': {
        'C': 0.13,
        'SI': 0.047,
        'MN': -0.02,
        'CR': -0.047,
        'NI': 0.015,
        'TI': -0.53,
        'NB': -0.06,
        'V': -0.123,
        'AL': -0.028,
        'N': 0.0,
        'S': 0.007,
        'O': 0.05,
    },
    'TI': {
        'C': -0.165,
        'N': -2.04,
        'SI': 0.05,
        'MN': 0.0,
        'AL': 0.0,
        'O': -1.8,
        'S': -0.11,
        'TI': 0.013,
    },
    'NB': {
        'C': -0.49,
        'N': -0.64,
        'SI': 0.09,
        'MN': 0.0,
        'AL': 0.0,
        'O': -0.83,
        'S': -0.05,
        'NB': 0.0,
    },
    'V': {
        'C': -0.34,
        'N': -0.29,
        'SI': 0.042,
        'MN': 0.0,
        'AL': 0.0,
        'O': -0.97,
        'S': -0.016,
        'V': 0.015,
    },
    'AL': {
        'C': 0.091,
        'N': -0.058,
        'SI': 0.056,
        'MN': 0.0,
        'O': -6.6,
        'S': 0.035,
        'AL': 0.045,
    },
    'S': {
        'C': 0.11,
        'SI': 0.063,
        'MN': -0.026,
        'CR': -0.011,
        'NI': 0.0,
        'TI': -0.072,
        'AL': 0.035,
        'N': 0.01,
        'S': -0.028,
        'O': -0.27,
    },
}


# ============================================================================
# 辅助函数
# ============================================================================

def get_solubility_product_data(compound: str, phase: str) -> Optional[Dict]:
    """
    获取指定化合物在指定相中的溶解度积数据

    Args:
        compound: 化合物名称，如 'TiN', 'NbC', 'VN'
        phase: 相名称，'AUSTENITE', 'FERRITE', 'LIQUID'

    Returns:
        溶解度积数据字典，或 None
    """
    phase_upper = phase.upper()

    # 相名称映射
    phase_map = {
        'FCC_A1': 'AUSTENITE',
        'FCC': 'AUSTENITE',
        'GAMMA': 'AUSTENITE',
        'BCC_A2': 'FERRITE',
        'BCC': 'FERRITE',
        'ALPHA': 'FERRITE',
    }

    phase_key = phase_map.get(phase_upper, phase_upper)

    if phase_key not in SOLUBILITY_PRODUCTS:
        return None

    # 大小写不敏感的化合物查找
    phase_data = SOLUBILITY_PRODUCTS[phase_key]
    compound_upper = compound.upper()

    # 直接查找
    if compound in phase_data:
        return phase_data[compound]

    # 大小写不敏感查找
    for key in phase_data:
        if key.upper() == compound_upper:
            return phase_data[key]

    return None


def calculate_log_solubility_product(compound: str, phase: str, temperature: float) -> Optional[float]:
    """
    计算指定温度下的溶解度积 log Ks

    Args:
        compound: 化合物名称
        phase: 相名称
        temperature: 温度 (K)

    Returns:
        log Ks 值，或 None
    """
    data = get_solubility_product_data(compound, phase)
    if data is None:
        return None

    A = data['A']
    B = data['B']

    return A - B / temperature


def calculate_precipitation_temperature_from_product(
    compound: str,
    phase: str,
    metal_wt_pct: float,
    nonmetal_wt_pct: float
) -> Optional[float]:
    """
    根据溶解度积计算析出温度

    T_precip = B / (A - log([%M][%X]^n))

    Args:
        compound: 化合物名称
        phase: 相名称
        metal_wt_pct: 金属元素质量百分数
        nonmetal_wt_pct: 非金属元素质量百分数

    Returns:
        析出温度 (K)，或 None
    """
    data = get_solubility_product_data(compound, phase)
    if data is None:
        return None

    A = data['A']
    B = data['B']
    n = data.get('n', 1.0)

    # 计算 log([%M][%X]^n)
    if metal_wt_pct <= 0 or nonmetal_wt_pct <= 0:
        return None

    log_product = math.log10(metal_wt_pct) + n * math.log10(nonmetal_wt_pct)

    # T = B / (A - log_product)
    denominator = A - log_product
    if denominator <= 0:
        # 溶解度积过大，不会析出
        return None

    return B / denominator


def calculate_equilibrium_content(
    compound: str,
    phase: str,
    temperature: float,
    fixed_element: str,
    fixed_wt_pct: float
) -> Optional[float]:
    """
    计算给定温度和一个元素含量时，另一元素的平衡含量

    Args:
        compound: 化合物名称
        phase: 相名称
        temperature: 温度 (K)
        fixed_element: 固定元素 ('metal' 或 'nonmetal')
        fixed_wt_pct: 固定元素的质量百分数

    Returns:
        另一元素的平衡质量百分数，或 None
    """
    data = get_solubility_product_data(compound, phase)
    if data is None:
        return None

    log_Ks = calculate_log_solubility_product(compound, phase, temperature)
    if log_Ks is None:
        return None

    n = data.get('n', 1.0)
    Ks = 10 ** log_Ks

    if fixed_element.lower() == 'metal':
        # [%X] = (Ks / [%M])^(1/n)
        if fixed_wt_pct <= 0:
            return None
        return (Ks / fixed_wt_pct) ** (1.0 / n)
    else:
        # [%M] = Ks / [%X]^n
        if fixed_wt_pct <= 0:
            return None
        return Ks / (fixed_wt_pct ** n)


def get_precipitation_sequence(
    composition_wt_pct: Dict[str, float],
    phase: str = 'AUSTENITE'
) -> list:
    """
    计算多种析出物的析出顺序（按温度从高到低排列）

    Args:
        composition_wt_pct: 成分（质量百分数）
        phase: 相名称

    Returns:
        按析出温度排序的列表 [(化合物, 析出温度), ...]
    """
    results = []

    phase_data = SOLUBILITY_PRODUCTS.get(phase.upper(), {})

    for compound, data in phase_data.items():
        metal = data['metal']
        nonmetal = data['nonmetal']

        metal_content = composition_wt_pct.get(metal, 0)
        nonmetal_content = composition_wt_pct.get(nonmetal, 0)

        if metal_content > 0 and nonmetal_content > 0:
            T_precip = calculate_precipitation_temperature_from_product(
                compound, phase, metal_content, nonmetal_content
            )
            if T_precip is not None:
                results.append((compound, T_precip))

    # 按温度降序排列（高温先析出）
    results.sort(key=lambda x: x[1], reverse=True)

    return results


def mole_to_weight_percent(mole_fraction: float, element: str, base_element: str = 'FE') -> float:
    """
    将摩尔分数转换为质量百分数（简化版，假设二元系统）

    [wt%] ≈ x * M_element / (x * M_element + (1-x) * M_base) * 100
    """
    # 原子量
    atomic_weights = {
        'FE': 55.845, 'C': 12.011, 'N': 14.007, 'TI': 47.867,
        'NB': 92.906, 'V': 50.942, 'AL': 26.982, 'SI': 28.086,
        'MN': 54.938, 'CR': 51.996, 'NI': 58.693, 'MO': 95.94,
        'S': 32.065, 'O': 15.999, 'H': 1.008, 'B': 10.811
    }

    M_el = atomic_weights.get(element.upper(), 50.0)
    M_base = atomic_weights.get(base_element.upper(), 55.845)

    if mole_fraction <= 0:
        return 0.0
    if mole_fraction >= 1:
        return 100.0

    x = mole_fraction
    wt_pct = (x * M_el) / (x * M_el + (1 - x) * M_base) * 100

    return wt_pct


def weight_to_mole_percent(weight_percent: float, element: str, base_element: str = 'FE') -> float:
    """
    将质量百分数转换为摩尔分数
    """
    atomic_weights = {
        'FE': 55.845, 'C': 12.011, 'N': 14.007, 'TI': 47.867,
        'NB': 92.906, 'V': 50.942, 'AL': 26.982, 'SI': 28.086,
        'MN': 54.938, 'CR': 51.996, 'NI': 58.693, 'MO': 95.94,
        'S': 32.065, 'O': 15.999, 'H': 1.008, 'B': 10.811
    }

    M_el = atomic_weights.get(element.upper(), 50.0)
    M_base = atomic_weights.get(base_element.upper(), 55.845)

    if weight_percent <= 0:
        return 0.0
    if weight_percent >= 100:
        return 1.0

    w = weight_percent / 100.0
    x = (w / M_el) / (w / M_el + (1 - w) / M_base)

    return x


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("Solubility Product Database - Test")
    print("=" * 70)

    # 测试1: TiN在奥氏体中的析出温度
    print("\n--- Test 1: TiN precipitation in austenite ---")
    Ti_wt = 0.02  # 0.02% Ti
    N_wt = 0.005  # 0.005% N (50 ppm)

    T_precip = calculate_precipitation_temperature_from_product('TiN', 'AUSTENITE', Ti_wt, N_wt)
    if T_precip:
        print(f"Composition: {Ti_wt}% Ti, {N_wt}% N")
        print(f"Precipitation temperature: {T_precip:.1f} K ({T_precip-273.15:.1f} °C)")

    # 测试2: NbC在奥氏体中的析出温度
    print("\n--- Test 2: NbC precipitation in austenite ---")
    Nb_wt = 0.03  # 0.03% Nb
    C_wt = 0.05   # 0.05% C

    T_precip = calculate_precipitation_temperature_from_product('NbC', 'AUSTENITE', Nb_wt, C_wt)
    if T_precip:
        print(f"Composition: {Nb_wt}% Nb, {C_wt}% C")
        print(f"Precipitation temperature: {T_precip:.1f} K ({T_precip-273.15:.1f} °C)")

    # 测试3: 析出顺序
    print("\n--- Test 3: Precipitation sequence ---")
    steel_comp = {
        'TI': 0.015,
        'NB': 0.025,
        'V': 0.05,
        'C': 0.08,
        'N': 0.008,
        'AL': 0.03
    }

    sequence = get_precipitation_sequence(steel_comp, 'AUSTENITE')
    print(f"Steel composition: {steel_comp}")
    print("\nPrecipitation sequence (high to low temperature):")
    for compound, T in sequence:
        print(f"  {compound}: {T:.1f} K ({T-273.15:.1f} °C)")

    # 测试4: log Ks vs temperature
    print("\n--- Test 4: log Ks vs temperature for TiN in austenite ---")
    for T in [1173, 1273, 1373, 1473, 1573]:
        log_Ks = calculate_log_solubility_product('TiN', 'AUSTENITE', T)
        Ks = 10 ** log_Ks if log_Ks else 0
        print(f"  T = {T} K ({T-273.15:.0f}°C): log Ks = {log_Ks:.3f}, Ks = {Ks:.2e}")
