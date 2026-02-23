# -*- coding: utf-8 -*-
"""
热力学模型模块 (Thermodynamic Models Module)
============================================
包含UEM-Miedema模型及相关外推模型。

模块结构：
---------
- miedema_model: Miedema模型核心实现 (MiedemaModel类)
  - 计算混合焓
  - 计算界面能
  - 计算原子体积

- extrapolation_models: 二元系统外推模型 (BinaryModel类)
  - UEM1, UEM2, UEM3等模型
  - 溶质-溶剂相互作用计算

- activity_interaction_parameters: 多元系统溶液模型 (multicomponentSolution类)

使用示例：
---------
>>> from models.miedema_model import MiedemaModel
>>> from models.extrapolation_models import BinaryModel
"""

# 为避免循环导入，不在此处直接导入
# 用户应直接从子模块导入所需的类/函数

__all__ = [
    'miedema_model',
    'extrapolation_models',
    'activity_interaction_parameters',
]
