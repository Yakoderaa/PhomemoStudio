from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v5103_header_status.py", pkg / "v5103_header_status.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V5103_HEADER_STATUS_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V5103_HEADER_STATUS_INSTALL
from .v5103_header_status import install as _install_v5103_header_status
_install_v5103_header_status(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.10.3 persistent printer header status")
