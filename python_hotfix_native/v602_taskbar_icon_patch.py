from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v602_taskbar_icon.py", pkg / "v602_taskbar_icon.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V602_TASKBAR_ICON_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V602_TASKBAR_ICON_INSTALL
from .v602_taskbar_icon import install as _install_v602_taskbar_icon
_install_v602_taskbar_icon(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 6.0.2 Windows taskbar icon identity")
