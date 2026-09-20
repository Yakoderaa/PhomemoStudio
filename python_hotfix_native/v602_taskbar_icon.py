from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication


APP_ID = "Yakoderaa.PhomemoStudio"


def _apply_native_taskbar_icon(window):
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32

        shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)

        hwnd = int(window.winId())
        if not hwnd:
            return

        # Extract the icon embedded by PyInstaller from PhomemoStudio.exe.
        large = wintypes.HICON()
        small = wintypes.HICON()
        count = shell32.ExtractIconExW(
            str(sys.executable),
            0,
            ctypes.byref(large),
            ctypes.byref(small),
            1,
        )
        if count:
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            if large:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, int(large))
            if small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, int(small))

        # Qt also accepts the embedded EXE icon path on Windows in packaged builds.
        # Keep the existing app/window icon if this fallback cannot load it.
        exe_icon = QIcon(str(sys.executable))
        if not exe_icon.isNull():
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(exe_icon)
            window.setWindowIcon(exe_icon)
    except Exception:
        pass


def enhance(window):
    # Run once during construction and again after Windows has created/shown the HWND.
    _apply_native_taskbar_icon(window)
    QTimer.singleShot(0, lambda: _apply_native_taskbar_icon(window))
    QTimer.singleShot(500, lambda: _apply_native_taskbar_icon(window))


def install(MainWindow):
    if getattr(MainWindow, "_v602_taskbar_installed", False):
        return
    MainWindow._v602_taskbar_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
