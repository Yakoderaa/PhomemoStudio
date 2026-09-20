from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidgetItem, QPushButton, QScrollArea,
    QStackedWidget, QTabWidget, QToolButton, QVBoxLayout, QWidget
)


DARK = "#2B2B2B"
DARK_2 = "#343434"
DARK_3 = "#3B3B3B"
PANEL = "#303030"
BORDER = "#494949"
TEXT = "#ECECEC"
MUTED = "#AFAFAF"
ACCENT = "#2F74C0"
ACCENT_2 = "#3D8BE0"
LOCK = "#D69A3A"


def _hide_rail_entry(window, name: str):
    buttons = getattr(window, "_v51_nav_buttons", {})
    button = buttons.get(name)
    if button is not None:
        button.hide()
        parent = button.parentWidget()
        if parent is not None and parent.layout() is not None:
            idx = parent.layout().indexOf(button)
            # The legacy rail stores a caption immediately after each button.
            for offset in (1, 2):
                item = parent.layout().itemAt(idx + offset)
                if item is not None and isinstance(item.widget(), QLabel):
                    if item.widget().text().strip().casefold() == name.casefold():
                        item.widget().hide()
                        break


def _restyle_left_library(window):
    rail = window.findChild(QFrame, "v51Rail")
    drawer = getattr(window, "_v51_drawer", None)
    if rail is not None:
        rail.setFixedWidth(58)
    if drawer is not None:
        drawer.setFixedWidth(282)
        drawer.setMinimumWidth(250)
        drawer.setMaximumWidth(320)

    _hide_rail_entry(window, "Cola")
    _hide_rail_entry(window, "Capas")

    buttons = getattr(window, "_v51_nav_buttons", {})
    symbols = {
        "Diseños": ("▱", "Diseños"),
        "Texto": ("T", "Texto"),
        "Formas": ("□", "Formas y biblioteca"),
        "Imágenes": ("▧", "Imágenes"),
    }
    for name, (symbol, tooltip) in symbols.items():
        button = buttons.get(name)
        if button is None:
            continue
        button.setText(symbol)
        button.setToolTip(tooltip)
        button.setFixedSize(44, 42)

    title = window.findChild(QLabel, "v51DrawerTitle")
    if title is not None:
        title.setText("Biblioteca")


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.setParent(None)
        elif child is not None:
            _clear_layout(child)


def _build_right_workspace(window):
    if getattr(window, "_v60_right_panel", None) is not None:
        return window._v60_right_panel

    workspace = window.findChild(QWidget, "v51Workspace")
    if workspace is None or workspace.layout() is None:
        return None

    old_inspector = getattr(window, "_v51_inspector", None)
    prop_scroll = window.findChild(QScrollArea, "v51InspectorScroll")
    pages = getattr(window, "_v51_drawer_pages", {})
    layers_page = pages.get("Capas")
    queue_page = pages.get("Cola")

    right = QFrame()
    right.setObjectName("v60RightPanel")
    right.setMinimumWidth(320)
    right.setMaximumWidth(390)
    lay = QVBoxLayout(right)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)

    tabs = QTabWidget()
    tabs.setObjectName("v60RightTabs")
    tabs.setDocumentMode(True)
    tabs.setMovable(False)

    prop_host = QWidget()
    prop_lay = QVBoxLayout(prop_host)
    prop_lay.setContentsMargins(8, 8, 8, 8)
    prop_lay.setSpacing(0)
    if prop_scroll is not None:
        prop_scroll.setParent(prop_host)
        prop_lay.addWidget(prop_scroll)
    else:
        prop_lay.addWidget(QLabel("Propiedades"))

    if layers_page is None:
        layers_page = QWidget()
        lp = QVBoxLayout(layers_page)
        lp.addWidget(QLabel("Capas"))
        lp.addStretch(1)
    else:
        layers_page.setParent(tabs)

    if queue_page is None:
        queue_page = QWidget()
        qp = QVBoxLayout(queue_page)
        qp.addWidget(QLabel("Cola de impresión"))
        qp.addStretch(1)
    else:
        queue_page.setParent(tabs)

    tabs.addTab(prop_host, "Propiedades")
    tabs.addTab(layers_page, "Capas")
    tabs.addTab(queue_page, "Cola")

    lay.addWidget(tabs, 1)

    work_lay = workspace.layout()
    if old_inspector is not None:
        idx = work_lay.indexOf(old_inspector)
        if idx >= 0:
            work_lay.insertWidget(idx, right)
        else:
            work_lay.addWidget(right)
        old_inspector.hide()
    else:
        work_lay.addWidget(right)

    window._v60_right_panel = right
    window._v60_right_tabs = tabs
    window._v51_inspector = right

    original_show = getattr(window, "_v51_show_drawer", None)

    def show_drawer(name):
        if name in ("Capas", "Cola"):
            right.show()
            tabs.setCurrentIndex(1 if name == "Capas" else 2)
            return
        if callable(original_show):
            return original_show(name)

    window._v51_show_drawer = show_drawer

    # The permanent Properties button now opens the right panel and selects
    # the Properties tab instead of trying to revive the legacy inspector.
    props_button = window.findChild(QPushButton, "v59ShowPropertiesButton")
    if props_button is not None:
        try:
            props_button.clicked.disconnect()
        except Exception:
            pass
        props_button.clicked.connect(lambda: (right.show(), tabs.setCurrentIndex(0)))

    # Existing "Capas" menu actions were created before this panel existed;
    # dynamic _v51_show_drawer routing above makes them land here correctly.
    return right


