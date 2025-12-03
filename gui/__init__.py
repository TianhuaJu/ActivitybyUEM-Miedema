# -*- coding: utf-8 -*-
"""
图形界面模块 (GUI Module)
=========================
包含所有PyQt5图形界面组件。

主窗口：
--------
- Alloyact_GUI_Pro: 主应用程序窗口
- alloyact_gui: 传统版GUI（已弃用）

功能组件：
----------
活度计算：
- ActivityCalculationWidget: 单点活度计算
- ActivityVaryTemperatureWidget: 活度随温度变化
- ActivityVaryConcentrationWidget: 活度随浓度变化
- ActivityVaryConcentrationWidget2: 合金添加模拟

热力学性质：
- ThermodynamicPropertiesWidget: 热力学性质计算
- InteractionCoefficientWidget: 相互作用系数
- SecondOrderCoefficientWidget: 二阶相互作用系数

相图与相平衡：
- PhaseDiagramWidget: 相图计算
- PhaseEquilibriumWidget: 多相平衡计算

溶解度与析出：
- SolubilityWidget: 溶解度计算
- PrecipitationTemperatureWidget: 析出温度计算

工具：
- UnitConversionWidget: 单位转换
- data_ui: 数据库管理界面
"""

# 主窗口
from gui.Alloyact_GUI_Pro import AlloyActProGUI

# 活度计算组件
from gui.ActivityCalculationWidget import ActivityCalculationWidget
from gui.ActivityVaryTemperatureWidget import ActivityTemperatureVariationWidget
from gui.ActivityVaryConcentrationWidget import CompositionVariationWidget
from gui.ActivityVaryConcentrationWidget2 import AlloyAdditionWidget

# 热力学性质组件
from gui.ThermodynamicPropertiesWidget import ThermodynamicPropertiesWidget
from gui.InteractionCoefficientWidget import InteractionCoefficientWidget
from gui.SecondOrderCoefficientWidget import SecondOrderCoefficientWidget

# 相图与相平衡组件
from gui.PhaseDiagramWidget import PhaseDiagramWidget
from gui.PhaseEquilibriumWidget import PhaseEquilibriumWidget

# 溶解度与析出组件
from gui.SolubilityWidget import SolubilityWidget
from gui.PrecipitationTemperatureWidget import PrecipitationTemperatureWidget

# 工具组件
from gui.UnitConversionWidget import UnitConversionWidget
from gui.data_ui import DatabaseManagerTab

__all__ = [
    # 主窗口
    'AlloyActProGUI',

    # 活度计算
    'ActivityCalculationWidget',
    'ActivityTemperatureVariationWidget',
    'CompositionVariationWidget',
    'AlloyAdditionWidget',

    # 热力学性质
    'ThermodynamicPropertiesWidget',
    'InteractionCoefficientWidget',
    'SecondOrderCoefficientWidget',

    # 相图与相平衡
    'PhaseDiagramWidget',
    'PhaseEquilibriumWidget',

    # 溶解度与析出
    'SolubilityWidget',
    'PrecipitationTemperatureWidget',

    # 工具
    'UnitConversionWidget',
    'DatabaseManagerTab',
]
