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

使用示例：
---------
>>> from calculations.thermodynamic_properties import ThermodynamicProperties
>>> from calculations.activity_calculator import ActivityCoefficient
>>> from calculations.phase_diagram import PhaseDiagramCalculator
"""

# 注意：为避免循环导入问题，不在此处直接导入所有类
# 用户应直接从子模块导入所需的类/函数

__all__ = [
    'thermodynamic_properties',
    'activity_calculator',
    'phase_diagram',
    'phase_equilibrium_calculator',
    'PhaseEquilibriumCalculator',
    'compound_solubility',
    'solubility_corrected',
    'precipitation_temperature',
    'parallel_solubility',
    'global_process_pool',
    'process_pool_init',
]
