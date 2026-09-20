from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v601_dark_zoom_print.py", pkg / "v601_dark_zoom_print.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V601_DARK_ZOOM_PRINT_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V601_DARK_ZOOM_PRINT_INSTALL
from .v601_dark_zoom_print import install as _install_v601_dark_zoom_print
_install_v601_dark_zoom_print(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 6.0.1 full dark UI + functional zoom + exact 40x12 print mapping")
