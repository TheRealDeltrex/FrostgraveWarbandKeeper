# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Frostgrave Warband Keeper.

Build (from the project root, with requirements-dev.txt installed):
    pyinstaller frostgrave.spec

Produces a onedir build at dist/FrostgraveWarbandKeeper/ (a folder containing
the exe + bundled resources), chosen over onefile for faster cold start and
easier debugging — onefile re-extracts everything to a temp dir on every launch.
"""

block_cipher = None

# Only the read-only reference data is bundled. Runtime user data (warbands,
# portraits) is never bundled — it lives in paths.user_data_dir(), resolved
# fresh at runtime, outside this read-only extracted bundle.
datas = [
    ("templates", "templates"),
    ("static", "static"),
    ("data/potions.json", "data"),
    ("data/potion_descriptions.json", "data"),
    ("data/spell_descriptions.json", "data"),
    ("data/standard_items.json", "data"),
    ("data/bestiary.json", "data"),
]

a = Analysis(
    ["run_app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["waitress", "pystray", "pystray._win32"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FrostgraveWarbandKeeper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FrostgraveWarbandKeeper",
)
