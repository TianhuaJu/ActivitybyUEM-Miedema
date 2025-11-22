#!/usr/bin/env python3
"""
温度曲线性能诊断工具
==================
分析温度曲线计算为什么慢，找出具体瓶颈
"""

import time
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class PerformanceProfiler:
    """性能分析器 - 记录函数调用次数和时间"""

    def __init__(self):
        self.stats = defaultdict(lambda: {'count': 0, 'total_time': 0.0})
        self.stack = []

    def start(self, name):
        """开始计时"""
        self.stack.append((name, time.time()))

    def end(self):
        """结束计时"""
        if not self.stack:
            return
        name, start_time = self.stack.pop()
        elapsed = time.time() - start_time
        self.stats[name]['count'] += 1
        self.stats[name]['total_time'] += elapsed

    def report(self):
        """生成报告"""
        print("\n" + "="*70)
        print("性能分析报告")
        print("="*70)

        # 按总时间排序
        sorted_stats = sorted(
            self.stats.items(),
            key=lambda x: x[1]['total_time'],
            reverse=True
        )

        print(f"{'函数名':<40} {'调用次数':>10} {'总时间(s)':>10} {'平均(s)':>10}")
        print("-"*70)

        for name, data in sorted_stats:
            count = data['count']
            total = data['total_time']
            avg = total / count if count > 0 else 0
            print(f"{name:<40} {count:>10} {total:>10.3f} {avg:>10.4f}")

        print("="*70)


# 全局分析器
profiler = PerformanceProfiler()


def test_single_temperature_point():
    """测试单个温度点的计算，详细分析"""
    print("="*70)
    print("测试单个温度点计算")
    print("="*70)

    from calculations.parallel_solubility import compute_temperature_point
    from calculations.phase_diagram import PhaseDiagramCalculator

    # 准备参数
    params = {
        't_curr': 1200.0,
        'index': 0,
        'base_composition': {'Fe': 0.95, 'Si': 0.05},
        'solute': 'C',
        'tdb_solution_phase': 'BCC_A2',
        'extrap_model_name': 'UEM1',
        'activity_model': 'Wagner'
    }

    print(f"\n测试参数:")
    print(f"  温度: {params['t_curr']}K")
    print(f"  基础合金: {params['base_composition']}")
    print(f"  溶质: {params['solute']}")
    print(f"  模型: {params['extrap_model_name']}")

    # 单点计算
    print(f"\n开始计算...")
    start = time.time()
    result = compute_temperature_point(params)
    elapsed = time.time() - start

    print(f"\n计算完成!")
    print(f"  总耗时: {elapsed:.3f}秒")
    print(f"  状态: {result[3].get('status', 'unknown')}")
    print(f"  溶解度: {result[1]:.6f}")
    print(f"  理想溶解度: {result[2]:.6f}")

    return elapsed


def test_temperature_curve():
    """测试完整温度曲线计算"""
    print("\n" + "="*70)
    print("测试温度曲线计算（20个点）")
    print("="*70)

    from calculations.parallel_solubility import compute_temperature_point

    # 准备20个温度点
    n_points = 20
    t_start = 800.0
    t_end = 1400.0
    temperatures = [t_start + i * (t_end - t_start) / (n_points - 1) for i in range(n_points)]

    tasks = []
    for i, temp in enumerate(temperatures):
        tasks.append({
            't_curr': temp,
            'index': i,
            'base_composition': {'Fe': 0.95, 'Si': 0.05},
            'solute': 'C',
            'tdb_solution_phase': 'BCC_A2',
            'extrap_model_name': 'UEM1',
            'activity_model': 'Wagner'
        })

    print(f"\n计算配置:")
    print(f"  温度范围: {t_start}K - {t_end}K")
    print(f"  采样点数: {n_points}")
    print(f"  基础合金: Fe-5%Si")
    print(f"  溶质: C")

    # 串行计算
    print(f"\n开始串行计算...")
    start = time.time()
    results = []
    for i, task in enumerate(tasks):
        t0 = time.time()
        result = compute_temperature_point(task)
        t1 = time.time()
        results.append(result)
        print(f"  点 {i+1}/{n_points}: T={task['t_curr']:.1f}K, 耗时={t1-t0:.2f}s, 状态={result[3].get('status', 'unknown')}")

    serial_time = time.time() - start

    print(f"\n串行计算完成:")
    print(f"  总耗时: {serial_time:.2f}秒")
    print(f"  平均每点: {serial_time/n_points:.2f}秒")

    # 分析结果
    success_count = sum(1 for r in results if r[3].get('status') == 'success')
    print(f"  成功计算: {success_count}/{n_points} ({success_count/n_points*100:.1f}%)")

    return serial_time, serial_time/n_points


