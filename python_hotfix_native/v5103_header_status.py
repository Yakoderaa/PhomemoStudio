from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


def _move_to_layout(layout, widget):
    if widget is None:
        return
    try:
        widget.setParent(layout.parentWidget())
    except Exception:
        pass
    layout.addWidget(widget)


def enhance(window):
    if getattr(window, "_v5103_header_status", None) is not None:
        return

    header = window.findChild(QFrame, "v51Header")
    if header is None or header.layout() is None:
        return

    header_layout = header.layout()
    status = QFrame(header)
    status.setObjectName("v5103PrinterStatus")
    row = QHBoxLayout(status)
    row.setContentsMargins(7, 4, 7, 4)
    row.setSpacing(7)

    connect = getattr(window, "connect_btn", None)
    battery = getattr(window, "battery", None)
    paper = getattr(window, "paper", None)
    roll = getattr(window, "roll_status", None)

    if isinstance(connect, QPushButton):
        connect.setObjectName("v5103ConnectButton")
        connect.setMinimumWidth(112)
        connect.setProperty("role", "primary")
        _move_to_layout(row, connect)

    for widget, name in (
        (battery, "v5103Battery"),
        (paper, "v5103Paper"),
        (roll, "v5103Roll"),
    ):
        if isinstance(widget, QLabel):
            widget.setObjectName(name)
            widget.setProperty("headerStatus", True)
            widget.setMinimumWidth(76)
            _move_to_layout(row, widget)

    status.setStyleSheet("""
        QFrame#v5103PrinterStatus {
            background: #F7F9FC;
            border: 1px solid #D8DEE9;
            border-radius: 9px;
        }
        QLabel[headerStatus="true"] {
            color: #445066;
            padding: 3px 5px;
            font-size: 11px;
        }
    """)

    before = window.findChild(QPushButton, "v59ShowPropertiesButton")
    if before is None:
        before = window.findChild(QPushButton, "v51UpdateButton")
    index = header_layout.indexOf(before) if before is not None else -1
    if index >= 0:
        header_layout.insertWidget(index, status)
    else:
        header_layout.addWidget(status)

    window._v5103_header_status = status
    window.statusBar().showMessage(
        "V5.10.3 · conexión, batería, papel y rollo siempre visibles arriba",
        5000,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v5103_header_installed", False):
        return
    MainWindow._v5103_header_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
