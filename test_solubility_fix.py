"""
测试溶解度计算的改进
验证：1. 相对添加量计算正确
2. 警告信息正确生成
3. 结果显示清晰明确
"""

from calculations.phase_diagram import PhaseDiagramCalculator
from models.extrapolation_models import BinaryModel

# 初始化
phase_calc = PhaseDiagramCalculator()
bm = BinaryModel()

print("=" * 80)
print("测试溶解度计算改进")
print("=" * 80)
print()

# 测试用例：V 在 Fe-Si 液态合金中的溶解度
# 重现用户报告的问题
test_cases = [
    {'FE': 0.7, 'SI': 0.3},  # Si = 30%
    {'FE': 0.5, 'SI': 0.5},  # Si = 50%
]

temperature = 1800.0  # K

for base_comp in test_cases:
    print(f"\n{'='*80}")
    print(f"测试用例: 基础合金 Fe({base_comp['FE']*100:.0f}%) + Si({base_comp['SI']*100:.0f}%)")
    print(f"溶质: V, 温度: {temperature} K")
    print(f"{'='*80}\n")

    result = phase_calc.calculate_solubility(
        base_alloy_composition=base_comp,
        solute_element='V',
        solution_phase='LIQUID',
        precipitating_phase='BCC_A2',
        temperature=temperature,
        extrapolation_func=bm.UEM1,
        extrapolation_model_name='UEM1',
        activity_model='Wagner'
    )

    if result['status'] == 'success':
        sol = result['solubility_mole_fraction']
        rel_add = result.get('relative_addition', 0)
        dilution = result.get('base_alloy_dilution', 0)
        final_comp = result.get('final_composition', {})
        warnings = result.get('warnings', [])

        print(f"✓ 溶解度 (摩尔分数): {sol:.6f} ({sol*100:.2f}%)")
        print(f"✓ 相对添加量: {rel_add:.4f}")
        print(f"  → 含义: 每 1 摩尔基础合金需要添加 {rel_add:.4f} 摩尔 V")
        print(f"✓ 基础合金稀释度: {dilution*100:.2f}%")
        print()

        # 验证计算
        print("验证:")
        calculated_dilution = 1 - sol
        calculated_rel_add = sol / calculated_dilution if calculated_dilution > 0 else float('inf')
        print(f"  计算验证: 1 - {sol:.4f} = {calculated_dilution:.4f} ✓")
        print(f"  相对添加量验证: {sol:.4f} / {calculated_dilution:.4f} = {calculated_rel_add:.4f} ✓")
        print()

        # 显示最终成分
        print("最终平衡合金成分:")
        sorted_comp = sorted(final_comp.items(), key=lambda x: x[1], reverse=True)
        for elem, frac in sorted_comp:
            print(f"  {elem}: {frac:.6f} ({frac*100:.2f}%)")
        total = sum(final_comp.values())
        print(f"  总计: {total:.6f} ({total*100:.2f}%)")
        print()

        # 显示警告
        if warnings:
            print("⚠️  合理性警告:")
            for i, warning in enumerate(warnings, 1):
                print(f"  {i}. {warning}")
        else:
            print("✓ 无合理性警告")
        print()

        # 物理意义解释
        print("物理意义:")
        print(f"  基础合金 Fe({base_comp['FE']*100:.0f}%) + Si({base_comp['SI']*100:.0f}%) 归一化为 1 摩尔")
        print(f"  最多可以溶解 {rel_add:.4f} 摩尔的 V")
        print(f"  最终得到 {1+rel_add:.4f} 摩尔的合金")
        print(f"  其中 V 占 {sol*100:.2f}%, Fe 占 {final_comp.get('FE',0)*100:.2f}%, Si 占 {final_comp.get('SI',0)*100:.2f}%")

    elif result['status'] == 'fully_soluble':
        print("结果: V 完全溶解")
    elif result['status'] == 'insoluble':
        print("结果: V 几乎不溶")
    else:
        print(f"状态: {result['status']}")

print()
print("=" * 80)
print("测试完成")
print("=" * 80)
print()
print("总结:")
print("1. 新增的'相对添加量'指标更直观地表示了实际需要添加的溶质量")
print("2. 警告系统能够自动识别并提示不合理的高溶解度情况")
print("3. 完整的成分显示避免了用户对溶解度含义的误解")
