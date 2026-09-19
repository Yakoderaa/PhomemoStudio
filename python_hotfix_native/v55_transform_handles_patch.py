from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v55_transform_handles.py", pkg / "v55_transform_handles.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V55_TRANSFORM_HANDLES_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V55_TRANSFORM_HANDLES_INSTALL
from .v55_transform_handles import install as _install_v55_transform_handles
_install_v55_transform_handles(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.5 Illustrator-style transform handles")
