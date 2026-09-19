from __future__ import annotations

import copy
import json
from types import MethodType

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import (
    QAction, QFont, QKeySequence, QTextBlockFormat, QTextCharFormat, QTextCursor, QTransform
)
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFrame, QGraphicsItem,
    QGraphicsPathItem, QGraphicsTextItem, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QStackedWidget,
    QToolButton, QVBoxLayout, QWidget
)

from .studio_pro import _find_canvas
from .v54_assets_session import (
    ROLE_KIND, ROLE_NAME, ROLE_V54, _is_user_item, _restore_item, _serialize_item
)

ROLE_LOCKED = 1058
OVERLAY_ROLE = 1098


def _schedule(window):
    try:
        from .v54_assets_session import _schedule_save
        _schedule_save(window)
    except Exception:
        pass


def _commit_history(window):
    history = getattr(window, "_v57_history", None)
    if history is not None:
        QTimer.singleShot(0, history.commit)


# ---------------------------------------------------------------------------
# Text formatting: apply to the complete QTextDocument, not just defaults.
# ---------------------------------------------------------------------------

def _selected_text(window):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return None
    selected = [i for i in view.scene().selectedItems() if not i.data(OVERLAY_ROLE)]
    if len(selected) == 1 and isinstance(selected[0], QGraphicsTextItem):
        return selected[0]
    return None


def _merge_document_char_format(item: QGraphicsTextItem, fmt: QTextCharFormat):
    cursor = QTextCursor(item.document())
    cursor.select(QTextCursor.Document)
    cursor.mergeCharFormat(fmt)
    cursor.clearSelection()
    item.setTextCursor(cursor)


def _for_each_block(item: QGraphicsTextItem, mutator):
    doc = item.document()
    block = doc.begin()
    while block.isValid():
        cursor = QTextCursor(block)
        fmt = block.blockFormat()
        mutator(fmt)
        cursor.setBlockFormat(fmt)
        block = block.next()


def _alignment_value(text: str):
    key = (text or "").strip().casefold()
    if "centro" in key or "centr" in key:
        return Qt.AlignHCenter
    if "derecha" in key or "right" in key:
        return Qt.AlignRight
    if "justif" in key:
        return Qt.AlignJustify
    return Qt.AlignLeft


def _apply_text_property(window, binder, key: str):
    item = _selected_text(window)
    if item is None:
        return False
    widget = binder.fields.get(key)
    if widget is None:
        return False

    if key == "contenido":
        try:
            value = widget.toPlainText()
        except Exception:
            try:
                value = widget.text()
            except Exception:
                return False
        if value != item.toPlainText():
            item.setPlainText(value)

    elif key == "fuente" and isinstance(widget, QComboBox):
        family = widget.currentText().strip()
        if not family:
            return False
        font = item.font()
        font.setFamily(family)
        item.setFont(font)
        fmt = QTextCharFormat()
        try:
            fmt.setFontFamilies([family])
        except Exception:
            try:
                fmt.setFontFamily(family)
            except Exception:
                fmt.setFont(font)
        _merge_document_char_format(item, fmt)

    elif key == "tamano" and isinstance(widget, QDoubleSpinBox):
        value = max(1.0, float(widget.value()))
        font = item.font()
        font.setPointSizeF(value)
        item.setFont(font)
        fmt = QTextCharFormat()
        fmt.setFontPointSize(value)
        _merge_document_char_format(item, fmt)

    elif key in ("grosor", "peso") and isinstance(widget, QComboBox):
        try:
            weight = int(widget.currentData())
        except Exception:
            weight = 400
        weight = max(100, min(900, weight))
        font = item.font()
        try:
            font.setWeight(QFont.Weight(weight))
        except Exception:
            font.setWeight(weight)
        item.setFont(font)
        fmt = QTextCharFormat()
        try:
            fmt.setFontWeight(weight)
        except Exception:
            fmt.setFont(font)
        _merge_document_char_format(item, fmt)

    elif key == "alineacion" and isinstance(widget, QComboBox):
        alignment = _alignment_value(widget.currentText())
        _for_each_block(item, lambda fmt: fmt.setAlignment(alignment))

    elif key in ("espaciado", "tracking") and isinstance(widget, QDoubleSpinBox):
        value = float(widget.value())
        font = item.font()
        font.setLetterSpacing(QFont.AbsoluteSpacing, value)
        item.setFont(font)
        fmt = QTextCharFormat()
        fmt.setFont(font)
        _merge_document_char_format(item, fmt)

    elif key == "interlineado" and isinstance(widget, QDoubleSpinBox):
        multiplier = max(0.5, min(4.0, float(widget.value())))
        percent = multiplier * 100.0
        _for_each_block(
            item,
            lambda fmt: fmt.setLineHeight(percent, QTextBlockFormat.ProportionalHeight),
        )

    else:
        return False

    try:
        from .v56_text_lines_rotation import _clear_text_selection
        _clear_text_selection(item, move_to_end=True)
    except Exception:
        pass

    item.update()
    if item.scene() is not None:
        item.scene().update()
    controller = getattr(window, "_v55_transform_controller", None)
    if controller is not None:
        controller.refresh_geometry(force=True)
    _schedule(window)
    _commit_history(window)
    return True


