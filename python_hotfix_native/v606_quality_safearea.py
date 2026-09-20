from __future__ import annotations

import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel


def _clean_placeholder_text(text: str, label: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return label

    # Normalize the common disconnected/unknown placeholders without touching
    # legitimate values such as "Batería 87%" or "Papel OK".
    compact = raw.replace("–", "—").replace("-", "—")
    patterns = (
        rf"^{re.escape(label)}\s*[:·]?\s*—+$",
        rf"^{re.escape(label)}\s*[:·]?\s*N/?A$",
        rf"^{re.escape(label)}\s*[:·]?\s*—?\s*$",
    )
    for pattern in patterns:
        if re.match(pattern, compact, flags=re.IGNORECASE):
            return label
    return raw


def _clean_header_status(window):
    battery = getattr(window, "battery", None)
    paper = getattr(window, "paper", None)

    if isinstance(battery, QLabel):
        battery.setText(_clean_placeholder_text(battery.text(), "Batería"))
    if isinstance(paper, QLabel):
        paper.setText(_clean_placeholder_text(paper.text(), "Papel"))


def enhance(window):
    _clean_header_status(window)

    timer = QTimer(window)
    timer.setInterval(400)
    timer.timeout.connect(lambda: _clean_header_status(window))
    timer.start()
    window._v606_header_clean_timer = timer

    window.statusBar().showMessage(
        "V6.0.6 · puntillismo preservado · marco curvo · zona segura · esquinas",
        6500,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v606_quality_installed", False):
        return
    MainWindow._v606_quality_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
