# -*- mode: python ; coding: utf-8 -*-
# Build with: pyinstaller desktop.spec

a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('models.py', '.'),
        ('pairing.py', '.'),
        ('app.py', '.'),
    ],
    hiddenimports=['webview', 'flask', 'sqlite3'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='KometAmericano',
    debug=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    icon=None,
)
