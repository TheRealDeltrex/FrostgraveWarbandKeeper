# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Linux build of Frostgrave Warband Keeper.

Build (on Linux, with requirements-dev.txt installed):
    pyinstaller frostgrave-linux.spec

Produces a single onefile binary at dist/FrostgraveWarbandKeeper — onefile
instead of the Windows build's onedir, since a single downloadable file that
just needs `chmod +x` is the easiest thing to hand a non-technical Linux user
(a whole folder to keep together is an extra way to break it).

The tray icon (tray.py, Windows-only — see app.py's main()) is excluded here:
it pulls in pystray's GTK/AppIndicator/X11 backends, which need system
libraries this build can't guarantee are present. Auto-shutdown on browser
close (idle_watchdog.py) is cross-platform and covers the same "don't leave
it running" need without a tray icon.
"""

block_cipher = None

# Globbed rather than hand-listed (B6) — see frostgrave.spec for why.
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
    hiddenimports=["waitress"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tray"],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="FrostgraveWarbandKeeper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
