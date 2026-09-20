from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v602_menu_cleanup.py", pkg / "v602_menu_cleanup.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V602_MENU_CLEANUP_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V602_MENU_CLEANUP_INSTALL
from .v602_menu_cleanup import install as _install_v602_menu_cleanup
_install_v602_menu_cleanup(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 6.0.2 menu/header cleanup")
