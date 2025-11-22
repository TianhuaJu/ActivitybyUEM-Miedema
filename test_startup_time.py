#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动时间测试脚本

用于对比不同打包配置的启动性能
"""

import time
import subprocess
import sys
import os
from pathlib import Path

def measure_startup_time(exe_path, runs=3):
    """
    测量可执行文件的启动时间

    Args:
        exe_path: 可执行文件路径
        runs: 测试次数

    Returns:
        平均启动时间（秒）
    """
    if not os.path.exists(exe_path):
        print(f"错误: 找不到文件 {exe_path}")
        return None

    times = []
    for i in range(runs):
        print(f"  第 {i+1}/{runs} 次测试...", end='', flush=True)

        start = time.time()
        try:
            # 启动程序并立即关闭
            proc = subprocess.Popen(
                [exe_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # 等待一小段时间让程序完全启动
            time.sleep(2)
            proc.terminate()
            proc.wait(timeout=5)
        except Exception as e:
            print(f" 失败: {e}")
            continue

        elapsed = time.time() - start
        times.append(elapsed)
        print(f" {elapsed:.2f}秒")

    if not times:
        return None

    avg_time = sum(times) / len(times)
    return avg_time


def main():
    """主函数"""
    print("=" * 60)
    print("AlloyActApp 启动时间性能测试")
    print("=" * 60)
    print()

    # 检测可用的构建版本
    builds = {
        "优化版 (Optimized)": "dist/AlloyActApp/AlloyActApp",
        "原版 (Standard)": "dist_old/AlloyActApp/AlloyActApp",
    }

    # Windows 下使用 .exe 扩展名
    if sys.platform == 'win32':
        builds = {k: v + '.exe' for k, v in builds.items()}

    results = {}

    for name, path in builds.items():
        print(f"\n测试 {name}:")
        print(f"路径: {path}")

        if not os.path.exists(path):
            print("  ⚠️  未找到，跳过")
            continue

        avg_time = measure_startup_time(path, runs=3)
        if avg_time:
            results[name] = avg_time
            print(f"  ✓ 平均启动时间: {avg_time:.2f}秒")

    # 显示对比结果
    if len(results) > 1:
        print("\n" + "=" * 60)
        print("性能对比结果")
        print("=" * 60)

        sorted_results = sorted(results.items(), key=lambda x: x[1])
        fastest_name, fastest_time = sorted_results[0]

        print(f"\n🏆 最快: {fastest_name} - {fastest_time:.2f}秒\n")

        for name, time_val in sorted_results:
            if name == fastest_name:
                improvement = "基准"
            else:
                improvement = f"慢 {(time_val/fastest_time - 1)*100:.1f}%"

            print(f"  {name:<25} {time_val:>6.2f}秒  [{improvement}]")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试已取消")
        sys.exit(0)