def _layer_row_style(selected: bool, locked: bool) -> str:
    if selected:
        bg = "#294D75"
        border = ACCENT_2
    elif locked:
        bg = "#3A332A"
        border = "#6A583E"
    else:
        bg = DARK_3
        border = BORDER
    return f"""
        QFrame#v60LayerRow {{
            background:{bg};
            border:1px solid {border};
            border-radius:4px;
        }}
        QFrame#v60LayerRow QLabel {{
            color:{TEXT};
            background:transparent;
            border:0;
        }}
        QFrame#v60LayerRow QToolButton {{
            background:transparent;
            border:0;
            color:{TEXT};
            padding:2px 4px;
        }}
        QFrame#v60LayerRow QToolButton:hover {{
            background:#4A4A4A;
        }}
    """


def _restyle_layers(window):
    layers = getattr(window, "_v58_layers", None)
    if layers is None or getattr(layers, "_v60_patched", False):
        return
    layers._v60_patched = True

    def refresh(self, force=False):
        if self.list is None:
            return
        sig = self.signature()
        if not force and sig == self._signature:
            return
        self._signature = sig
        query = (self.search.text() if self.search is not None else "").strip().casefold()

        self.list.clear()
        self.list.setSpacing(4)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        for item in self.items():
            name = item.data(1003) or item.data(1002)
            if not name:
                if hasattr(item, "toPlainText"):
                    txt = " ".join(item.toPlainText().split())
                    name = f"Texto · {txt[:28] or 'sin contenido'}"
                else:
                    name = item.data(1001) or item.__class__.__name__.replace("QGraphics", "").replace("Item", "")
            name = str(name)
            if query and query not in name.casefold():
                continue

            locked = bool(item.data(1058))
            selected = bool(item.isSelected())

            qitem = QListWidgetItem()
            qitem.setSizeHint(QSize(278, 50))

            row = QFrame()
            row.setObjectName("v60LayerRow")
            row.setStyleSheet(_layer_row_style(selected, locked))
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 5, 6, 5)
            h.setSpacing(7)

            marker = QLabel("●" if selected else "○")
            marker.setFixedWidth(16)
            marker.setStyleSheet(
                f"color:{ACCENT_2 if selected else MUTED}; font-size:13px; border:0; background:transparent;"
            )
            h.addWidget(marker)

            label = QLabel(name)
            label.setToolTip(name)
            label.setTextInteractionFlags(Qt.NoTextInteraction)
            h.addWidget(label, 1)

            if selected:
                badge = QLabel("SELEC.")
                badge.setStyleSheet(
                    "color:#DDEEFF;background:#34679A;border-radius:3px;padding:2px 5px;font-size:9px;font-weight:700;"
                )
                h.addWidget(badge)
            elif locked:
                badge = QLabel("BLOQ.")
                badge.setStyleSheet(
                    f"color:#FFF1D1;background:#6D5732;border-radius:3px;padding:2px 5px;font-size:9px;font-weight:700;"
                )
                h.addWidget(badge)

            select = QToolButton()
            select.setText("◎")
            select.setToolTip("Seleccionar capa")
            select.setEnabled(not locked)
            select.clicked.connect(lambda _=False, it=item: self.select_item(it))
            h.addWidget(select)

            lock = QToolButton()
            lock.setText("🔒" if locked else "🔓")
            lock.setToolTip("Desbloquear" if locked else "Bloquear")
            lock.setStyleSheet(
                f"color:{LOCK if locked else TEXT}; font-size:14px; background:transparent; border:0;"
            )
            lock.clicked.connect(lambda _=False, it=item, value=not locked: self.toggle(it, value))
            h.addWidget(lock)

            self.list.addItem(qitem)
            self.list.setItemWidget(qitem, row)

    layers.refresh = MethodType(refresh, layers)
    layers.refresh(force=True)


def _move_layers_to_right(window):
    panel = getattr(window, "_v60_right_panel", None)
    tabs = getattr(window, "_v60_right_tabs", None)
    if panel is None or tabs is None:
        return
    layers = getattr(window, "_v58_layers", None)
    if layers is not None:
        layers.refresh(force=True)


