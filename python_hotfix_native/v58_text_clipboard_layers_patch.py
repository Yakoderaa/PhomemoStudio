from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
shutil.copy2("python_hotfix_native/v58_text_clipboard_layers.py", pkg / "v58_text_clipboard_layers.py")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V58_TEXT_CLIPBOARD_LAYERS_INSTALL"
if marker not in s:
    s += """
# PHOMEMO_V58_TEXT_CLIPBOARD_LAYERS_INSTALL
from .v58_text_clipboard_layers import install as _install_v58_text_clipboard_layers
_install_v58_text_clipboard_layers(MainWindow)
"""
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.8 text fixes + clipboard + line properties + layers")
