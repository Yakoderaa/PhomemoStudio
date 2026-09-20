from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import QObject, QEvent, QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsItem, QGraphicsRectItem, QGraphicsView,
    QLabel, QPushButton, QScrollArea, QToolButton, QGridLayout, QVBoxLayout
)

from .studio_pro import _find_canvas
from .v5101_exact_print import DPI, _label_source_rect
from .v54_assets_session import (
    _is_user_item, _restore_item, _schedule_save, _serialize_item
)
from .v55_transform_handles import SelectionTransformController
from .v56_text_lines_rotation import _install_rotation
from .v58_text_clipboard_layers import _patch_line_resize
from .v59_properties_line_resize import _install_line_length_only_resize
from .v591_rotated_line_resize import _install_axis_independent_line_resize

OVERLAY_ROLE = 1098
ROLE_LOCKED = 1058
ROLE_KIND = 1001
SAFE_MARGIN_MM = 1.0
SAFE_MARGIN_PX = SAFE_MARGIN_MM * DPI / 25.4


def _commit(window):
    try:
        _schedule_save(window)
    except Exception:
        pass
    history = getattr(window, "_v57_history", None)
    if history is not None:
        QTimer.singleShot(0, history.commit)


def _selected_items(window):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return []
    return [
        item for item in view.scene().selectedItems()
        if not item.data(OVERLAY_ROLE)
        and not item.data(ROLE_LOCKED)
        and _is_user_item(item)
    ]


def _union_rect(items):
    rect = None
    for item in items:
        r = item.sceneBoundingRect()
        rect = QRectF(r) if rect is None else rect.united(r)
    return rect


def _set_item_scene_delta(item, start_pos: QPointF, scene_delta: QPointF):
    parent = item.parentItem()
    if parent is None:
        item.setPos(start_pos + scene_delta)
        return
    a = parent.mapFromScene(QPointF(0, 0))
    b = parent.mapFromScene(scene_delta)
    item.setPos(start_pos + (b - a))


def _safe_label_rect(label: QRectF) -> QRectF:
    margin = min(
        SAFE_MARGIN_PX,
        max(0.0, label.width() / 2.0 - 1.0),
        max(0.0, label.height() / 2.0 - 1.0),
    )
    return label.adjusted(margin, margin, -margin, -margin)


def align_selection(window, mode: str):
    items = _selected_items(window)
    if not items:
        window.statusBar().showMessage("Seleccioná uno o más objetos para alinear.", 2500)
        return False

    view = _find_canvas(window)
    scene = view.scene()
    label = _label_source_rect(scene)
    group = _union_rect(items)
    if group is None or label.isNull():
        return False

    safe = _safe_label_rect(label)
    dx = dy = 0.0
    if mode == "center":
        # Center is geometrically exact. Edge/corner modes use the 1 mm safe area.
        dx = label.center().x() - group.center().x()
        dy = label.center().y() - group.center().y()
    elif mode == "top":
        dx = safe.center().x() - group.center().x()
        dy = safe.top() - group.top()
    elif mode == "bottom":
        dx = safe.center().x() - group.center().x()
        dy = safe.bottom() - group.bottom()
    elif mode == "left":
        dx = safe.left() - group.left()
        dy = safe.center().y() - group.center().y()
    elif mode == "right":
        dx = safe.right() - group.right()
        dy = safe.center().y() - group.center().y()
    elif mode == "top-left":
        dx = safe.left() - group.left()
        dy = safe.top() - group.top()
    elif mode == "top-right":
        dx = safe.right() - group.right()
        dy = safe.top() - group.top()
    elif mode == "bottom-left":
        dx = safe.left() - group.left()
        dy = safe.bottom() - group.bottom()
    elif mode == "bottom-right":
        dx = safe.right() - group.right()
        dy = safe.bottom() - group.bottom()
    else:
        return False

    delta = QPointF(dx, dy)
    for item in items:
        _set_item_scene_delta(item, item.pos(), delta)

    controller = getattr(window, "_v55_transform_controller", None)
    if controller is not None:
        controller.refresh_selection()
        controller.refresh_geometry(force=True)
    multi = getattr(window, "_v604_multi_select", None)
    if multi is not None:
        multi.refresh_outline()
    _commit(window)
    window.statusBar().showMessage("Selección alineada a la etiqueta.", 1800)
    return True


