"""
完整测试固相溶解度计算
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
print("完整固相溶解度计算测试")
print("=" * 70)

try:
    result = phase_calc.calculate_solubility(
        base_alloy_composition=base_alloy_composition,
        solute_element=solute_element,
        solution_phase=solution_phase,
        precipitating_phase=precipitating_phase,
        temperature=temperature,
        extrapolation_func=extrap_func,
        extrapolation_model_name=extrap_model_name,
        activity_model=activity_model
    )

    print(f"\n✓ 溶解度计算成功!")
    print(f"  状态: {result['status']}")
    if result['status'] == 'success':
        solubility = result['solubility_mole_fraction']
        print(f"  溶解度 (摩尔分数): {solubility:.6e}")
        print(f"  溶解度 (wt%): {solubility * 100:.6f}%")
    else:
        print(f"  备注: {result}")

except Exception as e:
    print(f"\n❌ 溶解度计算失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
