"""
进程池初始化器
================
预加载模块，避免首次计算延迟
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 全局计算器实例（每个进程一个）
_calculator = None


def init_worker():
    """
    进程池工作进程初始化函数

    在每个工作进程启动时调用一次，预加载必要的模块和数据
    """
    global _calculator

    # 预加载计算模块
    from calculations.phase_diagram import PhaseDiagramCalculator
    from core.tdb_parser import get_tdb_parser

    # 预加载TDB数据（单例模式）
    _ = get_tdb_parser()

    # 创建计算器实例
    _calculator = PhaseDiagramCalculator()

    # print(f"Worker process {os.getpid()} initialized")  # 调试用


def get_worker_calculator():
    """获取当前进程的计算器实例"""
    global _calculator
    if _calculator is None:
        # 如果没有初始化（不应该发生），创建一个
        from calculations.phase_diagram import PhaseDiagramCalculator
        _calculator = PhaseDiagramCalculator()
    return _calculator
