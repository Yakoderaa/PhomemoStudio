from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2(
    "python_hotfix_native/v603_print_queue_concentration.py",
    pkg / "v603_print_queue_concentration.py",
)

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V603_PRINT_QUEUE_CONCENTRATION_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V603_PRINT_QUEUE_CONCENTRATION_INSTALL
from .v603_print_queue_concentration import install as _install_v603_print_queue_concentration
_install_v603_print_queue_concentration(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 6.0.3 centered print + concentration + unified queue")
