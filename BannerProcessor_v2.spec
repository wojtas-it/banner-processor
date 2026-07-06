# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

# Dołącz bibliotekę PDF (binarka pdfium + dane) do pakietu .exe
pdfium_datas, pdfium_binaries, pdfium_hiddenimports = collect_all('pypdfium2')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=pdfium_binaries,
    datas=pdfium_datas,
    hiddenimports=pdfium_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BannerProcessor_v2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