def _install_alignment_card(window):
    if getattr(window, "_v604_alignment_card", None) is not None:
        return

    scroll = window.findChild(QScrollArea, "v51InspectorScroll")
    body = scroll.widget() if scroll is not None else None
    layout = body.layout() if body is not None else None
    if layout is None:
        return

    card = QFrame()
    card.setObjectName("v604AlignmentCard")
    card.setProperty("sectionCard", True)
    outer = QVBoxLayout(card)
    outer.setContentsMargins(12, 12, 12, 12)
    outer.setSpacing(8)

    title = QLabel("Alinear a etiqueta")
    title.setProperty("sectionTitle", True)
    outer.addWidget(title)

    desc = QLabel("Centro exacto; bordes y esquinas respetan una zona segura interna de 1 mm.")
    desc.setWordWrap(True)
    desc.setProperty("muted", True)
    outer.addWidget(desc)

    grid = QGridLayout()
    grid.setSpacing(5)

    specs = [
        ("top-left", "↖", "Esquina superior izquierda · margen seguro 1 mm", 0, 0),
        ("top", "↑", "Arriba-centro · margen seguro 1 mm", 0, 1),
        ("top-right", "↗", "Esquina superior derecha · margen seguro 1 mm", 0, 2),
        ("left", "←", "Izquierda-centro · margen seguro 1 mm", 1, 0),
        ("center", "◎", "Centro exacto", 1, 1),
        ("right", "→", "Derecha-centro · margen seguro 1 mm", 1, 2),
        ("bottom-left", "↙", "Esquina inferior izquierda · margen seguro 1 mm", 2, 0),
        ("bottom", "↓", "Abajo-centro · margen seguro 1 mm", 2, 1),
        ("bottom-right", "↘", "Esquina inferior derecha · margen seguro 1 mm", 2, 2),
    ]
    buttons = {}
    for mode, symbol, tip, row, col in specs:
        b = QToolButton()
        b.setText(symbol)
        b.setToolTip(tip)
        b.setFixedSize(48, 38)
        b.clicked.connect(lambda _=False, m=mode: align_selection(window, m))
        grid.addWidget(b, row, col)
        buttons[mode] = b

    outer.addLayout(grid)
    layout.insertWidget(0, card)
    window._v604_alignment_card = card
    window._v604_alignment_buttons = buttons


def _rebuild_transform_controller(window):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return

    old = getattr(window, "_v55_transform_controller", None)
    if old is not None:
        try:
            old.dispose()
        except Exception:
            pass

    controller = SelectionTransformController(window, view)
    window._v55_transform_controller = controller

    # Restore the complete late-patch chain on the new controller:
    # 8 resize handles + 4 rotate handles for normal objects,
    # only left/right length handles + rotation for lines.
    _install_rotation(window)
    _patch_line_resize(window)
    _install_line_length_only_resize(window)
    _install_axis_independent_line_resize(window)

    controller.refresh_selection()
    controller.refresh_geometry(force=True)


