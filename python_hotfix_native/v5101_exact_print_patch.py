from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v5101_exact_print.py", pkg / "v5101_exact_print.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V5101_EXACT_PRINT_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V5101_EXACT_PRINT_INSTALL
from .v5101_exact_print import install as _install_v5101_exact_print
_install_v5101_exact_print(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.10.1 exact canvas print + D30 orientation")
