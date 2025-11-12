"""
测试 Si 溶解度计算问题
用户报告：当 x_V=0.5 时，Si 的溶解度为 0.7，这显然不合理
"""

from calculations.phase_diagram import PhaseDiagramCalculator
from models.extrapolation_models import BinaryModel

# 初始化
phase_calc = PhaseDiagramCalculator()
bm = BinaryModel()

print("=" * 70)
print("测试 Si 在 Fe-V 合金中的溶解度")
print("=" * 70)

# 测试不同 V 含量下的 Si 溶解度
test_cases = [
    {'FE': 1.0, 'V': 0.0},   # 纯 Fe
    {'FE': 0.9, 'V': 0.1},   # V = 10%
    {'FE': 0.7, 'V': 0.3},   # V = 30%
    {'FE': 0.5, 'V': 0.5},   # V = 50% (用户报告的情况)
    {'FE': 0.3, 'V': 0.7},   # V = 70%
]

temperature = 1800.0  # K (液相)

for base_comp in test_cases:
    print(f"\n基础合金: Fe({base_comp['FE']*100:.0f}%) + V({base_comp['V']*100:.0f}%)")
    print("-" * 70)

    try:
        result = phase_calc.calculate_solubility(
            base_alloy_composition=base_comp,
            solute_element='SI',
            solution_phase='LIQUID',
            precipitating_phase='DIAMOND_A4',  # Si 的稳定相
            temperature=temperature,
            extrapolation_func=bm.UEM1,
            extrapolation_model_name='UEM1',
            activity_model='Wagner'
        )

        if result['status'] == 'success':
            solubility = result['solubility_mole_fraction']
            final_comp = result.get('final_composition', {})

            print(f"✓ Si 溶解度: {solubility:.6f} ({solubility*100:.2f}%)")

            if final_comp:
                print(f"\n最终平衡合金成分（总计=100%）：")
                sorted_comp = sorted(final_comp.items(), key=lambda x: x[1], reverse=True)
                for elem, mole_frac in sorted_comp:
                    print(f"  {elem}: {mole_frac:.6f} ({mole_frac*100:.2f}%)")

                total = sum(final_comp.values())
                print(f"  总计: {total:.6f} ({total*100:.2f}%)")

                # 检查是否"不合理"
                if solubility > 0.5:
                    print(f"\n⚠️  警告: Si 溶解度 ({solubility*100:.2f}%) > 50%")
                    print(f"    这意味着最终合金中 Si 是主要成分，而不是溶质")
                    print(f"    基础合金被大幅稀释: Fe({final_comp.get('FE',0)*100:.2f}%) + V({final_comp.get('V',0)*100:.2f}%)")
        else:
            print(f"❌ 计算失败: {result.get('message', 'Unknown error')}")

    except Exception as e:
        print(f"❌ 计算出错: {str(e)}")

print("\n" + "=" * 70)
print("分析")
print("=" * 70)
print("""
当前算法的定义：
  "溶解度"是指溶质在最终平衡合金中的摩尔分数。

  当基础合金为 Fe(50%) + V(50%)，Si 溶解度为 70% 时：
  - 最终合金: Si(70%) + Fe(15%) + V(15%) = 100%
  - 基础合金被稀释到 30%

可能的问题：
  1. 物理意义不明确：当溶解度 > 50% 时，"溶质"变成了"溶剂"
  2. 用户期望：溶解度应该 < (1 - x_V)，即不能超过剩余空间

建议的修正方案：
  1. 添加合理性检查，当溶解度过高时发出警告
  2. 重新定义"溶解度"的含义（例如：溶质在基础合金+溶质中的最大添加量）
  3. 修改计算逻辑，确保基础合金成分保持相对比例不变
""")
