#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并行计算性能诊断脚本

测试当前的多线程实现是否真的在并行执行
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import os


def cpu_intensive_task(n, task_id):
    """CPU密集型任务模拟"""
    thread_id = threading.get_ident()
    print(f"任务 {task_id} 开始 (线程ID: {thread_id})")

    # 模拟计算
    result = 0
    for i in range(n):
        result += i ** 2

    print(f"任务 {task_id} 完成")
    return result


def test_threading():
    """测试ThreadPoolExecutor"""
    print("\n" + "="*60)
    print("测试 ThreadPoolExecutor (多线程)")
    print("="*60)

    n_tasks = 8
    n_iterations = 10000000

    start = time.time()
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(cpu_intensive_task, n_iterations, i) for i in range(n_tasks)]
        results = [f.result() for f in futures]
    elapsed = time.time() - start

    print(f"\n完成 {n_tasks} 个任务")
    print(f"总耗时: {elapsed:.2f}秒")
    print(f"平均每任务: {elapsed/n_tasks:.2f}秒")

    return elapsed


def test_sequential():
    """测试串行执行"""
    print("\n" + "="*60)
    print("测试串行执行 (单线程)")
    print("="*60)

    n_tasks = 8
    n_iterations = 10000000

    start = time.time()
    results = [cpu_intensive_task(n_iterations, i) for i in range(n_tasks)]
    elapsed = time.time() - start

    print(f"\n完成 {n_tasks} 个任务")
    print(f"总耗时: {elapsed:.2f}秒")
    print(f"平均每任务: {elapsed/n_tasks:.2f}秒")

    return elapsed


def test_multiprocessing():
    """测试ProcessPoolExecutor"""
    print("\n" + "="*60)
    print("测试 ProcessPoolExecutor (多进程)")
    print("="*60)

    n_tasks = 8
    n_iterations = 10000000

    # 重新定义任务函数（简化版，避免print在子进程中的问题）
    def task(n):
        result = 0
        for i in range(n):
            result += i ** 2
        return result

    start = time.time()
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(task, n_iterations) for i in range(n_tasks)]
        results = [f.result() for f in futures]
    elapsed = time.time() - start

    print(f"\n完成 {n_tasks} 个任务")
    print(f"总耗时: {elapsed:.2f}秒")
    print(f"平均每任务: {elapsed/n_tasks:.2f}秒")

    return elapsed


def main():
    print("="*60)
    print("Python 并行计算性能诊断")
    print(f"CPU 核心数: {os.cpu_count()}")
    print("="*60)

    # 测试串行
    time_sequential = test_sequential()

    # 测试多线程
    time_threading = test_threading()

    # 测试多进程
    time_multiprocessing = test_multiprocessing()

    # 总结
    print("\n" + "="*60)
    print("性能对比总结")
    print("="*60)
    print(f"串行执行:        {time_sequential:.2f}秒  (基准)")
    print(f"多线程并行:      {time_threading:.2f}秒  (加速比: {time_sequential/time_threading:.2f}x)")
    print(f"多进程并行:      {time_multiprocessing:.2f}秒  (加速比: {time_sequential/time_multiprocessing:.2f}x)")

    print("\n结论:")
    if time_threading / time_sequential > 0.8:
        print("⚠️  多线程几乎没有加速效果！")
        print("    原因: Python的GIL（全局解释器锁）限制了线程并行")
        print("    建议: 对于CPU密集型任务，应使用多进程(ProcessPoolExecutor)")
    else:
        print("✓ 多线程有明显加速效果")

    if time_multiprocessing / time_sequential < 0.3:
        print(f"✓ 多进程加速显著! 提升了 {time_sequential/time_multiprocessing:.1f}倍")

    print("="*60)


if __name__ == '__main__':
    main()
