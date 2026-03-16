# build.spec
"""PyInstaller spec file for History AI Chat Desktop"""
import sys
from pathlib import Path

# Get the src directory
src_dir = Path('src')

a = Analysis(
    ['src/viewer/desktop.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/viewer/static', 'viewer/static'),
        ('src/viewer/templates', 'viewer/templates'),
        ('src/viewer/assets', 'viewer/assets'),
    ],
    hiddenimports=[
        'viewer',
        'viewer.main',
        'viewer.tray',
        'viewer.parsers',
        'viewer.parsers.claude',
        'viewer.parsers.codex',
        'viewer.db',
        'viewer.db.cache',
        'pystray._win32',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='history-ai-chat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Enable UPX compression if available
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/viewer/assets/icon.ico',
)