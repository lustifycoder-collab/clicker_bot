# -*- mode: python ; coding: utf-8 -*-

# pynput и pyautogui тянут платформенные модули, которые PyInstaller
# не всегда находит автоматически. Прописываем их явно.
_hidden = [
    'pynput',
    'pynput.keyboard',
    'pynput.keyboard._base',
    'pynput.mouse',
    'pynput.mouse._base',
    'pynput._util',
    'pyautogui',
    'pyautogui._pyautogui_win',
    'pyautogui._pyautogui_x11',
    'pyautogui._pyautogui_osx',
    'pygetwindow',
    'pyscreeze',
    'pytweening',
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