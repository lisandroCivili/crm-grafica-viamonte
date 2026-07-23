# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# reportlab carga fuentes y recursos como data files que PyInstaller no siempre
# detecta solo. collect_all los junta (datas, binaries e hiddenimports).
rl_datas, rl_binaries, rl_hiddenimports = collect_all('reportlab')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=rl_binaries,
    datas=[('frontend', 'frontend')] + rl_datas,
    hiddenimports=rl_hiddenimports,
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
    name='GraficaViamonte',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
