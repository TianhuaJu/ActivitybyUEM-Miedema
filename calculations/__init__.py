# -*- coding: utf-8 -*-
"""
计算模块 (Calculations Module)
==============================
包含所有热力学计算相关的功能模块。

模块结构：
---------
- thermodynamic_properties: 热力学性质基础计算
- activity_calculator: 活度系数计算
- phase_diagram: 相图计算
- phase_equilibrium_calculator: 相平衡计算
- PhaseEquilibriumCalculator: 化合物优先剥离版相平衡计算
- compound_solubility: 化合物溶解度积计算
- solubility_corrected: 修正版溶解度计算
- precipitation_temperature: 析出温度计算
- parallel_solubility: 并行溶解度计算
- global_process_pool: 全局进程池管理
- process_pool_init: 进程池初始化
"""

# 核心计算模块
from calculations.thermodynamic_properties import ThermodynamicProperties
from calculations.activity_calculator import ActivityCoefficient
from calculations.phase_diagram import PhaseDiagramCalculator

# 相平衡计算
from calculations.phase_equilibrium_calculator import PhaseEquilibriumCalculator

# 溶解度和析出计算
from calculations.compound_solubility import (
    CompoundSolubilityCalculator,
    CompoundData,
    COMPOUND_DATABASE,
    load_compounds_from_database,
    get_solubility_product_from_database
)
from calculations.precipitation_temperature import PrecipitationTemperatureCalculator

# 并行计算工具
from calculations.parallel_solubility import ParallelSolubilityCalculator
from calculations.global_process_pool import get_process_pool, shutdown_process_pool

__all__ = [
    # 核心类
    'ThermodynamicProperties',
    'ActivityCoefficient',
    'PhaseDiagramCalculator',
    'PhaseEquilibriumCalculator',

    # 溶解度和析出
    'CompoundSolubilityCalculator',
    'CompoundData',
    'COMPOUND_DATABASE',
    'load_compounds_from_database',
    'get_solubility_product_from_database',
    'PrecipitationTemperatureCalculator',

    # 并行计算
    'ParallelSolubilityCalculator',
    'get_process_pool',
    'shutdown_process_pool',
]