def _apply_illustrator_style(window):
    current = window.styleSheet() or ""
    extra = f"""
        QMainWindow, QWidget#v51Root {{
            background:{DARK};
            color:{TEXT};
        }}
        QMenuBar {{
            background:#262626;
            color:{TEXT};
            border-bottom:1px solid #444;
            padding:2px 6px;
        }}
        QMenuBar::item:selected, QMenu::item:selected {{
            background:#444;
        }}
        QMenu {{
            background:#303030;
            color:{TEXT};
            border:1px solid #555;
        }}

        QFrame#v51Header {{
            background:#252525;
            border-bottom:1px solid #454545;
        }}
        QFrame#v5103PrinterStatus {{
            background:#303030;
            border:1px solid #4B4B4B;
            border-radius:4px;
        }}
        QFrame#v5103PrinterStatus QLabel {{
            color:#D5D5D5;
        }}

        QFrame#v51Rail {{
            background:#252525;
            border-right:1px solid #444;
        }}
        QFrame#v51Rail QToolButton {{
            background:transparent;
            color:#E8E8E8;
            border:1px solid transparent;
            border-radius:3px;
            font-size:18px;
        }}
        QFrame#v51Rail QToolButton:hover {{
            background:#3B3B3B;
            border-color:#555;
        }}
        QFrame#v51Rail QToolButton:checked {{
            background:#4A4A4A;
            border-color:{ACCENT_2};
        }}
        QLabel[railCaption="true"] {{
            color:#AFAFAF;
            font-size:9px;
        }}

        QFrame#v51Drawer {{
            background:#303030;
            border-right:1px solid #494949;
        }}
        QLabel#v51DrawerTitle {{
            color:{TEXT};
            font-size:13px;
            font-weight:700;
        }}
        QToolButton#v51DrawerClose {{
            color:#DDD;
            background:transparent;
            border:0;
        }}
        QToolButton#v51DrawerClose:hover {{
            background:#484848;
        }}

        QFrame#v60RightPanel {{
            background:#2F2F2F;
            border-left:1px solid #4A4A4A;
        }}
        QTabWidget#v60RightTabs::pane {{
            border:0;
            border-top:1px solid #4A4A4A;
            background:#303030;
        }}
        QTabWidget#v60RightTabs QTabBar::tab {{
            background:#2A2A2A;
            color:#BBBBBB;
            padding:9px 12px;
            border:0;
            border-right:1px solid #414141;
            min-width:78px;
        }}
        QTabWidget#v60RightTabs QTabBar::tab:selected {{
            color:white;
            background:#353535;
            border-bottom:2px solid {ACCENT_2};
        }}

        QScrollArea {{
            background:#303030;
            border:0;
        }}
        QScrollArea > QWidget > QWidget {{
            background:#303030;
        }}
        QFrame[sectionCard="true"], QFrame[card="true"] {{
            background:#373737;
            border:1px solid #4A4A4A;
            border-radius:4px;
        }}
        QLabel {{
            color:{TEXT};
        }}
        QLabel[muted="true"] {{
            color:{MUTED};
        }}
        QLabel[sectionTitle="true"] {{
            color:#FFFFFF;
            font-size:12px;
            font-weight:700;
        }}

        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background:#232323;
            color:#F0F0F0;
            border:1px solid #545454;
            border-radius:3px;
            padding:5px 7px;
            min-height:24px;
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
        QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border:1px solid {ACCENT_2};
        }}
        QPushButton, QToolButton {{
            background:#3B3B3B;
            color:#F2F2F2;
            border:1px solid #565656;
            border-radius:3px;
            padding:5px 9px;
        }}
        QPushButton:hover, QToolButton:hover {{
            background:#484848;
        }}
        QPushButton[role="primary"] {{
            background:{ACCENT};
            border-color:{ACCENT_2};
            color:white;
        }}

        QListWidget {{
            background:#2B2B2B;
            border:0;
            outline:0;
            padding:4px;
        }}

        QWidget#v51Workspace {{
            background:#444444;
        }}
        QGraphicsView {{
            background:#555555;
            border:0;
        }}
    """
    window.setStyleSheet(current + "
" + extra)


def enhance(window):
    _restyle_left_library(window)
    _build_right_workspace(window)
    _restyle_layers(window)
    _move_layers_to_right(window)
    _apply_illustrator_style(window)

    # If the drawer had been left on a right-side page, return the library to
    # a sensible left-side tool.
    current = getattr(window, "_v51_current_drawer", "")
    if current in ("Capas", "Cola") and callable(getattr(window, "_v51_show_drawer", None)):
        window._v51_show_drawer("Formas")

    window.statusBar().showMessage(
        "V6 · interfaz tipo Illustrator · biblioteca izquierda · Propiedades/Capas/Cola derecha",
        7000,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v60_installed", False):
        return
    MainWindow._v60_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
