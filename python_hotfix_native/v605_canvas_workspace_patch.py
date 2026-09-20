from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2(
    "python_hotfix_native/v605_canvas_workspace.py",
    pkg / "v605_canvas_workspace.py",
)

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V605_CANVAS_WORKSPACE_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V605_CANVAS_WORKSPACE_INSTALL
from .v605_canvas_workspace import install as _install_v605_canvas_workspace
_install_v605_canvas_workspace(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 6.0.5 rebuilt canvas + rounded 40x12 print zone")
