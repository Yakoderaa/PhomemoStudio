import ctypes
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from .ui import MainWindow


def _asset(name: str) -> Path:
    root=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent.parent))
    return root/"assets"/name


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    if sys.platform=="win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Yakoderaa.PhomemoStudio.Desktop.4_2")
        except Exception:
            pass
    app=QApplication(sys.argv)
    app.setApplicationName("Phomemo Studio")
    app.setApplicationDisplayName("Phomemo Studio")
    app.setOrganizationName("Phomemo Studio")
    icon=_asset("sr-gato.ico")
    if icon.exists(): app.setWindowIcon(QIcon(str(icon)))
    win=MainWindow()
    if icon.exists(): win.setWindowIcon(QIcon(str(icon)))
    win.show()
    return app.exec()


if __name__=="__main__":
    raise SystemExit(main())
