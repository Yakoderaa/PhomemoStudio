from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v56_text_lines_rotation.py", pkg / "v56_text_lines_rotation.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V56_TEXT_LINES_ROTATION_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V56_TEXT_LINES_ROTATION_INSTALL
from .v56_text_lines_rotation import install as _install_v56_text_lines_rotation
_install_v56_text_lines_rotation(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.6 live text properties + line library + free rotation")
