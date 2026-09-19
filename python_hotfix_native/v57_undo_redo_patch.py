from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v57_undo_redo.py", pkg / "v57_undo_redo.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V57_UNDO_REDO_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V57_UNDO_REDO_INSTALL
from .v57_undo_redo import install as _install_v57_undo_redo
_install_v57_undo_redo(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.7 global undo/redo history")
