# -*- coding: utf-8 -*-
"""
PyInstaller hook for matplotlib - 启动优化版

减少matplotlib导入时间的运行时钩子
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 只收集必要的matplotlib数据文件
datas = []

# 只导入需要的后端
hiddenimports = [
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_agg',
]

# 排除不需要的后端以减小体积
excludedimports = [
    'matplotlib.backends.backend_gtk3agg',
    'matplotlib.backends.backend_gtk3cairo',
    'matplotlib.backends.backend_gtk4agg',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_wx',
    'matplotlib.backends.backend_wxagg',
    'matplotlib.backends.backend_webagg',
    'matplotlib.tests',
]
