"""
全局进程池管理器
================
单例模式的ProcessPoolExecutor，避免重复创建进程

关键优势：
1. 进程只创建一次，复用于所有计算
2. 避免每次计算的进程启动开销
3. 线程安全，支持并发使用
"""

import os
import atexit
from concurrent.futures import ProcessPoolExecutor
from calculations.process_pool_init import init_worker


class GlobalProcessPool:
    """全局进程池单例"""

    _instance = None
    _executor = None
    _lock = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        import threading
        self._lock = threading.Lock()
        self._initialized = True
        self._create_pool()

    def _create_pool(self):
        """创建进程池"""
        if self._executor is not None:
            return

        # 使用CPU核心数，但限制最大进程数避免资源耗尽
        cpu_count = os.cpu_count() or 4
        max_workers = min(cpu_count, 16)  # 最多16个进程

        print(f"🚀 创建全局进程池：{max_workers}个工作进程")

        self._executor = ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=init_worker  # 进程启动时预热
        )

        # 注册退出时清理
        atexit.register(self.shutdown)

    def get_executor(self):
        """获取进程池executor"""
        with self._lock:
            if self._executor is None:
                self._create_pool()
            return self._executor

    def shutdown(self):
        """关闭进程池"""
        with self._lock:
            if self._executor is not None:
                print("🛑 关闭全局进程池")
                self._executor.shutdown(wait=True)
                self._executor = None

    def submit(self, fn, *args, **kwargs):
        """提交任务到进程池"""
        return self.get_executor().submit(fn, *args, **kwargs)


# 全局单例实例
_global_pool = None


def get_global_process_pool():
    """获取全局进程池单例"""
    global _global_pool
    if _global_pool is None:
        _global_pool = GlobalProcessPool()
    return _global_pool


def submit_task(fn, *args, **kwargs):
    """便捷函数：提交任务到全局进程池"""
    return get_global_process_pool().submit(fn, *args, **kwargs)


def shutdown_global_pool():
    """关闭全局进程池"""
    global _global_pool
    if _global_pool is not None:
        _global_pool.shutdown()
        _global_pool = None
