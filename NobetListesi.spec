# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: Nöbet Listesi Oluşturucu desktop GUI.

--onedir --windowed, native architecture only (matches the build host —
Apple Silicon/arm64 on a Mac). NOT universal2: ortools ships single-arch
wheels only (no fat/universal2 build), and Intel Mac support was explicitly
dropped as a requirement — this app targets this Mac (arm64) and, built
separately on a Windows machine/runner, Windows.

onedir (not onefile): PyInstaller deprecated onefile+.app-bundle on macOS
(it doesn't really make sense — a .app is already a directory, and onefile's
self-extract-to-temp-dir step just adds startup latency for no benefit here).
onedir launches directly from the already-unpacked bundle, so it starts
faster.

collect_all('ortools') pulls in its native .so/.dylib extensions and data
files, which plain PyInstaller static analysis tends to miss for a
C-extension-heavy package like this — the #1 real cause of "works with
python -m ... but not from the packaged .app" bugs.
On Windows, the BUNDLE() step below (which produces a macOS .app) is skipped
— dist/NobetListesi/ (containing NobetListesi.exe) is the final build there.
"""

import sys

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

for package in ("ortools", "openpyxl"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ["run_gui.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NobetListesi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # native arch only (arm64 here) — no universal2
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="NobetListesi",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="NobetListesi.app",
        icon=None,
        bundle_identifier="com.sudesavut.nobetlistesi",
        info_plist={
            "CFBundleName": "Nöbet Listesi",
            "CFBundleDisplayName": "Nöbet Listesi",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
        },
    )
