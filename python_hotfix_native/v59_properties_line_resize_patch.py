from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v59_properties_line_resize.py", pkg / "v59_properties_line_resize.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V59_PROPERTIES_LINE_RESIZE_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V59_PROPERTIES_LINE_RESIZE_INSTALL
from .v59_properties_line_resize import install as _install_v59_properties_line_resize
_install_v59_properties_line_resize(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.9 Properties restore + length-only line resize")
