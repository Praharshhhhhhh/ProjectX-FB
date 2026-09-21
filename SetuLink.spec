# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Harsh Patel\\Desktop\\WG_PROJECTX\\client\\main.py'],
    pathex=['C:\\Users\\Harsh Patel\\Desktop\\WG_PROJECTX\\client'],
    binaries=[('C:\\Users\\Harsh Patel\\Desktop\\WG_PROJECTX\\client\\.bin\\wg.exe', '.bin'), ('C:\\Users\\Harsh Patel\\Desktop\\WG_PROJECTX\\client\\.bin\\wireguard.exe', '.bin'), ('C:\\Users\\Harsh Patel\\Desktop\\WG_PROJECTX\\client\\.bin\\wintun.dll', '.bin')],
    datas=[('C:\\Users\\Harsh Patel\\Desktop\\WG_PROJECTX\\client\\assets', 'assets')],
    hiddenimports=['services.wireguard_local', 'keyring'],
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
    name='SetuLink',
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
    uac_admin=True,
)
