from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2(
    "python_hotfix_native/v604_alignment_multiselect.py",
    pkg / "v604_alignment_multiselect.py",
)

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V604_ALIGNMENT_MULTISELECT_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V604_ALIGNMENT_MULTISELECT_INSTALL
from .v604_alignment_multiselect import install as _install_v604_alignment_multiselect
_install_v604_alignment_multiselect(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 6.0.4 alignment + multi-selection + Illustrator drag modifiers")
