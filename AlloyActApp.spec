# AlloyActApp_onefile.spec - 单文件发行版
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# --- 数据文件 ---
# 这部分与文件夹版本完全相同，确保所有资源被包含
datas = [
    ('database/data/DataBase.db', 'database/data'),
    ('resources', 'resources'),
]
datas += collect_data_files('matplotlib')
datas += collect_data_files('pandas')


# --- 分析 ---
# 这部分也与文件夹版本完全相同
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

# --- PYZ ---
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- EXE (关键改动) ---
# 将所有依赖项和数据都包含进 EXE 文件中，并启用 onefile 模式
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,      # 将二进制文件包含进来
    a.datas,         # 将数据文件也包含进来
    name='AlloyActApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    onefile=True,    # 关键指令：打包成单文件
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/app_ico_Alloyact_Pro.ico'
)

# 在单文件模式下，不需要 COLLECT 块，所以将其整个移除。