def _patch_text_binder(window):
    binder = getattr(window, "_v56_text_binder", None)
    if binder is None or getattr(binder, "_v58_fixed", False):
        return
    binder._v58_fixed = True
    old_apply = binder.apply
    old_sync = binder.sync_from_selection

    def apply(self, key):
        if getattr(self, "_syncing", False):
            return
        if _apply_text_property(window, self, key):
            return
        return old_apply(key)

    def sync(self):
        old_sync()
        item = _selected_text(window)
        if item is None:
            return
        self._syncing = True
        try:
            font = item.font()
            weight = self.fields.get("grosor")
            if isinstance(weight, QComboBox):
                target = int(font.weight())
                best = min(
                    range(weight.count()),
                    key=lambda i: abs(int(weight.itemData(i) or 400) - target),
                    default=0,
                )
                weight.setCurrentIndex(best)

            tracking = self.fields.get("espaciado")
            if isinstance(tracking, QDoubleSpinBox):
                spacing = float(font.letterSpacing()) if font.letterSpacingType() == QFont.AbsoluteSpacing else 0.0
                tracking.setValue(spacing)

            alignment = self.fields.get("alineacion")
            if isinstance(alignment, QComboBox):
                first = item.document().begin()
                current = first.blockFormat().alignment() if first.isValid() else Qt.AlignLeft
                if current & Qt.AlignJustify:
                    alignment.setCurrentText("Justificado")
                elif current & Qt.AlignHCenter:
                    alignment.setCurrentText("Centro")
                elif current & Qt.AlignRight:
                    alignment.setCurrentText("Derecha")
                else:
                    alignment.setCurrentText("Izquierda")

            line_height = self.fields.get("interlineado")
            if isinstance(line_height, QDoubleSpinBox):
                first = item.document().begin()
                if first.isValid():
                    fmt = first.blockFormat()
                    try:
                        h = float(fmt.lineHeight())
                        line_height.setValue(h / 100.0 if h > 0 else 1.0)
                    except Exception:
                        line_height.setValue(1.0)
        finally:
            self._syncing = False

    binder.apply = MethodType(apply, binder)
    binder.sync_from_selection = MethodType(sync, binder)
    if binder.view is not None and binder.view.scene() is not None:
        try:
            binder.view.scene().selectionChanged.connect(binder.sync_from_selection)
        except Exception:
            pass
    binder.sync_from_selection()


# ---------------------------------------------------------------------------
# Line geometry/properties: changing length never scales stroke thickness.
# ---------------------------------------------------------------------------

def _is_line(item):
    return isinstance(item, QGraphicsPathItem) and item.data(ROLE_KIND) == "studio-line"


def _normalize_line_geometry(item):
    if not _is_line(item):
        return False
    transform = item.transform()
    if transform.isIdentity():
        return False
    item.setPath(transform.map(item.path()))
    item.setTransform(QTransform())
    item.update()
    return True


def _patch_line_resize(window):
    controller = getattr(window, "_v55_transform_controller", None)
    if controller is None or getattr(controller, "_v58_line_resize_fixed", False):
        return
    controller._v58_line_resize_fixed = True
    old_end = controller.end_resize

    def end_resize():
        target = controller.target
        old_end()
        if target is not None and _normalize_line_geometry(target):
            controller.refresh_geometry(force=True)
            _schedule(window)
            _commit_history(window)

    controller.end_resize = end_resize


