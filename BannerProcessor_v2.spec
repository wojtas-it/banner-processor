# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


def _collect(pkg):
    # Zwraca puste listy, jeśli pakiet nie jest zainstalowany (build nie pada).
    try:
        return collect_all(pkg)
    except Exception:
        return ([], [], [])


# PDF (pdfium) wymagany; drag & drop (tkinterdnd2) opcjonalny.
pdfium_datas, pdfium_binaries, pdfium_hidden = _collect('pypdfium2')
dnd_datas, dnd_binaries, dnd_hidden = _collect('tkinterdnd2')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=pdfium_binaries + dnd_binaries,
    datas=pdfium_datas + dnd_datas,
    hiddenimports=pdfium_hidden + dnd_hidden,
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
    icon='favicon.ico',
)
