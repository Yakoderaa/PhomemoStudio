from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2(
    "python_hotfix_native/v606_quality_safearea.py",
    pkg / "v606_quality_safearea.py",
)

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V606_QUALITY_SAFEAREA_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V606_QUALITY_SAFEAREA_INSTALL
from .v606_quality_safearea import install as _install_v606_quality_safearea
_install_v606_quality_safearea(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 6.0.6 print-quality + safe-area integration")
