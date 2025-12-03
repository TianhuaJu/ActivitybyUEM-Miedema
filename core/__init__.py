# -*- coding: utf-8 -*-
"""
核心模块 (Core Module)
======================
包含基础工具类、常量定义和数据处理模块。

模块结构：
---------
- constants: 物理常量和元素数据 (Constants类)
- element: 元素类定义 (Element类)
- database_handler: 数据库访问处理
- tdb_parser: TDB热力学数据库文件解析 (TDBParser类)
- utils: 通用工具函数

使用示例：
---------
>>> from core.constants import Constants
>>> from core.element import Element
>>> from core.tdb_parser import TDBParser
"""

# 为避免循环导入，不在此处直接导入
# 用户应直接从子模块导入所需的类/函数

__all__ = [
    'constants',
    'element',
    'database_handler',
    'tdb_parser',
    'utils',
]
