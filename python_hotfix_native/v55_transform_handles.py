from __future__ import annotations

from functools import wraps

from PySide6.QtCore import QObject, QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QBrush, QPainterPath, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import (
    QApplication, QGraphicsItem, QGraphicsPolygonItem, QGraphicsRectItem
)

from .studio_pro import _find_canvas

OVERLAY_ROLE = 1098
HANDLE_SIZE = 9.0
MIN_SCALE = 0.025
MAX_SCALE = 80.0


def _clamp_scale(value: float) -> float:
    value = abs(float(value))
    return max(MIN_SCALE, min(MAX_SCALE, value))


class _ResizeHandle(QGraphicsRectItem):
    def __init__(self, controller, kind: str):
        super().__init__(QRectF(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE))
        self.controller = controller
        self.kind = kind
        self.setData(OVERLAY_ROLE, True)
        self.setZValue(1_000_001)
        self.setPen(QPen(QColor("#3B82F6"), 1.2))
        self.setBrush(QBrush(QColor("#FFFFFF")))
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setCursor(self._cursor())

    def _cursor(self):
        return {
            "tl": Qt.SizeFDiagCursor,
            "br": Qt.SizeFDiagCursor,
            "tr": Qt.SizeBDiagCursor,
            "bl": Qt.SizeBDiagCursor,
            "t": Qt.SizeVerCursor,
            "b": Qt.SizeVerCursor,
            "l": Qt.SizeHorCursor,
            "r": Qt.SizeHorCursor,
        }.get(self.kind, Qt.SizeAllCursor)

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(QColor("#DBEAFE")))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(QColor("#FFFFFF")))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self.controller.begin_resize(self.kind, event.scenePos(), event.modifiers())
        event.accept()

    def mouseMoveEvent(self, event):
        self.controller.resize_to(event.scenePos(), event.modifiers())
        event.accept()

    def mouseReleaseEvent(self, event):
        self.controller.resize_to(event.scenePos(), event.modifiers())
        self.controller.end_resize()
        event.accept()


