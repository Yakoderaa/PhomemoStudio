from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v52_polish.py", pkg / "v52_polish.py")

req = Path("python_app/requirements.txt")
requirements = req.read_text(encoding="utf-8") if req.exists() else ""
if "qtawesome" not in requirements.lower():
    if requirements and not requirements.endswith("\n"):
        requirements += "\n"
    requirements += "qtawesome==1.4.2\n"
    req.write_text(requirements, encoding="utf-8")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V52_POLISH_INSTALL"
if marker not in s:
    s += '''\n\n# PHOMEMO_V52_POLISH_INSTALL\nfrom .v52_polish import install as _install_v52_polish\n_install_v52_polish(MainWindow)\n'''
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.2 modern numeric controls + open licensed icon library")
