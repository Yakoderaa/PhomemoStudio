from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v54_assets_session.py", pkg / "v54_assets_session.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V54_ASSETS_SESSION_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V54_ASSETS_SESSION_INSTALL
from .v54_assets_session import install as _install_v54_assets_session
_install_v54_assets_session(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.4 persistent image library + autosave session")
