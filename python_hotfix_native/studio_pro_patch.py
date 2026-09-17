from pathlib import Path
import re
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/studio_pro.py", pkg / "studio_pro.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_STUDIO_PRO_INSTALL"
if marker not in s:
    s += '''\n\n# PHOMEMO_STUDIO_PRO_INSTALL\nfrom .studio_pro import install as _install_studio_pro\n_install_studio_pro(MainWindow)\n'''
    ui.write_text(s, encoding="utf-8")

# Force PyInstaller to embed the transparent Sr Gato icon into the executable.
spec = Path("python_app/PhomemoStudio.spec")
if spec.exists():
    x = spec.read_text(encoding="utf-8")
    if re.search(r"icon\s*=", x):
        x = re.sub(r"icon\s*=\s*[^,\n\)]+", "icon='assets/sr-gato.ico'", x, count=1)
    else:
        # Add icon to the EXE(...) call. Works with the compact spec used by the project.
        pos = x.find("EXE(")
        if pos >= 0:
            close = x.find("\n)", pos)
            if close >= 0:
                x = x[:close] + ",\n    icon='assets/sr-gato.ico'" + x[close:]
    spec.write_text(x, encoding="utf-8")

print("Applied Studio Pro: modern UI, total font discovery, shape library, working updater and taskbar icon identity")
