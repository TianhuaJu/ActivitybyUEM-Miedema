"""
运行时优化钩子 - 在程序启动时执行

优化策略：
1. 设置matplotlib使用Agg后端（更快）
2. 禁用不必要的警告
3. 预加载关键模块
"""

import os
import sys
import warnings

# ============================================
# 1. 设置环境变量 - 在导入模块前配置
# ============================================

# matplotlib后端优化（使用Qt5Agg，在导入matplotlib前设置）
os.environ['MPLBACKEND'] = 'Qt5Agg'

# 禁用matplotlib的字体缓存重建（加快启动）
os.environ['MPLCONFIGDIR'] = os.path.join(sys._MEIPASS if hasattr(sys, '_MEIPASS') else '.', 'mpl_cache')

# NumPy线程数优化（避免过度线程创建）
os.environ['OMP_NUM_THREADS'] = str(min(os.cpu_count() or 4, 8))
os.environ['MKL_NUM_THREADS'] = str(min(os.cpu_count() or 4, 8))
os.environ['NUMEXPR_NUM_THREADS'] = str(min(os.cpu_count() or 4, 8))

# ============================================
# 2. 禁用不必要的警告
# ============================================
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*Matplotlib.*')

# ============================================
# 3. 设置matplotlib优化参数
# ============================================
try:
    import matplotlib
    # 使用Agg后端（在PyQt5之前设置）
    matplotlib.use('Qt5Agg', force=False)

    # 关闭交互模式（加快启动）
    matplotlib.interactive(False)

    # 优化rcParams
    matplotlib.rcParams['figure.max_open_warning'] = 0
    matplotlib.rcParams['agg.path.chunksize'] = 10000

except ImportError:
    pass

# ============================================
# 4. PyQt5优化
# ============================================
try:
    from PyQt5.QtCore import QCoreApplication
    # 设置组织和应用名称（优化设置存储）
    QCoreApplication.setOrganizationName("AlloyActApp")
    QCoreApplication.setApplicationName("AlloyActApp")
except ImportError:
    pass

print("Runtime optimization loaded successfully.")
