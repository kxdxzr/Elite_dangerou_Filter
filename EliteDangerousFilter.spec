# Build: python -m PyInstaller --noconfirm --clean EliteDangerousFilter.spec
from pathlib import Path

project = Path(SPECPATH)
a = Analysis(
    [str(project / "filter_gui.py")],
    pathex=[str(project)],
    binaries=[],
    datas=[],
    hiddenimports=["powerplay_gui", "powerplay_tool", "rare_goods", "exe_smoke_test", "exe_session_test"],
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
    name="EliteDangerousFilter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
