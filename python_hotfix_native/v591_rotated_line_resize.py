from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QPainterPath, QTransform
from PySide6.QtWidgets import QGraphicsPathItem

ROLE_KIND = 1001


def _is_line(item):
    return isinstance(item, QGraphicsPathItem) and item.data(ROLE_KIND) == "studio-line"


def _install_axis_independent_line_resize(window):
    controller = getattr(window, "_v55_transform_controller", None)
    if controller is None or getattr(controller, "_v591_axis_line_resize", False):
        return
    controller._v591_axis_line_resize = True

    old_begin = controller.begin_resize
    old_resize = controller.resize_to
    old_end = controller.end_resize

    state = {
        "active": False,
        "target": None,
        "kind": None,
        "path": None,
        "rect": QRectF(),
        "inverse": None,
        "start_x": 0.0,
    }

    def begin_resize(kind, scene_pos, modifiers):
        target = controller.target
        if not _is_line(target):
            return old_begin(kind, scene_pos, modifiers)
        if kind not in ("l", "r"):
            controller.drag_kind = None
            return

        inverse, ok = target.sceneTransform().inverted()
        if not ok:
            return

        rect = target.path().boundingRect()
        state.update({
            "active": True,
            "target": target,
            "kind": kind,
            "path": QPainterPath(target.path()),
            "rect": QRectF(rect),
            "inverse": inverse,
            "start_x": rect.left() if kind == "l" else rect.right(),
        })
        controller.drag_kind = kind

    def resize_to(scene_pos, modifiers):
        target = controller.target
        if not _is_line(target):
            return old_resize(scene_pos, modifiers)
        if not state["active"] or state["target"] is not target:
            return

        inv = state["inverse"]
        rect = state["rect"]
        local = inv.map(scene_pos)
        kind = state["kind"]

        alt = bool(modifiers & Qt.AltModifier)
        anchor_x = rect.center().x() if alt else (rect.right() if kind == "l" else rect.left())
        start_x = state["start_x"]
        denom = start_x - anchor_x
        if abs(denom) < 1e-9:
            return

        factor = (local.x() - anchor_x) / denom
        # Do not mirror the line by crossing its opposite endpoint.
        factor = max(0.025, min(80.0, float(factor)))

        xform = QTransform()
        xform.translate(anchor_x, 0.0)
        xform.scale(factor, 1.0)
        xform.translate(-anchor_x, 0.0)

        target.setPath(xform.map(state["path"]))
        # Keep item transform/rotation untouched: only line geometry changes.
        target.update()
        controller.refresh_geometry(force=True)

    def end_resize():
        target = controller.target
        if not _is_line(target):
            return old_end()

        # Do NOT call the generic resize finalizer for the line because the
        # geometry has already been changed directly in local coordinates.
        controller.drag_kind = None
        controller.initial_transform = None
        controller.initial_scene_inverse = None
        state.update({
            "active": False,
            "target": None,
            "kind": None,
            "path": None,
            "inverse": None,
        })

        try:
            from .v54_assets_session import _schedule_save
            _schedule_save(window)
        except Exception:
            pass
        history = getattr(window, "_v57_history", None)
        if history is not None:
            QTimer.singleShot(0, history.commit)
        controller.refresh_geometry(force=True)

    controller.begin_resize = begin_resize
    controller.resize_to = resize_to
    controller.end_resize = end_resize


def enhance(window):
    _install_axis_independent_line_resize(window)
    window.statusBar().showMessage(
        "V5.9.1 · líneas redimensionables por sus extremos a cualquier ángulo",
        5000,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v591_installed", False):
        return
    MainWindow._v591_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
