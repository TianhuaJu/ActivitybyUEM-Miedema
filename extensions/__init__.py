# -*- coding: utf-8 -*-
"""
Extensions - 可扩展计算插件系统
================================
提供统一的插件接口，支持 DFT、分子动力学、CALPHAD、机器学习势等
第三方计算引擎的即插即用集成。

用法:
    from extensions import PluginRegistry, CalculationPlugin

    registry = PluginRegistry()
    registry.discover()  # 自动扫描并加载插件
"""

from extensions.base import (
    CalculationPlugin,
    PluginMetadata,
    PluginType,
    ToolSchema,
)
from extensions.registry import PluginRegistry
from extensions.async_task import AsyncTaskQueue, TaskStatus, TaskInfo

__all__ = [
    "CalculationPlugin",
    "PluginMetadata",
    "PluginType",
    "ToolSchema",
    "PluginRegistry",
    "AsyncTaskQueue",
    "TaskStatus",
    "TaskInfo",
]
