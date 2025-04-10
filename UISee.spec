# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
project_root = os.path.abspath('.')

a = Analysis(
    ['ui_see_app.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        ('UISee.py', '.'),  # Entry point script
        ('config/.env', 'config'),  # Environment settings
        ('snapshots/', 'snapshots'),  # Auto-saved snapshots
        ('templates/', 'templates'),  # Test templates
        ('ui_map.db', '.'),  # DB file if needed
        ('gui/', 'gui'),  # GUI modules
        ('services/', 'services'),  # MQTT + Parser services
        ('utils/', 'utils'),  # Utility classes like MQTT adapter
    ],
    hiddenimports=collect_submodules('tkinter') + 
                   collect_submodules('gui') +
                   collect_submodules('services') +
                   collect_submodules('utils'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='UI-See',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Change to False for silent GUI app
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='UI-See'
)
