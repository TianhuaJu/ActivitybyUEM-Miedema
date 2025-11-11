"""
测试固相溶解度计算
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calculations.phase_diagram import PhaseDiagramCalculator
from models.extrapolation_models import BinaryModel

# 创建计算器
phase_calc = PhaseDiagramCalculator()

# 准备参数
base_alloy_composition = {'FE': 0.7, 'SI': 0.3}
solute_element = 'C'
solution_phase = 'SOLID'
precipitating_phase = 'GRAPHITE'
temperature = 1200.0

# 外推模型
bm = BinaryModel()
extrap_func = bm.UEM1
extrap_model_name = 'UEM1'
activity_model = 'Wagner'

print("=" * 70)
print("测试固相溶解度计算")
print("=" * 70)
print(f"基础合金: {base_alloy_composition}")
print(f"溶质元素: {solute_element}")
print(f"溶液相: {solution_phase}")
print(f"析出相: {precipitating_phase}")
print(f"温度: {temperature} K")
print(f"外推模型: {extrap_model_name}")
print(f"活度模型: {activity_model}")
print("=" * 70)

# 测试化学势计算
print("\n1. 测试固相化学势计算 (x_C = 1e-9):")
test_composition = {'FE': 0.7 * (1 - 1e-9), 'SI': 0.3 * (1 - 1e-9), 'C': 1e-9}
print(f"   成分: {test_composition}")

mu_solid = phase_calc._get_chemical_potential(
    composition=test_composition,
    component=solute_element,
    temperature=temperature,
    tdb_phase='SOLID',
    extrapolation_model_func=extrap_func,
    extrapolation_model=extrap_model_name,
    activity_model=activity_model
)

if mu_solid is None:
    print("   ❌ 化学势计算失败!")
else:
    print(f"   ✓ μ_C = {mu_solid:.2f} J/mol")

# 测试 TDB 数据查询
print("\n2. 测试 TDB 数据查询:")
print(f"   查询 FE 的参考相:")
fe_ref = phase_calc.tdb_parser.get_reference_phase('FE')
print(f"     FE -> {fe_ref}")

if fe_ref:
    print(f"   查询 C-{fe_ref} 的 Gibbs 能量 @ {temperature}K:")
    g_c = phase_calc.tdb_parser.get_gibbs_energy('C', fe_ref, temperature)
    if g_c is None:
        print(f"     ❌ 无法获取 C-{fe_ref} 的 Gibbs 能量")
    else:
        print(f"     ✓ G°_C,{fe_ref} = {g_c:.2f} J/mol")

print("\n3. 测试活度系数计算:")
from calculations.thermodynamic_properties import ThermodynamicProperties
thermo = ThermodynamicProperties()

ln_gamma = thermo.calculate_ln_activity_coefficient(
    composition=test_composition,
    component=solute_element,
    temperature=temperature,
    phase_state='solid',
    extrapolation_model_func=extrap_func,
    extrapolation_model_name=extrap_model_name,
    activity_model=activity_model
)

if ln_gamma is None:
    print(f"   ❌ 活度系数计算失败!")
else:
    print(f"   ✓ ln(γ_C) = {ln_gamma:.4f}")

print("\n" + "=" * 70)
print("诊断完成")
print("=" * 70)
