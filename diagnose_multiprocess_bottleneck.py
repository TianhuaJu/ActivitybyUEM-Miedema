#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多进程性能瓶颈诊断脚本

诊断以下几个方面：
1. 进程启动时间
2. TDB文件加载时间
3. 第一次计算时间
4. 后续计算时间
"""

import time
import os
import sys
from concurrent.futures import ProcessPoolExecutor

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_tdb_loading():
    """测试TDB文件加载时间"""
    print("\n" + "="*60)
    print("测试1: TDB文件加载时间")
    print("="*60)

    start = time.time()
    from core.tdb_parser import get_tdb_parser
    tdb = get_tdb_parser()
    elapsed = time.time() - start

    print(f"TDB文件加载耗时: {elapsed:.3f}秒")
    if elapsed > 1.0:
        print("⚠️  TDB加载很慢！这是主要瓶颈")
    else:
        print("✓ TDB加载速度正常")

    return elapsed


def test_calculator_creation():
    """测试计算器创建时间"""
    print("\n" + "="*60)
    print("测试2: 计算器实例创建时间")
    print("="*60)

    start = time.time()
    from calculations.phase_diagram import PhaseDiagramCalculator
    calc = PhaseDiagramCalculator()
    elapsed = time.time() - start

    print(f"计算器创建耗时: {elapsed:.3f}秒")
    if elapsed > 0.5:
        print("⚠️  计算器创建很慢")
    else:
        print("✓ 计算器创建速度正常")

    return elapsed


def test_single_calculation():
    """测试单次计算时间"""
    print("\n" + "="*60)
    print("测试3: 单次溶解度计算时间")
    print("="*60)

    from calculations.phase_diagram import PhaseDiagramCalculator
    from models.extrapolation_models import BinaryModel

    calc = PhaseDiagramCalculator()
    bm = BinaryModel()

    # 测试参数
    base_composition = {'Fe': 0.95, 'Si': 0.05}
    solute = 'C'
    temperature = 1200.0

    start = time.time()
    result = calc.calculate_solubility(
        base_alloy_composition=base_composition,
        solute_element=solute,
        solution_phase='BCC_A2',
        temperature=temperature,
        extrapolation_func=bm.UEM1,
        extrapolation_model_name='UEM1',
        activity_model='Wagner'
    )
    elapsed = time.time() - start

    print(f"单次计算耗时: {elapsed:.3f}秒")
    print(f"计算结果状态: {result.get('status', 'Unknown')}")

    return elapsed


def worker_init_time():
    """子进程初始化时间测试"""
    start = time.time()
    from calculations.parallel_solubility import get_calculator
    calc = get_calculator()
    elapsed = time.time() - start
    return elapsed


def test_multiprocess_startup():
    """测试多进程启动开销"""
    print("\n" + "="*60)
    print("测试4: 多进程启动开销")
    print("="*60)

    n_processes = min(os.cpu_count() or 4, 8)

    start = time.time()
    with ProcessPoolExecutor(max_workers=n_processes) as executor:
        futures = [executor.submit(worker_init_time) for _ in range(n_processes)]
        init_times = [f.result() for f in futures]
    total_elapsed = time.time() - start

    avg_init = sum(init_times) / len(init_times)

    print(f"启动{n_processes}个进程总耗时: {total_elapsed:.3f}秒")
    print(f"平均每个进程初始化: {avg_init:.3f}秒")
    print(f"初始化时间分布: min={min(init_times):.3f}s, max={max(init_times):.3f}s")

    if avg_init > 2.0:
        print("⚠️  进程初始化很慢！每个进程都在重新加载TDB")
        print("   这是多进程性能问题的主要原因！")
        return True  # 有瓶颈
    else:
        print("✓ 进程初始化速度可接受")
        return False


def test_actual_parallel_calculation():
    """测试实际并行计算"""
    print("\n" + "="*60)
    print("测试5: 实际并行计算性能")
    print("="*60)

    from calculations.parallel_solubility import compute_concentration_point

    # 准备10个测试任务
    n_tasks = 10
    task_params = []
    for i in range(n_tasks):
        x_var = 0.05 + i * 0.01
        param_dict = {
            'x_var': float(x_var),
            'index': i,
            'fixed_base_norm': {'Fe': 1.0},
            'variable_comp': 'Si',
            'solute': 'C',
            'tdb_solution_phase': 'BCC_A2',
            'temperature': 1200.0,
            'extrap_model_name': 'UEM1',
            'activity_model': 'Wagner'
        }
        task_params.append(param_dict)

    # 串行测试
    print(f"\n串行执行{n_tasks}个计算...")
    start = time.time()
    serial_results = [compute_concentration_point(p) for p in task_params]
    serial_time = time.time() - start
    print(f"串行耗时: {serial_time:.3f}秒 ({serial_time/n_tasks:.3f}秒/任务)")

    # 并行测试
    n_workers = min(os.cpu_count() or 4, n_tasks)
    print(f"\n并行执行{n_tasks}个计算（{n_workers}个进程）...")
    start = time.time()
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = [executor.submit(compute_concentration_point, p) for p in task_params]
        parallel_results = [f.result() for f in futures]
    parallel_time = time.time() - start
    print(f"并行耗时: {parallel_time:.3f}秒")

    speedup = serial_time / parallel_time
    print(f"\n加速比: {speedup:.2f}x")

    if speedup < 2.0:
        print(f"⚠️  并行加速效果很差！应该有{n_workers}x加速，实际只有{speedup:.2f}x")
        print("   问题：进程启动开销 > 计算收益")
        return False
    else:
        print(f"✓ 并行加速效果良好")
        return True


def main():
    print("="*60)
    print("多进程性能瓶颈诊断")
    print("="*60)
    print(f"CPU核心数: {os.cpu_count()}")
    print(f"Python版本: {sys.version}")

    # 运行所有测试
    tdb_time = test_tdb_loading()
    calc_time = test_calculator_creation()
    single_calc_time = test_single_calculation()
    has_startup_bottleneck = test_multiprocess_startup()
    parallel_ok = test_actual_parallel_calculation()

    # 总结
    print("\n" + "="*60)
    print("诊断总结")
    print("="*60)

    total_overhead = tdb_time + calc_time
    print(f"\n每个进程的启动开销: ~{total_overhead:.3f}秒")
    print(f"单次计算时间: ~{single_calc_time:.3f}秒")
    print(f"开销/计算比: {total_overhead/single_calc_time:.2f}x")

    if total_overhead > single_calc_time * 5:
        print("\n🔴 主要问题：进程启动开销远大于计算时间！")
        print("   每个进程启动需要 {:.1f}秒，但单次计算只需 {:.1f}秒".format(total_overhead, single_calc_time))
        print("\n解决方案：")
        print("   1. 使用进程池初始化器预加载TDB")
        print("   2. 减少进程数量，增加每个进程的任务数")
        print("   3. 考虑使用线程池 + 释放GIL的C扩展")
    elif not parallel_ok:
        print("\n🔴 并行效果不佳")
        print("\n可能原因：")
        print("   1. 任务太少，进程启动开销占主导")
        print("   2. 计算太快，多进程通信开销占主导")
    else:
        print("\n🟢 并行性能良好")

    print("="*60)


if __name__ == '__main__':
    main()