class MultiSelectionController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.view = _find_canvas(window)
        self.scene = self.view.scene()
        self.viewport = self.view.viewport()

        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setRubberBandSelectionMode(Qt.ContainsItemShape)
        self.viewport.installEventFilter(self)

        self.drag_active = False
        self.drag_started = False
        self.drag_duplicate = False
        self.drag_orthogonal = False
        self.press_scene = QPointF()
        self.drag_items = []
        self.start_positions = {}

        self.group_outline = QGraphicsRectItem()
        self.group_outline.setData(OVERLAY_ROLE, True)
        self.group_outline.setZValue(999_999)
        pen = QPen(QColor("#2F80ED"), 1.2)
        pen.setCosmetic(True)
        self.group_outline.setPen(pen)
        self.group_outline.setBrush(Qt.NoBrush)
        self.group_outline.setAcceptedMouseButtons(Qt.NoButton)
        self.scene.addItem(self.group_outline)

        self.scene.selectionChanged.connect(self.refresh_outline)
        self.refresh_outline()

        self.delete_action = QAction("Eliminar selección", window)
        self.delete_action.setShortcut("Delete")
        self.delete_action.setShortcutContext(Qt.ApplicationShortcut)
        self.delete_action.triggered.connect(self.delete_selected)
        window.addAction(self.delete_action)

        self.select_all_action = QAction("Seleccionar todo", window)
        self.select_all_action.setShortcut("Ctrl+A")
        self.select_all_action.setShortcutContext(Qt.ApplicationShortcut)
        self.select_all_action.triggered.connect(self.select_all)
        window.addAction(self.select_all_action)

    def user_items(self):
        return [
            item for item in self.scene.items()
            if not item.data(OVERLAY_ROLE)
            and not item.data(ROLE_LOCKED)
            and _is_user_item(item)
        ]

    def selected(self):
        return [
            item for item in self.scene.selectedItems()
            if not item.data(OVERLAY_ROLE)
            and not item.data(ROLE_LOCKED)
            and _is_user_item(item)
        ]

    def refresh_outline(self):
        items = self.selected()
        if len(items) <= 1:
            self.group_outline.hide()
            return
        rect = _union_rect(items)
        if rect is None:
            self.group_outline.hide()
            return
        self.group_outline.setRect(rect)
        self.group_outline.show()

    def select_all(self):
        self.scene.clearSelection()
        for item in self.user_items():
            item.setSelected(True)
        self.refresh_outline()

    def delete_selected(self):
        items = self.selected()
        if not items:
            return
        self.scene.clearSelection()
        for item in items:
            try:
                self.scene.removeItem(item)
            except Exception:
                pass
        self.refresh_outline()
        controller = getattr(self.window, "_v55_transform_controller", None)
        if controller is not None:
            controller.refresh_selection()
        _commit(self.window)

    def _target_at(self, viewport_pos):
        for item in self.view.items(viewport_pos):
            if item.data(OVERLAY_ROLE):
                # Interactive resize/rotate handles keep their native event path.
                # Passive overlays (selection/group outlines) must not block the
                # actual object underneath from Shift/Ctrl/Alt selection logic.
                try:
                    if item.acceptedMouseButtons() != Qt.NoButton:
                        return item
                except Exception:
                    pass
                continue
            if item.data(ROLE_LOCKED):
                continue
            if _is_user_item(item):
                return item
        return None

    def _begin_custom_drag(self, target, event, duplicate=False, orthogonal=False):
        if target is None or target.data(OVERLAY_ROLE):
            return False

        selected = self.selected()
        if target not in selected:
            if orthogonal:
                # Shift+click adds to the existing selection.
                target.setSelected(True)
            else:
                self.scene.clearSelection()
                target.setSelected(True)

        self.drag_items = self.selected()
        self.start_positions = {id(item): QPointF(item.pos()) for item in self.drag_items}
        self.press_scene = self.view.mapToScene(event.position().toPoint())
        self.drag_active = True
        self.drag_started = False
        self.drag_duplicate = bool(duplicate)
        self.drag_orthogonal = bool(orthogonal)
        self.refresh_outline()
        return True

    def _duplicate_drag_items(self):
        originals = list(self.drag_items)
        clones = []
        self.scene.clearSelection()
        for item in originals:
            data = _serialize_item(item)
            if data is None:
                continue
            clone = _restore_item(deepcopy(data))
            if clone is None:
                continue
            clone.setData(ROLE_LOCKED, False)
            self.scene.addItem(clone)
            clone.setSelected(True)
            clones.append(clone)

        if clones:
            self.drag_items = clones
            self.start_positions = {id(item): QPointF(item.pos()) for item in clones}
            controller = getattr(self.window, "_v55_transform_controller", None)
            if controller is not None:
                controller.refresh_selection()
        return bool(clones)

    def _move_drag(self, event):
        current = self.view.mapToScene(event.position().toPoint())
        delta = current - self.press_scene

        if not self.drag_started:
            if abs(delta.x()) + abs(delta.y()) < 1.5:
                return
            self.drag_started = True
            if self.drag_duplicate:
                self._duplicate_drag_items()

        if self.drag_orthogonal:
            if abs(delta.x()) >= abs(delta.y()):
                delta.setY(0.0)
            else:
                delta.setX(0.0)

        for item in self.drag_items:
            start = self.start_positions.get(id(item), item.pos())
            _set_item_scene_delta(item, start, delta)

        controller = getattr(self.window, "_v55_transform_controller", None)
        if controller is not None:
            controller.refresh_selection()
            controller.refresh_geometry(force=True)
        self.refresh_outline()

    def _end_drag(self):
        moved = self.drag_started
        self.drag_active = False
        self.drag_started = False
        self.drag_items = []
        self.start_positions = {}
        if moved:
            _commit(self.window)
        self.refresh_outline()

    def eventFilter(self, obj, event):
        if obj is not self.viewport:
            return False

        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            target = self._target_at(event.position().toPoint())
            if target is not None and target.data(OVERLAY_ROLE):
                return False

            mods = event.modifiers()

            # Ctrl+click toggles membership in the current selection.
            if (mods & Qt.ControlModifier) and not (mods & Qt.AltModifier):
                if target is not None:
                    target.setSelected(not target.isSelected())
                    self.refresh_outline()
                    event.accept()
                    return True
                return False

            # Alt drag duplicates. Shift drag constrains to horizontal/vertical.
            # Alt+Shift does both, like Illustrator.
            if target is not None and (mods & (Qt.AltModifier | Qt.ShiftModifier)):
                if self._begin_custom_drag(
                    target,
                    event,
                    duplicate=bool(mods & Qt.AltModifier),
                    orthogonal=bool(mods & Qt.ShiftModifier),
                ):
                    event.accept()
                    return True

            # The older text-selection filter clears a multi-selection on a
            # normal click, so handle group drag here before that filter sees it.
            if target is not None and len(self.selected()) > 1 and target.isSelected():
                if self._begin_custom_drag(target, event, duplicate=False, orthogonal=False):
                    event.accept()
                    return True

        elif event.type() == QEvent.MouseMove and self.drag_active:
            if event.buttons() & Qt.LeftButton:
                self._move_drag(event)
                event.accept()
                return True

        elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and self.drag_active:
            self._end_drag()
            event.accept()
            return True

        return False

    def dispose(self):
        try:
            self.viewport.removeEventFilter(self)
        except Exception:
            pass
        if self.group_outline.scene() is self.scene:
            self.scene.removeItem(self.group_outline)


def enhance(window):
    _rebuild_transform_controller(window)
    _install_alignment_card(window)

    old = getattr(window, "_v604_multi_select", None)
    if old is not None:
        try:
            old.dispose()
        except Exception:
            pass

    window._v604_multi_select = MultiSelectionController(window)
    window.statusBar().showMessage(
        "V6.0.4 · alinear a etiqueta · selección múltiple · Alt duplica · Shift ortogonal · tiradores restaurados",
        7000,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v604_installed", False):
        return
    MainWindow._v604_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
