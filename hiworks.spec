# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller 빌드 스펙
# 실행: pyinstaller hiworks.spec --clean --noconfirm
#
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# playwright 드라이버(Node.js 바이너리 포함) 전체 수집
datas = collect_data_files("playwright", include_py_files=False)

hiddenimports = (
    collect_submodules("playwright")
    + [
        "keyring.backends",
        "keyring.backends.Windows",
        "keyring.backends.fail",
        "PyQt5",
        "PyQt5.QtWidgets",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
    ]
)

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="hiworks-time",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # 콘솔 창 없음
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
