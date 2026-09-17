import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from .ui import MainWindow

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app=QApplication(sys.argv); app.setApplicationName("Phomemo Studio"); app.setOrganizationName("Phomemo Studio")
    win=MainWindow(); app.setWindowIcon(win.windowIcon()); win.show(); return app.exec()

if __name__=="__main__": raise SystemExit(main())
