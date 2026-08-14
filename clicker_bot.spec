# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec для clicker_bot.

Использование:
    pyinstaller clicker_bot.spec

Платформенные hiddenimports подставляются по sys.platform —
pyautogui/pynput тянут разные нативные модули на Windows/macOS/Linux,
и PyInstaller не всегда находит их автоматически. Несуществующие на
данной платформе модули в список НЕ включаем (иначе warning в логе).
"""
import sys

# Общие для всех платформ
_hidden = [
    'pynput',
    'pynput.keyboard',
    'pynput.keyboard._base',
    'pynput.mouse',
    'pynput.mouse._base',
    'pynput._util',
    'pyautogui',
    'pyscreeze',
    'pytweening',
]

if sys.platform == 'win32':
    _hidden += [
        'pyautogui._pyautogui_win',
        'pygetwindow',
    ]
elif sys.platform == 'darwin':
    _hidden += [
        'pyautogui._pyautogui_osx',
    ]
else:  # linux и прочие X11
    _hidden += [
        'pyautogui._pyautogui_x11',
        'Xlib',
        'Xlib.display',
        'Xlib.ext',
        'Xlib.ext.xtest',
        'Xlib.xobject',
        'Xlib.protocol',
        'Xlib.XK',
        'Xlib.X',
    ]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=_hidden,
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
    name='clicker_bot',
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
)

# На macOS дополнительно собираем .app-бандл
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='clicker_bot.app',
        icon=None,
        bundle_identifier='com.clicker.bot',
    )
