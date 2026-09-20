from __future__ import annotations

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QBrush, QFont, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsView
)

from .studio_pro import _find_canvas
from .v5101_exact_print import (
    DEFAULT_PRINT_RADIUS_MM, OVERLAY_ROLE, PRINT_RADIUS_ROLE,
    PRINT_ZONE_ROLE, WORKBOARD_ROLE, _label_source_rect, _logical_item_rect,
)
from .v54_assets_session import _is_user_item
from .v604_alignment_multiselect import _rebuild_transform_controller

PRINT_W_PX = 320.0
PRINT_H_PX = 96.0
WORK_MARGIN_X = 56.0
WORK_MARGIN_Y = 48.0
SCENE_MARGIN_X = 110.0
SCENE_MARGIN_Y = 90.0


def _path_item(rect: QRectF, radius: float, fill: str, stroke: str, width: float, role: int):
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    item = QGraphicsPathItem(path)
    item.setBrush(QBrush(QColor(fill)))
    pen = QPen(QColor(stroke), width)
    pen.setCosmetic(True)
    item.setPen(pen)
    item.setAcceptedMouseButtons(Qt.NoButton)
    item.setFlag(QGraphicsItem.ItemIsSelectable, False)
    item.setFlag(QGraphicsItem.ItemIsMovable, False)
    item.setData(OVERLAY_ROLE, True)
    item.setData(role, True)
    return item


def _same_rect(a: QRectF, b: QRectF, tol=2.0):
    return (
        abs(a.x() - b.x()) <= tol
        and abs(a.y() - b.y()) <= tol
        and abs(a.width() - b.width()) <= tol
        and abs(a.height() - b.height()) <= tol
    )


def _remove_legacy_page(scene, old_rect: QRectF):
    for item in list(scene.items()):
        try:
            if item.data(PRINT_ZONE_ROLE) or item.data(WORKBOARD_ROLE):
                continue
            if item.data(OVERLAY_ROLE):
                continue
            if _is_user_item(item):
                continue
            if not isinstance(item, (QGraphicsRectItem, QGraphicsPathItem)):
                continue
            if not hasattr(item, "brush"):
                continue
            color = item.brush().color()
            if color.alpha() < 230 or min(color.red(), color.green(), color.blue()) < 225:
                continue
            rect = _logical_item_rect(item)
            if _same_rect(rect, old_rect, tol=3.0):
                scene.removeItem(item)
        except Exception:
            pass


def _existing(scene, role):
    for item in scene.items():
        try:
            if item.data(role):
                return item
        except Exception:
            pass
    return None


def _ensure_workspace(window, recenter=False):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return
    scene = view.scene()

    zone = _existing(scene, PRINT_ZONE_ROLE)
    if zone is not None:
        print_rect = _logical_item_rect(zone)
    else:
        # Preserve the exact coordinates of the old 40x12 page so existing
        # designs/autosave sessions do not jump when upgrading to V6.0.5.
        old_rect = _label_source_rect(scene)
        if (
            old_rect.isNull()
            or old_rect.width() < 250
            or old_rect.height() < 70
            or old_rect.width() > 380
            or old_rect.height() > 140
        ):
            old_rect = QRectF(0, 0, PRINT_W_PX, PRINT_H_PX)
        print_rect = QRectF(old_rect.x(), old_rect.y(), PRINT_W_PX, PRINT_H_PX)
        _remove_legacy_page(scene, old_rect)

    board_rect = print_rect.adjusted(
        -WORK_MARGIN_X, -WORK_MARGIN_Y, WORK_MARGIN_X, WORK_MARGIN_Y
    )
    scene_rect = board_rect.adjusted(
        -SCENE_MARGIN_X, -SCENE_MARGIN_Y, SCENE_MARGIN_X, SCENE_MARGIN_Y
    )

    board = _existing(scene, WORKBOARD_ROLE)
    if board is None:
        board = _path_item(
            board_rect, 10.0, "#D9DCE1", "#5C6067", 1.0, WORKBOARD_ROLE
        )
        board.setZValue(-1_000_100)
        scene.addItem(board)
    else:
        path = QPainterPath()
        path.addRoundedRect(board_rect, 10.0, 10.0)
        board.setPath(path)

    zone = _existing(scene, PRINT_ZONE_ROLE)
    radius_px = DEFAULT_PRINT_RADIUS_MM * 203.0 / 25.4
    if zone is None:
        zone = _path_item(
            print_rect, radius_px, "#FFFFFF", "#7C8189", 1.2, PRINT_ZONE_ROLE
        )
        zone.setData(PRINT_RADIUS_ROLE, DEFAULT_PRINT_RADIUS_MM)
        zone.setZValue(-1_000_000)
        scene.addItem(zone)
    else:
        path = QPainterPath()
        path.addRoundedRect(print_rect, radius_px, radius_px)
        zone.setPath(path)
        zone.setData(PRINT_RADIUS_ROLE, DEFAULT_PRINT_RADIUS_MM)

    caption = getattr(window, "_v605_print_caption", None)
    if caption is None or caption.scene() is not scene:
        caption = QGraphicsSimpleTextItem("Área imprimible · 40 × 12 mm")
        caption.setData(OVERLAY_ROLE, True)
        caption.setData(WORKBOARD_ROLE, True)
        caption.setBrush(QBrush(QColor("#666B73")))
        font = QFont()
        font.setPointSizeF(8.5)
        font.setBold(True)
        caption.setFont(font)
        caption.setAcceptedMouseButtons(Qt.NoButton)
        caption.setZValue(-999_999)
        scene.addItem(caption)
        window._v605_print_caption = caption
    caption.setPos(print_rect.left(), board_rect.top() + 10)

    scene.setSceneRect(scene_rect)
    window._v605_print_zone = zone
    window._v605_workboard = board
    window._v605_print_rect = QRectF(print_rect)
    window._v605_scene_rect = QRectF(scene_rect)

    if recenter:
        view.centerOn(print_rect.center())


def _refresh_transform_tools(window):
    # Autosave/session restoration happens after MainWindow construction.
    # Rebuild the selection controller afterwards so handles always bind to
    # the restored scene/items, not to the pre-restore selection state.
    try:
        _rebuild_transform_controller(window)
    except Exception:
        controller = getattr(window, "_v55_transform_controller", None)
        if controller is not None:
            try:
                controller.refresh_selection()
                controller.refresh_geometry(force=True)
            except Exception:
                pass

    multi = getattr(window, "_v604_multi_select", None)
    if multi is not None:
        try:
            multi.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            multi.view.setRubberBandSelectionMode(Qt.ItemSelectionMode.ContainsItemShape)
            multi.refresh_outline()
        except Exception:
            pass


def enhance(window):
    _ensure_workspace(window, recenter=True)

    # v54 restores the session at ~350 ms. Enforce the new artboard after it,
    # then rebuild visual selection handles on the restored objects.
    QTimer.singleShot(650, lambda: _ensure_workspace(window, recenter=True))
    QTimer.singleShot(780, lambda: _refresh_transform_tools(window))
    QTimer.singleShot(1600, lambda: _ensure_workspace(window, recenter=False))

    window.statusBar().showMessage(
        "V6.0.5 · mesa de trabajo nueva · área imprimible redondeada 40×12 mm",
        7000,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v605_workspace_installed", False):
        return
    MainWindow._v605_workspace_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
