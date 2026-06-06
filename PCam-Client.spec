# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['PCam-Client.py'],
    pathex=[],
    binaries=[
        ('Binaries/ffmpeg.exe', 'Binaries'),
        ('Binaries/adb.exe', 'Binaries'),
        ('Binaries/AdbWinApi.dll', 'Binaries'),
        ('Binaries/AdbWinUsbApi.dll', 'Binaries'),
    ],
    datas=[('Images', 'Images')],
    hiddenimports=['zeroconf', 'pyvirtualcam'],
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
    name='PCam',
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
    icon='Images\\PCam_logo.ico',
)