def analyze_calculation_steps():
    """详细分析计算步骤的时间分配"""
    print("\n" + "="*70)
    print("详细步骤时间分析")
    print("="*70)

    from calculations.phase_diagram import PhaseDiagramCalculator
    from models.extrapolation_models import BinaryModel

    calc = PhaseDiagramCalculator()
    bm = BinaryModel()

    base_composition = {'Fe': 0.95, 'Si': 0.05}
    solute = 'C'
    temperature = 1200.0
    tdb_solution_phase = 'BCC_A2'
    extrap_func = bm.UEM1
    extrap_model_name = 'UEM1'
    activity_model = 'Wagner'

    print(f"\n测试参数:")
    print(f"  基础合金: {base_composition}")
    print(f"  温度: {temperature}K")
    print(f"  溶质: {solute}")

    # 步骤1: 实际溶解度计算
    print(f"\n步骤1: 计算实际溶解度...")
    t0 = time.time()
    result = calc.calculate_solubility(
        base_alloy_composition=base_composition,
        solute_element=solute,
        solution_phase=tdb_solution_phase,
        temperature=temperature,
        extrapolation_func=extrap_func,
        extrapolation_model_name=extrap_model_name,
        activity_model=activity_model
    )
    t1 = time.time()
    actual_time = t1 - t0
    print(f"  耗时: {actual_time:.3f}秒")
    print(f"  状态: {result.get('status')}")
    print(f"  溶解度: {result.get('solubility_mole_fraction', 0):.6f}")

    # 步骤2: 理想溶解度计算
    print(f"\n步骤2: 计算理想溶解度...")
    t0 = time.time()
    ideal_result = calc.calculate_ideal_solubility(
        base_alloy_composition=base_composition,
        solute_element=solute,
        solution_phase=tdb_solution_phase,
        precipitating_phase="",
        temperature=temperature
    )
    t1 = time.time()
    ideal_time = t1 - t0
    print(f"  耗时: {ideal_time:.3f}秒")
    print(f"  状态: {ideal_result.get('status')}")
    print(f"  理想溶解度: {ideal_result.get('solubility_mole_fraction', 0):.6f}")

    # 总结
    total = actual_time + ideal_time
    print(f"\n时间分配:")
    print(f"  实际溶解度: {actual_time:.3f}秒 ({actual_time/total*100:.1f}%)")
    print(f"  理想溶解度: {ideal_time:.3f}秒 ({ideal_time/total*100:.1f}%)")
    print(f"  总计: {total:.3f}秒")

    return actual_time, ideal_time


def identify_bottlenecks():
    """识别性能瓶颈"""
    print("\n" + "="*70)
    print("性能瓶颈诊断")
    print("="*70)

    # 测试单点
    single_time = test_single_temperature_point()

    # 分析步骤
    actual_time, ideal_time = analyze_calculation_steps()

    # 诊断
    print("\n" + "="*70)
    print("瓶颈诊断结果")
    print("="*70)

    print(f"\n单点计算耗时: {single_time:.2f}秒")

    if single_time > 2.0:
        print("\n🔴 诊断：单点计算太慢！")
        print(f"   每个温度点需要 {single_time:.2f}秒")
        print(f"   20个点需要 {single_time*20:.0f}秒（串行）")
        print(f"   即使16核并行，也需要 {single_time*20/16:.0f}秒")

        if actual_time > ideal_time * 2:
            print("\n主要瓶颈：实际溶解度计算")
            print("可能原因：")
            print("  1. 相稳定性检查（_check_alloy_full_stability）频繁调用")
            print("  2. 数值求解器（brentq）迭代次数多")
            print("  3. 每次迭代都要计算所有组分的化学势")
            print("  4. TDB查询没有缓存")
        else:
            print("\n实际溶解度和理想溶解度计算耗时相近")
            print("可能原因：")
            print("  1. TDB数据查询慢")
            print("  2. 化学势计算本身复杂")
    else:
        print("\n🟢 单点计算速度正常")

    # 提出优化建议
    print("\n" + "="*70)
    print("优化建议")
    print("="*70)

    print("\n1. 短期优化（代码层面）：")
    print("   ✓ 缓存 TDB 查询结果（已部分实现）")
    print("   ✓ 减少重复的稳定性检查")
    print("   ✓ 优化求解器参数（减少精度换取速度）")
    print("   ✓ 跳过不必要的理想溶解度计算（如果用户不需要）")

    print("\n2. 中期优化（算法层面）：")
    print("   • 使用更快的初值猜测（减少迭代次数）")
    print("   • 实现增量计算（利用相邻温度点的结果）")
    print("   • 分段计算（跳过明显不溶或完全互溶的区域）")

    print("\n3. 长期优化（架构层面）：")
    print("   • 使用 Cython/Numba 加速核心计算")
    print("   • 预计算常用体系的查找表")
    print("   • 实现 GPU 加速")

    print("="*70)


if __name__ == '__main__':
    print("温度曲线性能诊断工具")
    print("="*70)

    try:
        # 完整诊断流程
        identify_bottlenecks()

        # 测试温度曲线
        serial_time, avg_time = test_temperature_curve()

        print("\n" + "="*70)
        print("总结")
        print("="*70)
        print(f"单点平均耗时: {avg_time:.2f}秒")
        print(f"20点串行总耗时: {serial_time:.2f}秒")
        print(f"16核并行预估: {serial_time/16:.2f}秒")
        print("="*70)

    except Exception as e:
        print(f"\n❌ 诊断过程出错: {e}")
        import traceback
        traceback.print_exc()
