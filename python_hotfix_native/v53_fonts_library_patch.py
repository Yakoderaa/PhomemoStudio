from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v53_fonts_library.py", pkg / "v53_fonts_library.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V53_FONTS_LIBRARY_INSTALL"
if marker not in s:
    s += '''\n\n# PHOMEMO_V53_FONTS_LIBRARY_INSTALL\nfrom .v53_fonts_library import install as _install_v53_fonts_library\n_install_v53_fonts_library(MainWindow)\n'''
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.3 live searchable fonts + massive objects/decor library")
