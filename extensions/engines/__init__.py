# -*- coding: utf-8 -*-
"""
DFT/MD 计算引擎抽象层
======================
每种 DFT 软件实现一个 DFTEngine 子类，统一输入生成和输出解析接口。
DFTAdapter 通过引擎名称动态调度到对应实现。
"""

from extensions.engines.dft_engine import DFTEngine, DFTTaskType, EngineCapability

__all__ = ["DFTEngine", "DFTTaskType", "EngineCapability"]
