# -*- coding: utf-8 -*-
"""
热力学模型模块 (Thermodynamic Models Module)
============================================
包含UEM-Miedema模型及相关外推模型。

模块结构：
---------
- miedema_model: Miedema模型核心实现
  - 计算混合焓
  - 计算界面能
  - 计算原子体积

- extrapolation_models: 二元系统外推模型
  - UEM1, UEM2, UEM3等模型
  - 溶质-溶剂相互作用计算

- activity_interaction_parameters: 活度相互作用参数
  - Wagner相互作用系数
  - 二阶相互作用参数
"""

from models.miedema_model import MiedemaModel
from models.extrapolation_models import BinaryModel
from models.activity_interaction_parameters import ActivityInteractionParameters

__all__ = [
    'MiedemaModel',
    'BinaryModel',
    'ActivityInteractionParameters',
]
