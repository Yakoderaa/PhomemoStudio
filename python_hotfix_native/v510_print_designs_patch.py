from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v510_print_designs.py", pkg / "v510_print_designs.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V510_PRINT_DESIGNS_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V510_PRINT_DESIGNS_INSTALL
from .v510_print_designs import install as _install_v510_print_designs
_install_v510_print_designs(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.10 print stability + persistent designs")