class SelectionTransformController(QObject):
    """
    Illustrator-style selection box for any selectable QGraphicsItem.

    Classic modifier behavior:
      * drag a corner: free width/height scaling
      * Shift + corner: preserve proportions
      * drag a side: resize one axis
      * Alt + any handle: resize from the centre
      * Shift + Alt: preserve proportions from the centre
    """

    def __init__(self, window, view):
        super().__init__(window)
        self.window = window
        self.view = view
        self.scene = view.scene()
        self.target = None
        self.drag_kind = None
        self.initial_transform = None
        self.initial_scene_inverse = None
        self.initial_rect = QRectF()
        self.initial_handle_local = QPointF()
        self._overlay_enabled = True
        self._last_points = {}

        self.outline = QGraphicsPolygonItem()
        self.outline.setData(OVERLAY_ROLE, True)
        self.outline.setZValue(1_000_000)
        pen = QPen(QColor("#2563EB"), 1.2)
        pen.setCosmetic(True)
        self.outline.setPen(pen)
        self.outline.setBrush(Qt.NoBrush)
        self.outline.setAcceptedMouseButtons(Qt.NoButton)
        self.scene.addItem(self.outline)

        self.handles = {}
        for kind in ("tl", "t", "tr", "r", "br", "b", "bl", "l"):
            h = _ResizeHandle(self, kind)
            self.scene.addItem(h)
            self.handles[kind] = h

        self.scene.selectionChanged.connect(self.refresh_selection)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.refresh_geometry)
        self.timer.start()
        self.refresh_selection()

    def _valid_selected_items(self):
        result = []
        for item in self.scene.selectedItems():
            if item.data(OVERLAY_ROLE):
                continue
            if isinstance(item, (_ResizeHandle, QGraphicsPolygonItem)) and item.data(OVERLAY_ROLE):
                continue
            result.append(item)
        return result

    def refresh_selection(self):
        selected = self._valid_selected_items()
        target = selected[0] if len(selected) == 1 else None
        if target is not self.target:
            self.target = target
            self.drag_kind = None
        self.refresh_geometry(force=True)

    def set_overlay_visible(self, visible: bool):
        self._overlay_enabled = bool(visible)
        self.refresh_geometry(force=True)

    def overlay_visible(self) -> bool:
        return bool(self._overlay_enabled and self.target is not None)

    def _set_all_visible(self, visible: bool):
        self.outline.setVisible(visible)
        for handle in self.handles.values():
            handle.setVisible(visible)

    def _local_points(self, rect: QRectF):
        cx, cy = rect.center().x(), rect.center().y()
        return {
            "tl": rect.topLeft(),
            "t": QPointF(cx, rect.top()),
            "tr": rect.topRight(),
            "r": QPointF(rect.right(), cy),
            "br": rect.bottomRight(),
            "b": QPointF(cx, rect.bottom()),
            "bl": rect.bottomLeft(),
            "l": QPointF(rect.left(), cy),
        }

    def refresh_geometry(self, force=False):
        target = self.target
        if not self._overlay_enabled or target is None or target.scene() is not self.scene or not target.isVisible():
            self._set_all_visible(False)
            return

        rect = target.boundingRect()
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            self._set_all_visible(False)
            return

        local = self._local_points(rect)
        points = {key: target.mapToScene(pt) for key, pt in local.items()}

        changed = force or set(points) != set(self._last_points)
        if not changed:
            for key, point in points.items():
                old = self._last_points.get(key)
                if old is None or abs(point.x() - old.x()) > 0.01 or abs(point.y() - old.y()) > 0.01:
                    changed = True
                    break
        if not changed:
            return

        poly = QPolygonF([points["tl"], points["tr"], points["br"], points["bl"]])
        self.outline.setPolygon(poly)
        self.outline.setVisible(True)
        for key, handle in self.handles.items():
            handle.setPos(points[key])
            handle.setVisible(True)
        self._last_points = points

    def _handle_local_point(self, kind: str, rect: QRectF) -> QPointF:
        return self._local_points(rect)[kind]

    def _opposite_anchor(self, kind: str, rect: QRectF) -> QPointF:
        pts = self._local_points(rect)
        opposite = {
            "tl": "br", "t": "b", "tr": "bl", "r": "l",
            "br": "tl", "b": "t", "bl": "tr", "l": "r",
        }
        return pts[opposite[kind]]

    def begin_resize(self, kind: str, scene_pos: QPointF, modifiers):
        if self.target is None:
            return
        self.drag_kind = kind
        self.initial_rect = QRectF(self.target.boundingRect())
        self.initial_transform = QTransform(self.target.transform())
        inverse, ok = self.target.sceneTransform().inverted()
        self.initial_scene_inverse = inverse if ok else None
        self.initial_handle_local = self._handle_local_point(kind, self.initial_rect)

    def _factors(self, current_local: QPointF, modifiers):
        rect = self.initial_rect
        kind = self.drag_kind
        if not kind:
            return 1.0, 1.0, rect.center()

        alt = bool(modifiers & Qt.AltModifier)
        shift = bool(modifiers & Qt.ShiftModifier)
        anchor = rect.center() if alt else self._opposite_anchor(kind, rect)
        hp = self.initial_handle_local

        dx0 = hp.x() - anchor.x()
        dy0 = hp.y() - anchor.y()
        sx = (current_local.x() - anchor.x()) / dx0 if abs(dx0) > 1e-9 else 1.0
        sy = (current_local.y() - anchor.y()) / dy0 if abs(dy0) > 1e-9 else 1.0

        uses_x = kind in ("tl", "tr", "r", "br", "bl", "l")
        uses_y = kind in ("tl", "t", "tr", "br", "b", "bl")

        if not uses_x:
            sx = 1.0
        if not uses_y:
            sy = 1.0

        # Keep resize stable: crossing the opposite handle reaches the minimum size
        # rather than suddenly mirroring the artwork.
        if uses_x:
            sx = _clamp_scale(sx)
        if uses_y:
            sy = _clamp_scale(sy)

        if shift:
            if uses_x and uses_y:
                # Pick the axis with the larger change so Shift feels natural.
                uniform = sx if abs(sx - 1.0) >= abs(sy - 1.0) else sy
                sx = sy = _clamp_scale(uniform)
            elif uses_x:
                sy = sx
            elif uses_y:
                sx = sy

        return sx, sy, anchor

    def resize_to(self, scene_pos: QPointF, modifiers):
        if self.target is None or self.drag_kind is None or self.initial_scene_inverse is None:
            return
        current_local = self.initial_scene_inverse.map(scene_pos)
        sx, sy, anchor = self._factors(current_local, modifiers)

        extra = QTransform()
        extra.translate(anchor.x(), anchor.y())
        extra.scale(sx, sy)
        extra.translate(-anchor.x(), -anchor.y())

        # Restore the press-time transform on every move, then apply the new
        # relative transform. This prevents cumulative drift.
        self.target.setTransform(self.initial_transform)
        self.target.setTransform(extra, True)
        self.refresh_geometry(force=True)

    def end_resize(self):
        self.drag_kind = None
        self.initial_transform = None
        self.initial_scene_inverse = None
        try:
            from .v54_assets_session import _schedule_save
            _schedule_save(self.window)
        except Exception:
            pass
        self.refresh_geometry(force=True)

    def dispose(self):
        self.timer.stop()
        for handle in list(self.handles.values()):
            if handle.scene() is self.scene:
                self.scene.removeItem(handle)
        if self.outline.scene() is self.scene:
            self.scene.removeItem(self.outline)


def _wrap_output_methods(MainWindow):
    names = (
        "export_png", "export_image", "export_svg", "export_ai",
        "print_current", "print_queue", "render_label", "render_scene"
    )
    for name in names:
        original = getattr(MainWindow, name, None)
        if not callable(original) or getattr(original, "_v55_overlay_safe", False):
            continue

        @wraps(original)
        def wrapped(self, *args, __original=original, **kwargs):
            controller = getattr(self, "_v55_transform_controller", None)
            was_visible = controller.overlay_visible() if controller is not None else False
            if controller is not None:
                controller.set_overlay_visible(False)
                try:
                    QApplication.processEvents()
                except Exception:
                    pass
            try:
                return __original(self, *args, **kwargs)
            finally:
                if controller is not None and was_visible:
                    QTimer.singleShot(0, lambda c=controller: c.set_overlay_visible(True))

        wrapped._v55_overlay_safe = True
        setattr(MainWindow, name, wrapped)


def enhance(window):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return
    controller = SelectionTransformController(window, view)
    window._v55_transform_controller = controller
    window.statusBar().showMessage(
        "V5.5 · tiradores de transformación: Shift mantiene proporción · Alt escala desde el centro",
        6500,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v55_installed", False):
        return
    MainWindow._v55_installed = True
    _wrap_output_methods(MainWindow)

    original_init = MainWindow.__init__
    original_close = getattr(MainWindow, "closeEvent", None)

    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        enhance(self)

    def wrapped_close(self, event):
        controller = getattr(self, "_v55_transform_controller", None)
        if controller is not None:
            try:
                controller.dispose()
            except Exception:
                pass
        if original_close is not None:
            return original_close(self, event)
        event.accept()

    MainWindow.__init__ = wrapped_init
    MainWindow.closeEvent = wrapped_close
