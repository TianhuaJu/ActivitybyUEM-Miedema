# -*- coding: utf-8 -*-
"""
AlloyAct Pro - 基于UEM-Miedema模型的合金热力学计算软件
========================================================

AlloyAct Pro是一个专业的合金热力学计算软件，基于UEM-Miedema模型框架，
提供溶解度计算、析出温度预测、相平衡分析等功能。

主要功能：
----------
1. 活度计算
   - 单点活度计算
   - 活度随温度/浓度变化

2. 热力学性质
   - 混合焓、混合熵、Gibbs能
   - 相互作用系数

3. 相图与相平衡
   - 二元相图计算
   - 多相平衡计算

4. 溶解度与析出
   - 化合物溶解度积
   - 析出温度计算

模块结构：
----------
- calculations: 核心计算模块
- core: 基础工具和常量
- database: 数据库管理
- gui: 图形界面
- models: 热力学模型
- utils: 辅助工具
- hooks: 构建钩子

版本：1.0.0
作者：AlloyAct Pro Team
"""

__version__ = '1.0.0'
__author__ = 'AlloyAct Pro Team'

# 导出主要模块
from calculations import *
from models import *
from core import *
from database import *
