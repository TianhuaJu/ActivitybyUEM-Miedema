# -*- coding: utf-8 -*-
"""
核心模块 (Core Module)
======================
包含基础工具类、常量定义和数据处理模块。

模块结构：
---------
- constants: 物理常量和元素数据
- element: 元素类定义
- database_handler: 数据库访问处理
- tdb_parser: TDB热力学数据库文件解析
- utils: 通用工具函数
"""

from core.constants import PHYSICAL_CONSTANTS, ELEMENT_DATA
from core.element import Element
from core.database_handler import DatabaseHandler
from core.tdb_parser import TDBParser
from core.utils import *

__all__ = [
    'PHYSICAL_CONSTANTS',
    'ELEMENT_DATA',
    'Element',
    'DatabaseHandler',
    'TDBParser',
]
