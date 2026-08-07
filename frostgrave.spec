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
#
# Globbed rather than hand-listed (B6) — this exact list used to be
# maintained by hand in three places (this file, frostgrave-linux.spec, and
# scripts/build_browser_bundle.py) and has desynced and shipped broken twice
# (see git history). A glob can't drift.
from pathlib import Path

datas = [
    ("templates", "templates"),
    ("static", "static"),
    ("pyproject.toml", "."),
] + [(str(p), "data") for p in sorted(Path("data").glob("*.json"))]

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
