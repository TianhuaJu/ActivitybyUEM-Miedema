# AlloyActApp.spec - 完整稳定版
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

datas = [
    ('database/data/DataBase.db', 'database/data'),
    ('resources', 'resources'),
]

a = Analysis(
    ['Main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Qt
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',

        # 数据库和文件
        'sqlite3',
        'openpyxl',

        # pkg_resources 依赖链（完整版）
        'pkg_resources',
        'pkg_resources.py2_warn',
        'pkg_resources.markers',
        'jaraco.text',
        'jaraco.functools',
        'jaraco.context',
        'more_itertools',
        'importlib_metadata',
        'zipp',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        '_tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    [],
    name='AlloyActApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 关闭UPX加速启动
    upx_exclude=[],
    console=False,
    onefile=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/AlloyActApp.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,  # 关闭UPX加速启动
    upx_exclude=[],
    name='AlloyActApp'
)