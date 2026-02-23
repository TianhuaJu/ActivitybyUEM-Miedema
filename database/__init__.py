# -*- coding: utf-8 -*-
"""
数据库模块 (Database Module)
============================
包含数据库管理和化合物热力学数据。

模块结构：
---------
- compound_database: 化合物热力学数据库管理
  - 创建和初始化SQLite数据库
  - 查询化合物热力学数据
  - 查询溶解度积数据
  - 查询格点稳定性和Wagner系数

数据文件：
----------
- data/DataBase.db: 元素参数数据库
- data/compounds.db: 化合物热力学数据库
- data/unary50.tdb: SGTE单元系热力学数据

使用示例：
---------
>>> from database.compound_database import (
...     init_database, get_compound_data, get_solubility_product
... )
"""

# 为避免循环导入，不在此处直接导入
# 用户应直接从子模块导入所需的类/函数

__all__ = [
    'compound_database',
]
