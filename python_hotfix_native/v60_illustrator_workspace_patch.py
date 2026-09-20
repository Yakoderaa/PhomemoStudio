from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v60_illustrator_workspace.py", pkg / "v60_illustrator_workspace.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V60_ILLUSTRATOR_WORKSPACE_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V60_ILLUSTRATOR_WORKSPACE_INSTALL
from .v60_illustrator_workspace import install as _install_v60_illustrator_workspace
_install_v60_illustrator_workspace(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 6.0 Illustrator-style workspace")