class LineProperties(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.view = _find_canvas(window)
        self._syncing = False
        self.card = None
        self.width = None
        self._build()
        if self.view is not None and self.view.scene() is not None:
            self.view.scene().selectionChanged.connect(self.sync)
        self.sync()

    def _build(self):
        inspector = getattr(self.window, "_v51_inspector", None)
        if inspector is None:
            return
        scroll = inspector.findChild(QScrollArea, "v51InspectorScroll")
        body = scroll.widget() if scroll is not None else None
        layout = body.layout() if body is not None else None
        if layout is None:
            return

        card = QFrame()
        card.setObjectName("v58LineProperties")
        card.setProperty("card", True)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(9)

        title = QLabel("Línea")
        title.setProperty("sectionTitle", True)
        outer.addWidget(title)

        row = QHBoxLayout()
        row.addWidget(QLabel("Grosor"))
        width = QDoubleSpinBox()
        width.setObjectName("v58LineWidth")
        width.setRange(0.25, 50.0)
        width.setDecimals(2)
        width.setSingleStep(0.25)
        width.setSuffix(" px")
        width.valueChanged.connect(self.apply)
        row.addWidget(width, 1)
        outer.addLayout(row)

        card.hide()
        layout.insertWidget(1, card)
        self.card = card
        self.width = width

    def selected_line(self):
        if self.view is None or self.view.scene() is None:
            return None
        selected = [i for i in self.view.scene().selectedItems() if not i.data(OVERLAY_ROLE)]
        if len(selected) == 1 and _is_line(selected[0]):
            return selected[0]
        return None

    def sync(self):
        item = self.selected_line()
        if self.card is not None:
            self.card.setVisible(item is not None)
        if item is None or self.width is None:
            return
        self._syncing = True
        try:
            self.width.setValue(max(0.25, float(item.pen().widthF())))
        finally:
            self._syncing = False

    def apply(self, value):
        if self._syncing:
            return
        item = self.selected_line()
        if item is None:
            return
        _normalize_line_geometry(item)
        pen = item.pen()
        pen.setWidthF(max(0.25, float(value)))
        item.setPen(pen)
        item.update()
        controller = getattr(self.window, "_v55_transform_controller", None)
        if controller is not None:
            controller.refresh_geometry(force=True)
        _schedule(self.window)
        _commit_history(self.window)


# ---------------------------------------------------------------------------
# Clipboard: Ctrl+C, Ctrl+V and Illustrator-style Ctrl+B (Paste in Back).
# ---------------------------------------------------------------------------

class ClipboardController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.view = _find_canvas(window)
        self.payload = []

        self.copy_action = QAction("Copiar", window)
        self.copy_action.setShortcut(QKeySequence("Ctrl+C"))
        self.copy_action.setShortcutContext(Qt.ApplicationShortcut)
        self.copy_action.triggered.connect(self.copy)

        self.paste_action = QAction("Pegar", window)
        self.paste_action.setShortcut(QKeySequence("Ctrl+V"))
        self.paste_action.setShortcutContext(Qt.ApplicationShortcut)
        self.paste_action.triggered.connect(lambda: self.paste(False))

        self.paste_back_action = QAction("Pegar detrás", window)
        self.paste_back_action.setShortcut(QKeySequence("Ctrl+B"))
        self.paste_back_action.setShortcutContext(Qt.ApplicationShortcut)
        self.paste_back_action.triggered.connect(lambda: self.paste(True))

        for action in (self.copy_action, self.paste_action, self.paste_back_action):
            window.addAction(action)

        menu = getattr(window, "_v57_edit_menu", None)
        if menu is not None:
            menu.addSeparator()
            menu.addAction(self.copy_action)
            menu.addAction(self.paste_action)
            menu.addAction(self.paste_back_action)
        self._update()
        if self.view is not None and self.view.scene() is not None:
            self.view.scene().selectionChanged.connect(self._update)

    def _selected(self):
        if self.view is None or self.view.scene() is None:
            return []
        return [
            i for i in self.view.scene().selectedItems()
            if not i.data(OVERLAY_ROLE) and _is_user_item(i) and not i.data(ROLE_LOCKED)
        ]

    def _update(self):
        self.copy_action.setEnabled(bool(self._selected()))
        enabled = bool(self.payload)
        self.paste_action.setEnabled(enabled)
        self.paste_back_action.setEnabled(enabled)

    def copy(self):
        selected = self._selected()
        payload = []
        for item in selected:
            data = _serialize_item(item)
            if data is not None:
                payload.append(copy.deepcopy(data))
        if payload:
            self.payload = payload
            self.window.statusBar().showMessage(f"Copiado: {len(payload)} elemento(s)", 1500)
        self._update()

    def paste(self, behind=False):
        if not self.payload or self.view is None or self.view.scene() is None:
            return
        scene = self.view.scene()
        scene.clearSelection()
        created = []
        for data in self.payload:
            clone = copy.deepcopy(data)
            if behind:
                clone["z"] = float(clone.get("z", 0.0)) - 0.1
            else:
                clone["x"] = float(clone.get("x", 0.0)) + 12.0
                clone["y"] = float(clone.get("y", 0.0)) + 12.0
                clone["z"] = float(clone.get("z", 0.0)) + 0.1
            clone["locked"] = False
            item = _restore_item(clone)
            if item is None:
                continue
            scene.addItem(item)
            if not behind:
                item.setSelected(True)
            created.append(item)
        if created:
            _schedule(self.window)
            _commit_history(self.window)
            label = "Pegado detrás" if behind else "Pegado"
            self.window.statusBar().showMessage(f"{label}: {len(created)} elemento(s)", 1500)
        self._update()


# ---------------------------------------------------------------------------
# Layers panel with per-item lock/unlock.
# ---------------------------------------------------------------------------

def _layer_name(item):
    name = item.data(ROLE_NAME) or item.data(1002)
    if name:
        return str(name)
    if isinstance(item, QGraphicsTextItem):
        text = " ".join(item.toPlainText().split())
        return f"Texto · {text[:28] or 'sin contenido'}"
    kind = item.data(ROLE_KIND)
    if kind:
        return str(kind)
    return item.__class__.__name__.replace("QGraphics", "").replace("Item", "")


def set_item_locked(window, item, locked: bool):
    locked = bool(locked)
    item.setSelected(False)
    item.setData(ROLE_LOCKED, locked)
    item.setData(ROLE_V54, True)
    if locked:
        try:
            item.clearFocus()
        except Exception:
            pass
        if isinstance(item, QGraphicsTextItem):
            try:
                item.setTextInteractionFlags(Qt.NoTextInteraction)
            except Exception:
                pass
        item.setFlags(QGraphicsItem.GraphicsItemFlag(0))
    else:
        item.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsFocusable
        )
    item.update()
    _schedule(window)
    _commit_history(window)


