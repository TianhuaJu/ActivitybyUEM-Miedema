#!/usr/bin/env python3
"""
深度性能分析 - 找出真正的瓶颈
"""

import time
import os
import sys
import cProfile
import pstats
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def profile_single_calculation():
    """分析单次计算的性能瓶颈"""
    print("="*60)
    print("分析单次溶解度计算")
    print("="*60)

    from calculations.parallel_solubility import compute_concentration_point

    params = {
        'x_var': 0.05,
        'index': 0,
        'fixed_base_norm': {'Fe': 1.0},
        'variable_comp': 'Si',
        'solute': 'C',
        'tdb_solution_phase': 'BCC_A2',
        'temperature': 1200.0,
        'extrap_model_name': 'UEM1',
        'activity_model': 'Wagner'
    }

    # 性能分析
    profiler = cProfile.Profile()
    profiler.enable()

    result = compute_concentration_point(params)

    profiler.disable()

    # 输出结果
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # 显示前20个最慢的函数

    print(s.getvalue())
    print(f"\n结果: {result[3].get('status', 'unknown')}")


def time_breakdown_test():
    """分解时间消耗：初始化 vs 计算"""
    print("\n" + "="*60)
    print("时间分解测试")
    print("="*60)

    # 测试1: 导入模块时间
    print("\n1. 导入模块...")
    start = time.time()
    from calculations.parallel_solubility import compute_concentration_point, get_calculator
    import_time = time.time() - start
    print(f"   导入耗时: {import_time:.3f}秒")

    # 测试2: 获取计算器时间
    print("\n2. 获取计算器实例...")
    start = time.time()
    calc = get_calculator()
    calc_init_time = time.time() - start
    print(f"   计算器初始化: {calc_init_time:.3f}秒")

    # 测试3: 第一次计算
    print("\n3. 第一次计算...")
    params = {
        'x_var': 0.05,
        'index': 0,
        'fixed_base_norm': {'Fe': 1.0},
        'variable_comp': 'Si',
        'solute': 'C',
        'tdb_solution_phase': 'BCC_A2',
        'temperature': 1200.0,
        'extrap_model_name': 'UEM1',
        'activity_model': 'Wagner'
    }

    start = time.time()
    result1 = compute_concentration_point(params)
    first_calc_time = time.time() - start
    print(f"   第一次计算: {first_calc_time:.3f}秒")

    # 测试4: 第二次计算（缓存后）
    print("\n4. 第二次计算（相同参数）...")
    params2 = params.copy()
    params2['x_var'] = 0.06
    params2['index'] = 1

    start = time.time()
    result2 = compute_concentration_point(params2)
    second_calc_time = time.time() - start
    print(f"   第二次计算: {second_calc_time:.3f}秒")

    # 总结
    print("\n" + "="*60)
    print("时间分解总结")
    print("="*60)
    print(f"导入模块:       {import_time:.3f}秒")
    print(f"初始化计算器:   {calc_init_time:.3f}秒")
    print(f"第一次计算:     {first_calc_time:.3f}秒")
    print(f"第二次计算:     {second_calc_time:.3f}秒")
    print(f"计算加速比:     {first_calc_time/second_calc_time:.2f}x")

    if calc_init_time > 1.0:
        print("\n⚠️  计算器初始化很慢！")
    if first_calc_time > 2.0:
        print("⚠️  单次计算很慢！")
    if first_calc_time / second_calc_time > 2.0:
        print("⚠️  首次计算有显著预热开销！")

    return {
        'import': import_time,
        'init': calc_init_time,
        'first': first_calc_time,
        'second': second_calc_time
    }


def test_actual_multiprocess():
    """测试实际的多进程性能"""
    print("\n" + "="*60)
    print("实际多进程测试")
    print("="*60)

    from concurrent.futures import ProcessPoolExecutor
    from calculations.parallel_solubility import compute_concentration_point
    from calculations.process_pool_init import init_worker

    # 准备任务
    n_tasks = 20
    tasks = []
    for i in range(n_tasks):
        tasks.append({
            'x_var': 0.01 + i * 0.01,
            'index': i,
            'fixed_base_norm': {'Fe': 1.0},
            'variable_comp': 'Si',
            'solute': 'C',
            'tdb_solution_phase': 'BCC_A2',
            'temperature': 1200.0,
            'extrap_model_name': 'UEM1',
            'activity_model': 'Wagner'
        })

    # 测试：4个进程
    print(f"\n使用4个进程处理{n_tasks}个任务...")
    start = time.time()

    with ProcessPoolExecutor(max_workers=4, initializer=init_worker) as executor:
        futures = [executor.submit(compute_concentration_point, t) for t in tasks]
        results = [f.result() for f in futures]

    time_4workers = time.time() - start
    print(f"耗时: {time_4workers:.2f}秒")
    print(f"平均每任务: {time_4workers/n_tasks:.2f}秒")

    # 测试：串行
    print(f"\n串行处理{n_tasks}个任务...")
    start = time.time()
    results_serial = [compute_concentration_point(t) for t in tasks]
    time_serial = time.time() - start
    print(f"耗时: {time_serial:.2f}秒")
    print(f"平均每任务: {time_serial/n_tasks:.2f}秒")

    # 对比
    speedup = time_serial / time_4workers
    print(f"\n加速比: {speedup:.2f}x")

    if speedup < 2.0:
        print("⚠️  多进程加速不明显！")
        print(f"   理想加速应该是4x，实际只有{speedup:.2f}x")
        overhead = time_4workers - time_serial / 4
        print(f"   进程开销: {overhead:.2f}秒 ({overhead/time_4workers*100:.1f}%)")

    return time_4workers, time_serial, speedup


if __name__ == '__main__':
    print("深度性能分析")
    print("="*60)
    print(f"CPU核心: {os.cpu_count()}")
    print()

    # 1. 时间分解
    breakdown = time_breakdown_test()

    # 2. 性能分析
    # profile_single_calculation()

    # 3. 多进程测试
    mp_time, serial_time, speedup = test_actual_multiprocess()

    # 总结
    print("\n" + "="*60)
    print("性能瓶颈诊断")
    print("="*60)

    single_calc = breakdown['second']  # 使用第二次计算时间（已预热）

    print(f"\n单次计算时间: {single_calc:.2f}秒")
    print(f"20任务串行: {serial_time:.2f}秒")
    print(f"20任务并行(4进程): {mp_time:.2f}秒")
    print(f"加速比: {speedup:.2f}x")

    if single_calc > 1.0:
        print("\n🔴 核心问题：单次计算太慢！")
        print(f"   每个点需要{single_calc:.2f}秒")
        print(f"   100个点需要{single_calc*100:.0f}秒（串行）")
        print("\n   即使完美并行（16核），也需要{:.0f}秒".format(single_calc*100/16))
        print("\n建议：")
        print("   1. 优化底层计算算法")
        print("   2. 使用C/Cython扩展加速")
        print("   3. 减少TDB查询次数")
    elif speedup < 2.5:
        print("\n🔴 核心问题：多进程开销太大！")
        print("   进程通信和启动开销占主导")
    else:
        print("\n🟢 性能正常")

    print("="*60)
