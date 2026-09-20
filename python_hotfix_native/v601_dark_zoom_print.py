from __future__ import annotations

from PySide6.QtCore import QObject, QEvent, QTimer, Qt
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import (
    QAbstractScrollArea, QAbstractSpinBox, QDoubleSpinBox, QFrame, QGraphicsView, QLabel,
    QPushButton, QScrollArea, QSpinBox, QToolButton, QWidget
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
        QSpinBox[modernStepper="true"], QDoubleSpinBox[modernStepper="true"] {{
            background:#232323;
            color:{TEXT};
            border:1px solid #555;
            border-radius:3px;
            padding:4px 31px 4px 31px;
            min-height:26px;
        }}
        QSpinBox[modernStepper="true"]::up-button,
        QSpinBox[modernStepper="true"]::down-button,
        QDoubleSpinBox[modernStepper="true"]::up-button,
        QDoubleSpinBox[modernStepper="true"]::down-button {{
            width:0px;
            height:0px;
            border:0;
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



class NumericStepper(QObject):
    """Clear horizontal − / + buttons for every numeric field."""

    def __init__(self, spin):
        super().__init__(spin)
        self.spin = spin
        spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin.setProperty("modernStepper", True)

        self.minus = QToolButton(spin)
        self.minus.setObjectName("v601StepperMinus")
        self.minus.setText("−")
        self.minus.setToolTip("Disminuir")
        self.minus.setFocusPolicy(Qt.NoFocus)
        self.minus.setAutoRepeat(True)
        self.minus.setAutoRepeatDelay(350)
        self.minus.setAutoRepeatInterval(75)
        self.minus.clicked.connect(spin.stepDown)

        self.plus = QToolButton(spin)
        self.plus.setObjectName("v601StepperPlus")
        self.plus.setText("+")
        self.plus.setToolTip("Aumentar")
        self.plus.setFocusPolicy(Qt.NoFocus)
        self.plus.setAutoRepeat(True)
        self.plus.setAutoRepeatDelay(350)
        self.plus.setAutoRepeatInterval(75)
        self.plus.clicked.connect(spin.stepUp)

        button_style = """
            QToolButton {
                background:#3A3A3A;
                color:#F2F2F2;
                border:0;
                font-size:15px;
                font-weight:700;
                padding:0;
            }
            QToolButton:hover { background:#4B4B4B; }
            QToolButton:pressed { background:#245B91; }
            QToolButton:disabled { color:#777; background:#303030; }
        """
        self.minus.setStyleSheet(button_style)
        self.plus.setStyleSheet(button_style)

        spin.installEventFilter(self)
        self._position()

    def _position(self):
        if self.spin is None:
            return
        h = max(22, self.spin.height() - 2)
        w = min(28, max(24, h))
        self.minus.setGeometry(1, 1, w, h)
        self.plus.setGeometry(max(1, self.spin.width() - w - 1), 1, w, h)
        self.minus.raise_()
        self.plus.raise_()
        line = self.spin.lineEdit()
        if line is not None:
            line.setTextMargins(w + 4, 0, w + 4, 0)

    def eventFilter(self, obj, event):
        if obj is self.spin and event.type() in (
            QEvent.Resize, QEvent.Show, QEvent.StyleChange, QEvent.FontChange
        ):
            QTimer.singleShot(0, self._position)
        return False


def _install_numeric_steppers(window):
    controllers = getattr(window, "_v601_numeric_steppers", None)
    if controllers is None:
        controllers = []
        window._v601_numeric_steppers = controllers

    def scan():
        spins = list(window.findChildren(QSpinBox)) + list(window.findChildren(QDoubleSpinBox))
        for spin in spins:
            if spin.property("v601StepperInstalled"):
                continue
            spin.setProperty("v601StepperInstalled", True)
            controllers.append(NumericStepper(spin))

    scan()
    timer = QTimer(window)
    timer.setInterval(1200)
    timer.timeout.connect(scan)
    timer.start()
    window._v601_numeric_stepper_timer = timer


def _force_dark_local_widgets(window):
    # Older versions gave the printer status its own light local stylesheet.
    status = window.findChild(QFrame, "v5103PrinterStatus")
    if status is not None:
        status.setStyleSheet("""
            QFrame#v5103PrinterStatus {
                background:#303030;
                border:1px solid #4C4C4C;
                border-radius:4px;
            }
            QFrame#v5103PrinterStatus QLabel {
                color:#E7E7E7;
                background:transparent;
                border:0;
                padding:3px 5px;
            }
            QFrame#v5103PrinterStatus QPushButton {
                background:#383838;
                color:#F2F2F2;
                border:1px solid #565656;
                border-radius:3px;
                padding:5px 9px;
            }
            QFrame#v5103PrinterStatus QPushButton[role="primary"] {
                background:#2F74C0;
                border-color:#4A91DD;
                color:white;
            }
        """)


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
    _force_dark_local_widgets(window)
    _install_numeric_steppers(window)
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
