# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
block_cipher=None
root=Path(SPECPATH)
a=Analysis(['run.py'], pathex=[str(root)], binaries=[], datas=[(str(root/'assets'/'sr-gato.png'),'assets')], hiddenimports=['bleak.backends.winrt','bleak.backends.winrt.client','bleak.backends.winrt.scanner'], hookspath=[], runtime_hooks=[], excludes=[], noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='PhomemoStudio',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon=str(root/'assets'/'sr-gato.ico'))
