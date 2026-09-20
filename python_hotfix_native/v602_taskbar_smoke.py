import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v602-taskbar-")

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.v602_taskbar_icon import APP_ID, _apply_native_taskbar_icon

assert APP_ID == "Yakoderaa.PhomemoStudio"

w = MainWindow()
QApplication.processEvents()
_apply_native_taskbar_icon(w)
QApplication.processEvents()

# Installer shortcuts must use the same Windows identity as the running process.
iss = Path("python_app/installer.iss").read_text(encoding="utf-8")
assert 'AppUserModelID: "Yakoderaa.PhomemoStudio"' in iss
assert 'IconFilename: "{app}\\{#MyAppExeName}"' in iss

w.close()
print("V6.0.2 Windows taskbar icon identity smoke OK")
