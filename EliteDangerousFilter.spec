# Build: python -m PyInstaller --noconfirm --clean EliteDangerousFilter.spec
from pathlib import Path

project = Path(SPECPATH)
a = Analysis(
    [str(project / "filter_gui.py")],
    pathex=[str(project)],
    binaries=[],
    datas=[],
    hiddenimports=["powerplay_gui", "powerplay_tool", "rare_goods", "exe_smoke_test", "exe_session_test",
                   "pve_gui", "pve_tool", "pve_access", "pve_cache", "faction_options", "i18n", "localized_tk"],
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