class LayersPanel(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.view = _find_canvas(window)
        self.scene = self.view.scene() if self.view is not None else None
        self.list = None
        self.search = None
        self._signature = None
        self._build_page()
        self.timer = QTimer(self)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.refresh_if_needed)
        self.timer.start()
        if self.scene is not None:
            self.scene.selectionChanged.connect(self.refresh_if_needed)
        self.refresh(force=True)

    def items(self):
        if self.scene is None:
            return []
        return [
            item for item in self.scene.items(Qt.DescendingOrder)
            if not item.data(OVERLAY_ROLE) and _is_user_item(item)
        ]

    def _build_page(self):
        pages = getattr(self.window, "_v51_drawer_pages", None)
        stack = self.window.findChild(QStackedWidget, "v51DrawerStack")
        if not isinstance(pages, dict) or stack is None:
            return
        if "Capas" in pages:
            return

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(9)

        info = QLabel("Bloqueá elementos para que sigan visibles e imprimibles sin poder moverlos por accidente.")
        info.setWordWrap(True)
        info.setProperty("muted", True)
        outer.addWidget(info)

        search = QLineEdit()
        search.setPlaceholderText("Buscar capas…")
        search.textChanged.connect(lambda _="": self.refresh(force=True))
        outer.addWidget(search)
        self.search = search

        actions = QHBoxLayout()
        lock_all = QPushButton("Bloquear todos")
        unlock_all = QPushButton("Desbloquear todos")
        lock_all.clicked.connect(lambda: self.set_all(True))
        unlock_all.clicked.connect(lambda: self.set_all(False))
        actions.addWidget(lock_all)
        actions.addWidget(unlock_all)
        outer.addLayout(actions)

        listing = QListWidget()
        listing.setObjectName("v58LayersList")
        listing.setSelectionMode(QAbstractItemView.NoSelection)
        outer.addWidget(listing, 1)
        self.list = listing

        pages["Capas"] = page
        stack.addWidget(page)

        # Add a rail entry matching the V5.1 navigation.
        rail = getattr(self.window, "_v51_nav_buttons", {})
        rail_frame = self.window.findChild(QFrame, "v51Rail")
        rail_layout = rail_frame.layout() if rail_frame is not None else None
        if rail_layout is not None:
            insert_at = max(0, rail_layout.count() - 1)
            button = QToolButton()
            button.setText("▤")
            button.setToolTip("Capas")
            button.setFixedSize(48, 44)
            button.setProperty("nav", True)
            button.setObjectName("v58NavCapas")
            button.clicked.connect(lambda: self.window._v51_show_drawer("Capas"))
            caption = QLabel("Capas")
            caption.setProperty("railCaption", True)
            caption.setAlignment(Qt.AlignCenter)
            rail_layout.insertWidget(insert_at, button, 0, Qt.AlignHCenter)
            rail_layout.insertWidget(insert_at + 1, caption)
            rail["Capas"] = button

        menu = self.window.menuBar()
        for action in menu.actions():
            if action.text().replace("&", "").strip().casefold() == "ver" and action.menu():
                show = QAction("Capas", self.window)
                show.triggered.connect(lambda: self.window._v51_show_drawer("Capas"))
                action.menu().addAction(show)
                break

    def signature(self):
        out = []
        for item in self.items():
            out.append((
                id(item), _layer_name(item), bool(item.data(ROLE_LOCKED)),
                bool(item.isVisible()), float(item.zValue()), bool(item.isSelected())
            ))
        return tuple(out)

    def refresh_if_needed(self):
        sig = self.signature()
        if sig != self._signature:
            self.refresh(force=True)

    def refresh(self, force=False):
        if self.list is None:
            return
        sig = self.signature()
        if not force and sig == self._signature:
            return
        self._signature = sig
        query = (self.search.text() if self.search is not None else "").strip().casefold()
        self.list.clear()
        for item in self.items():
            name = _layer_name(item)
            if query and query not in name.casefold():
                continue
            row_item = QListWidgetItem()
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(7, 4, 7, 4)
            layout.setSpacing(7)

            select = QToolButton()
            select.setText("●" if item.isSelected() else "○")
            select.setToolTip("Seleccionar esta capa")
            select.setEnabled(not bool(item.data(ROLE_LOCKED)))
            select.clicked.connect(lambda _=False, it=item: self.select_item(it))
            layout.addWidget(select)

            label = QLabel(name)
            label.setToolTip(name)
            layout.addWidget(label, 1)

            lock = QToolButton()
            locked = bool(item.data(ROLE_LOCKED))
            lock.setText("🔒" if locked else "🔓")
            lock.setToolTip("Desbloquear" if locked else "Bloquear")
            lock.setFixedWidth(36)
            lock.clicked.connect(lambda _=False, it=item, value=not locked: self.toggle(it, value))
            layout.addWidget(lock)

            row_item.setSizeHint(row.sizeHint())
            self.list.addItem(row_item)
            self.list.setItemWidget(row_item, row)

    def select_item(self, item):
        if self.scene is None or bool(item.data(ROLE_LOCKED)):
            return
        self.scene.clearSelection()
        item.setSelected(True)
        try:
            item.setFocus()
        except Exception:
            pass
        self.refresh(force=True)

    def toggle(self, item, locked):
        set_item_locked(self.window, item, locked)
        self.refresh(force=True)

    def set_all(self, locked):
        for item in self.items():
            set_item_locked(self.window, item, locked)
        self.refresh(force=True)


def enhance(window):
    _patch_text_binder(window)
    _patch_line_resize(window)
    window._v58_line_properties = LineProperties(window)
    window._v58_clipboard = ClipboardController(window)
    window._v58_layers = LayersPanel(window)
    window.statusBar().showMessage(
        "V5.8 · texto corregido · Ctrl+C/Ctrl+V/Ctrl+B · grosor de línea · capas bloqueables",
        6500,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v58_installed", False):
        return
    MainWindow._v58_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
