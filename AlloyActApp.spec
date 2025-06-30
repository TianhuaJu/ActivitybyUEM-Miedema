# AlloyActApp.spec - 文件夹发行版 (one-dir mode)
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# --- 数据文件 ---
# 此部分定义了需要打包到最终发行文件夹中的所有非代码文件。
# 路径格式为 ('源文件路径', '在目标文件夹中的相对路径')。
datas = [
    ('database/data/DataBase.db', 'database/data'),
    ('resources', 'resources'),
]
# PyInstaller 的钩子会自动收集 matplotlib 和 pandas 所需的数据文件。
datas += collect_data_files('matplotlib')
datas += collect_data_files('pandas')


# --- 分析 (Analysis) ---
# PyInstaller 在此阶段分析您的主脚本 (Main.py)，找出所有依赖的模块和库。
# 这部分对于单文件和文件夹模式通常是相同的。
a = Analysis(
    ['Main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'sqlite3',
        'numpy',
        'pandas',
        'matplotlib',
        'openpyxl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --- PYZ (Python Archive) ---
# 将所有纯 Python 模块打包成一个 .pyz 的压缩文件。
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- EXE ---
# 创建可执行文件本身。
# 在文件夹模式下，EXE 对象应该保持“干净”，它主要包含启动逻辑和你的脚本。
# 二进制文件(binaries)和数据文件(datas)的引用在这里留空，因为它们将由下面的 COLLECT 块处理。
exe = EXE(
    pyz,
    a.scripts,
    [],  # 在文件夹模式下，二进制文件由 COLLECT 处理
    [],  # 在文件夹模式下，数据文件由 COLLECT 处理
    name='AlloyActApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # 可以设置为 True 以压缩可执行文件和DLL，减小体积
    upx_exclude=[],
    console=False,      # GUI 程序设置为 False，这样运行时不会弹出黑色命令行窗口
    onefile=False,      # 关键指令：False 表示生成文件夹模式
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/AlloyActApp.ico'
)

# --- COLLECT ---
# 这是文件夹模式的核心构建块。
# 它负责将可执行文件(exe)、所有二进制依赖项(a.binaries)、
# Python 模块压缩包(a.zipfiles)和数据文件(a.datas)
# 全部收集到 dist/AlloyActApp 这个输出文件夹中。
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True, # 同样可以对收集的二进制文件进行压缩
    upx_exclude=[],
    name='AlloyActApp'
)