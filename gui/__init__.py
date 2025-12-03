# -*- coding: utf-8 -*-
"""
图形界面模块 (GUI Module)
=========================
包含所有PyQt5图形界面组件。

主窗口：
--------
- Alloyact_GUI_Pro: 主应用程序窗口 (AlloyThermolCalProGUI类)

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

使用示例：
---------
>>> from gui.Alloyact_GUI_Pro import AlloyThermolCalProGUI
>>> from gui.SolubilityWidget import SolubilityWidget
"""

# 为避免循环导入，不在此处直接导入
# 用户应直接从子模块导入所需的类/函数

__all__ = [
    'Alloyact_GUI_Pro',
    'ActivityCalculationWidget',
    'ActivityVaryTemperatureWidget',
    'ActivityVaryConcentrationWidget',
    'ActivityVaryConcentrationWidget2',
    'ThermodynamicPropertiesWidget',
    'InteractionCoefficientWidget',
    'SecondOrderCoefficientWidget',
    'PhaseDiagramWidget',
    'PhaseEquilibriumWidget',
    'SolubilityWidget',
    'PrecipitationTemperatureWidget',
    'UnitConversionWidget',
    'data_ui',
]
