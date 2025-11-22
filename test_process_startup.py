#!/usr/bin/env python3
"""快速测试多进程启动和任务执行"""

import time
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def simple_worker(task_id):
    """简单的工作函数 - 测试进程启动"""
    import time
    start = time.time()

    # 模拟导入计算模块
    try:
        from calculations.parallel_solubility import get_calculator
        calc = get_calculator()
        init_time = time.time() - start

        # 模拟一次简单计算
        result = task_id ** 2
        total_time = time.time() - start

        return {
            'task_id': task_id,
            'init_time': init_time,
            'total_time': total_time,
            'result': result
        }
    except Exception as e:
        return {
            'task_id': task_id,
            'error': str(e),
            'init_time': time.time() - start
        }


def test_progress_updates():
    """测试进度更新是否及时"""
    print("="*60)
    print("测试：进度更新及时性")
    print("="*60)

    n_tasks = 20
    n_workers = min(os.cpu_count() or 4, 8)

    print(f"提交 {n_tasks} 个任务，使用 {n_workers} 个进程...")
    print("观察进度更新...")
    print()

    start_time = time.time()
    completed = 0

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        # 提交任务
        submit_start = time.time()
        futures = {executor.submit(simple_worker, i): i for i in range(n_tasks)}
        submit_time = time.time() - submit_start
        print(f"✓ 提交所有任务耗时: {submit_time:.3f}秒")
        print()

        # 处理完成的任务
        first_result_time = None
        init_times = []

        for future in as_completed(futures):
            if first_result_time is None:
                first_result_time = time.time() - start_time
                print(f"⏱️  第一个任务完成时间: {first_result_time:.3f}秒")
                if first_result_time > 3.0:
                    print("   ⚠️  第一个任务太慢了！")
                print()

            try:
                result = future.result()
                if 'init_time' in result:
                    init_times.append(result['init_time'])

                completed += 1
                elapsed = time.time() - start_time
                print(f"  [{completed:2d}/{n_tasks}] 完成 (耗时: {elapsed:.2f}秒)", end='\r')

            except Exception as e:
                print(f"\n任务失败: {e}")

        print()  # 换行

    total_time = time.time() - start_time

    print()
    print("="*60)
    print("结果分析")
    print("="*60)
    print(f"总耗时: {total_time:.3f}秒")
    print(f"第一个结果: {first_result_time:.3f}秒")
    print(f"平均每任务: {total_time/n_tasks:.3f}秒")

    if init_times:
        avg_init = sum(init_times) / len(init_times)
        print(f"\n进程初始化时间:")
        print(f"  平均: {avg_init:.3f}秒")
        print(f"  最小: {min(init_times):.3f}秒")
        print(f"  最大: {max(init_times):.3f}秒")

        if avg_init > 2.0:
            print("\n🔴 问题发现：进程初始化太慢！")
            print(f"   每个进程需要 {avg_init:.1f}秒 来加载模块")
        elif first_result_time > 5.0:
            print("\n🔴 问题发现：第一批任务启动太慢！")
            print(f"   用户等待 {first_result_time:.1f}秒 才看到第一个进度更新")
        else:
            print("\n🟢 进程启动速度正常")

    return first_result_time, total_time


def test_actual_calculation():
    """测试实际的溶解度计算"""
    print("\n" + "="*60)
    print("测试：实际溶解度计算性能")
    print("="*60)

    from calculations.parallel_solubility import compute_concentration_point

    # 单个任务
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

    print("执行单次计算...")
    start = time.time()
    result = compute_concentration_point(params)
    elapsed = time.time() - start

    print(f"✓ 单次计算耗时: {elapsed:.3f}秒")
    print(f"  状态: {result[3].get('status', 'unknown') if len(result) > 3 else 'error'}")

    # 多任务并行
    n_tasks = 10
    n_workers = 4
    task_list = []
    for i in range(n_tasks):
        p = params.copy()
        p['x_var'] = 0.01 + i * 0.01
        p['index'] = i
        task_list.append(p)

    print(f"\n执行 {n_tasks} 个并行计算（{n_workers}个进程）...")
    start = time.time()

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = [executor.submit(compute_concentration_point, p) for p in task_list]
        results = [f.result() for f in as_completed(futures)]

    parallel_time = time.time() - start
    print(f"✓ 并行耗时: {parallel_time:.3f}秒")
    print(f"  平均每任务: {parallel_time/n_tasks:.3f}秒")

    expected_speedup = min(n_workers, n_tasks)
    if parallel_time > elapsed * n_tasks / expected_speedup * 2:
        print(f"\n⚠️  并行效率低下！")
        print(f"   预期耗时: ~{elapsed * n_tasks / expected_speedup:.2f}秒")
        print(f"   实际耗时: {parallel_time:.2f}秒")
        print(f"   开销占比: {(parallel_time - elapsed * n_tasks / expected_speedup) / parallel_time * 100:.1f}%")


if __name__ == '__main__':
    print("多进程性能诊断 - 快速版")
    print(f"CPU核心数: {os.cpu_count()}")
    print()

    # 测试1: 进度更新
    first_time, total_time = test_progress_updates()

    # 测试2: 实际计算
    try:
        test_actual_calculation()
    except Exception as e:
        print(f"\n实际计算测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("诊断完成")
    print("="*60)
