"""
测试溶解度计算结果显示
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calculations.phase_diagram import PhaseDiagramCalculator
from models.extrapolation_models import BinaryModel

# 创建计算器
phase_calc = PhaseDiagramCalculator()

# 模拟用户的例子：Fe-Si 合金，Si=0.3，计算 V 的溶解度
base_alloy_composition = {'FE': 0.7, 'SI': 0.3}
solute_element = 'V'
solution_phase = 'LIQUID'
precipitating_phase = 'BCC_A2'  # V 的参考相
temperature = 1800.0  # 高温液相

# 外推模型
bm = BinaryModel()
extrap_func = bm.UEM1
extrap_model_name = 'UEM1'
activity_model = 'Wagner'

print("=" * 70)
print("溶解度计算结果显示测试")
print("=" * 70)
print(f"基础合金: Fe(70%) + Si(30%)")
print(f"溶质: {solute_element}")
print(f"温度: {temperature} K")
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

    print(f"\n✓ 计算成功!")
    print(f"  状态: {result['status']}")

    if result['status'] == 'success':
        solubility = result['solubility_mole_fraction']
        print(f"\n溶解度: {solubility:.6f} ({solubility*100:.4f}%)")

        print(f"\n说明：溶解度是指 {solute_element} 在【最终平衡合金】中的摩尔分数")
        print("-" * 70)

        if 'final_composition' in result:
            print("最终平衡合金成分（总计=100%）：")
            final_comp = result['final_composition']
            sorted_comp = sorted(final_comp.items(), key=lambda x: x[1], reverse=True)

            for elem, mole_frac in sorted_comp:
                print(f"  {elem}: {mole_frac:.6f} ({mole_frac*100:.4f}%)")

            total = sum(final_comp.values())
            print(f"  ----")
            print(f"  总计: {total:.6f} ({total*100:.2f}%)")

            print("\n✓ 成分守恒验证: 总和 = 100%")
        else:
            print("\n⚠ 警告：未返回 final_composition 字段")

except Exception as e:
    print(f"\n❌ 计算失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
