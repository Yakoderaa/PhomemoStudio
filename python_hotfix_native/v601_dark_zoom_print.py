from __future__ import annotations

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import (
    QAbstractScrollArea, QFrame, QGraphicsView, QLabel, QPushButton, QScrollArea,
    QToolButton, QWidget
)

from .studio_pro import _find_canvas


DARK = "#2B2B2B"
DARK2 = "#303030"
DARK3 = "#383838"
BORDER = "#4C4C4C"
TEXT = "#ECECEC"
MUTED = "#B8B8B8"
ACCENT = "#2F74C0"


def _apply_full_dark(window):
    extra = f"""
        QMainWindow {{
            background:{DARK};
            color:{TEXT};
        }}
        QMainWindow QWidget {{
            background:{DARK};
            color:{TEXT};
        }}
        QMainWindow QFrame {{
            background:{DARK2};
            color:{TEXT};
            border-color:{BORDER};
        }}
        QMainWindow QScrollArea,
        QMainWindow QScrollArea > QWidget,
        QMainWindow QScrollArea > QWidget > QWidget,
        QMainWindow QAbstractScrollArea::viewport {{
            background:{DARK2};
            color:{TEXT};
        }}
        QFrame#v51Header,
        QFrame#v51CanvasBar,
        QFrame#v51Stage,
        QFrame#v51Drawer,
        QFrame#v60RightPanel,
        QFrame#v5103PrinterStatus {{
            background:{DARK2};
            color:{TEXT};
            border-color:{BORDER};
        }}
        QFrame#v51CanvasHost {{
            background:#4B4B4B;
            border:0;
        }}
        QWidget#v51Workspace {{
            background:#444444;
        }}
        QLabel {{
            background:transparent;
            color:{TEXT};
        }}
        QLabel[muted="true"] {{
            color:{MUTED};
        }}
        QPushButton, QToolButton {{
            background:{DARK3};
            color:{TEXT};
            border:1px solid #5A5A5A;
            border-radius:3px;
            padding:5px 9px;
        }}
        QPushButton:hover, QToolButton:hover {{
            background:#474747;
        }}
        QPushButton[role="primary"] {{
            background:{ACCENT};
            color:white;
            border-color:#4A91DD;
        }}
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background:#232323;
            color:{TEXT};
            border:1px solid #555;
            border-radius:3px;
        }}
        QListWidget, QTreeWidget {{
            background:#292929;
            color:{TEXT};
            border:0;
        }}
        QTabWidget::pane {{
            background:{DARK2};
            border:0;
        }}
        QTabBar::tab {{
            background:#292929;
            color:#C7C7C7;
            padding:8px 11px;
            border:0;
            border-right:1px solid #454545;
        }}
        QTabBar::tab:selected {{
            background:#363636;
            color:white;
            border-bottom:2px solid #3D8BE0;
        }}
        QProgressBar {{
            background:#252525;
            color:{TEXT};
            border:1px solid #505050;
            border-radius:3px;
            text-align:center;
        }}
        QProgressBar::chunk {{
            background:{ACCENT};
        }}
    """
    window.setStyleSheet((window.styleSheet() or "") + "\n" + extra)


class ZoomController(QObject):
    def __init__(self, window, view: QGraphicsView, label: QLabel, minus, plus, reset):
        super().__init__(window)
        self.window = window
        self.view = view
        self.label = label
        self.percent = 100
        self.minus = minus
        self.plus = plus
        self.reset = reset

        for button in (minus, plus, reset):
            if button is None:
                continue
            try:
                button.clicked.disconnect()
            except Exception:
                pass

        if minus is not None:
            minus.clicked.connect(lambda: self.step(-10))
            minus.setToolTip("Alejar 10%")
        if plus is not None:
            plus.clicked.connect(lambda: self.step(10))
            plus.setToolTip("Acercar 10%")
        if reset is not None:
            reset.clicked.connect(lambda: self.set_zoom(100))
            reset.setToolTip("Restablecer zoom al 100%")

        self.view.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.view.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.view.viewport().installEventFilter(self)
        self.set_zoom(100)

    def set_zoom(self, percent):
        self.percent = max(10, min(800, int(percent)))
        transform = QTransform()
        scale = self.percent / 100.0
        transform.scale(scale, scale)
        self.view.setTransform(transform, False)
        self.label.setText(f"{self.percent}%")
        if self.reset is not None:
            self.reset.setText("100%")

    def step(self, amount):
        self.set_zoom(self.percent + int(amount))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and (event.modifiers() & Qt.ControlModifier):
            delta = event.angleDelta().y()
            self.step(10 if delta > 0 else -10)
            event.accept()
            return True
        return False


def _install_zoom(window):
    view = _find_canvas(window)
    bar = window.findChild(QFrame, "v51CanvasBar")
    label = window.findChild(QLabel, "v51ZoomLabel")
    if view is None or bar is None or label is None:
        return

    minus = None
    plus = None
    reset = None
    for button in bar.findChildren(QToolButton):
        text = button.text().strip()
        if text in ("−", "-"):
            minus = button
        elif text == "+":
            plus = button
    for button in bar.findChildren(QPushButton):
        if button.text().strip() == "100%":
            reset = button
            break

    if minus is None or plus is None or reset is None:
        return

    window._v601_zoom_controller = ZoomController(window, view, label, minus, plus, reset)


def enhance(window):
    _apply_full_dark(window)
    _install_zoom(window)
    window.statusBar().showMessage(
        "V6.0.1 · tema oscuro completo · zoom real · impresión 40×12 mm 1:1",
        6000,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v601_installed", False):
        return
    MainWindow._v601_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
