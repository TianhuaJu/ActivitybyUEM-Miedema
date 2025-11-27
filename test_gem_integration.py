#!/usr/bin/env python
"""
GEM Integration Test
====================
验证GEM求解器与GUI的集成是否正确
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calculations.phase_equilibrium_calculator import PhaseEquilibriumCalculator
from models.extrapolation_models import BinaryModel

def test_gui_compatible_method():
    """测试GUI兼容方法"""
    print("=" * 60)
    print("测试 GEM 求解器与 GUI 集成")
    print("=" * 60)

    # 创建计算器
    calculator = PhaseEquilibriumCalculator()
    binary_model = BinaryModel()

    # 测试组成
    composition = {'Fe': 0.70, 'C': 0.03, 'Si': 0.27}
    temperature = 1873.0  # K

    print(f"\n测试输入:")
    print(f"  组成: {composition}")
    print(f"  温度: {temperature} K")

    try:
        # 调用GUI兼容方法
        result = calculator.calculate_phase_equilibrium_gui_compatible(
            composition=composition,
            temperature=temperature,
            extrapolation_model_func=binary_model.UEM1,
            extrapolation_model_name='UEM1',
            activity_model='Wagner'
        )

        print(f"\n✓ GUI兼容方法调用成功")
        print(f"\n返回结果类型: {type(result).__name__}")
        print(f"结果状态: {result.get('status', 'unknown')}")
        print(f"消息: {result.get('message', 'N/A')}")

        # 验证返回格式
        required_keys = ['status', 'temperature', 'total_composition', 'phases', 'message']
        missing_keys = [key for key in required_keys if key not in result]

        if missing_keys:
            print(f"\n⚠ 警告: 缺少必需的键: {missing_keys}")
            return False

        print(f"\n✓ 返回格式验证通过")

        # 显示相信息
        if 'phases' in result and result['phases']:
            print(f"\n平衡相信息:")
            for i, phase in enumerate(result['phases'], 1):
                print(f"  相 {i}: {phase.name}")
                print(f"    分数: {phase.fraction:.4f} ({phase.fraction*100:.2f}%)")
                print(f"    组成: {phase.composition}")
        else:
            print(f"\n⚠ 警告: 未找到平衡相")

        return True

    except Exception as e:
        print(f"\n✗ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_temperature_variation():
    """测试温度变化分析方法"""
    print("\n" + "=" * 60)
    print("测试温度变化分析方法")
    print("=" * 60)

    calculator = PhaseEquilibriumCalculator()
    binary_model = BinaryModel()

    composition = {'Fe': 0.70, 'C': 0.03, 'Si': 0.27}
    T_min = 1273.0
    T_max = 1473.0
    n_points = 5

    print(f"\n测试输入:")
    print(f"  组成: {composition}")
    print(f"  温度范围: {T_min} - {T_max} K")
    print(f"  点数: {n_points}")

    try:
        result = calculator.calculate_phase_equilibrium_vs_temperature(
            composition=composition,
            T_min=T_min,
            T_max=T_max,
            n_points=n_points,
            extrapolation_func=binary_model.UEM1,
            extrapolation_model_name='UEM1',
            activity_model='Wagner'
        )

        print(f"\n✓ 温度变化方法调用成功")
        print(f"温度点数: {len(result.get('temperatures', []))}")
        print(f"发现相: {list(result.get('phase_fractions', {}).keys())}")

        # 验证数组长度一致性
        phase_fractions = result.get('phase_fractions', {})
        if phase_fractions:
            lengths = [len(fracs) for fracs in phase_fractions.values()]
            if len(set(lengths)) == 1:
                print(f"✓ 所有相数组长度一致: {lengths[0]}")
            else:
                print(f"⚠ 警告: 相数组长度不一致: {lengths}")
                return False

        return True

    except Exception as e:
        print(f"\n✗ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_composition_variation():
    """测试组分变化分析方法"""
    print("\n" + "=" * 60)
    print("测试组分变化分析方法")
    print("=" * 60)

    calculator = PhaseEquilibriumCalculator()
    binary_model = BinaryModel()

    base_composition = {'Fe': 0.97, 'Si': 0.03}
    variable_element = 'C'
    x_min = 0.0
    x_max = 0.05
    temperature = 1873.0
    n_points = 5

    print(f"\n测试输入:")
    print(f"  基础组成: {base_composition}")
    print(f"  变化元素: {variable_element}")
    print(f"  组分范围: {x_min} - {x_max}")
    print(f"  温度: {temperature} K")
    print(f"  点数: {n_points}")

    try:
        result = calculator.calculate_phase_equilibrium_vs_composition(
            base_composition=base_composition,
            variable_element=variable_element,
            x_min=x_min,
            x_max=x_max,
            temperature=temperature,
            n_points=n_points,
            extrapolation_func=binary_model.UEM1,
            extrapolation_model_name='UEM1',
            activity_model='Wagner'
        )

        print(f"\n✓ 组分变化方法调用成功")
        print(f"组分点数: {len(result.get('compositions', []))}")
        print(f"发现相: {list(result.get('phase_fractions', {}).keys())}")

        # 验证数组长度一致性
        phase_fractions = result.get('phase_fractions', {})
        if phase_fractions:
            lengths = [len(fracs) for fracs in phase_fractions.values()]
            if len(set(lengths)) == 1:
                print(f"✓ 所有相数组长度一致: {lengths[0]}")
            else:
                print(f"⚠ 警告: 相数组长度不一致: {lengths}")
                return False

        return True

    except Exception as e:
        print(f"\n✗ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("\n开始 GEM 集成测试...\n")

    results = []

    # 运行测试
    results.append(("GUI兼容方法", test_gui_compatible_method()))
    results.append(("温度变化分析", test_temperature_variation()))
    results.append(("组分变化分析", test_composition_variation()))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{test_name}: {status}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print(f"\n{'='*60}")
        print("✓ 所有测试通过! GEM 集成成功!")
        print(f"{'='*60}\n")
        sys.exit(0)
    else:
        print(f"\n{'='*60}")
        print("✗ 部分测试失败")
        print(f"{'='*60}\n")
        sys.exit(1)
