from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v51_redesign.py", pkg / "v51_redesign.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V51_REDESIGN_INSTALL"
if marker not in s:
    s += '''\n\n# PHOMEMO_V51_REDESIGN_INSTALL\nfrom .v51_redesign import install as _install_v51_redesign\n_install_v51_redesign(MainWindow)\n'''
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.1 complete UI redesign")
