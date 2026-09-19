from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtWidgets import QGraphicsPathItem, QPushButton

from .studio_pro import _find_canvas

ROLE_KIND = 1001
OVERLAY_ROLE = 1098


def _is_line(item):
    return isinstance(item, QGraphicsPathItem) and item.data(ROLE_KIND) == "studio-line"


def _install_properties_restore_button(window):
    if getattr(window, "_v59_properties_button", None) is not None:
        return

    header = window.findChild(type(window._v51_update_button) if hasattr(window, "_v51_update_button") else QPushButton, "v51UpdateButton")
    # The header button itself is easier to find through its parent/layout.
    if header is None:
        header = window.findChild(QPushButton, "v51UpdateButton")
    if header is None or header.parentWidget() is None or header.parentWidget().layout() is None:
        return

    button = QPushButton("Propiedades")
    button.setObjectName("v59ShowPropertiesButton")
    button.setToolTip("Mostrar el panel de Propiedades")
    button.setProperty("role", "secondary")
    button.clicked.connect(lambda: _show_properties(window))

    layout = header.parentWidget().layout()
    index = layout.indexOf(header)
    layout.insertWidget(max(0, index), button)
    window._v59_properties_button = button


def _show_properties(window):
    inspector = getattr(window, "_v51_inspector", None)
    if inspector is None:
        return
    inspector.show()
    inspector.raise_()
    try:
        from PySide6.QtCore import QSettings
        QSettings("Yakoderaa", "PhomemoStudio").setValue("ui/inspectorVisible", True)
    except Exception:
        pass


def _install_line_length_only_resize(window):
    controller = getattr(window, "_v55_transform_controller", None)
    if controller is None or getattr(controller, "_v59_line_length_only", False):
        return
    controller._v59_line_length_only = True

    original_refresh = controller.refresh_geometry
    original_begin = controller.begin_resize
    original_resize = controller.resize_to
    original_end = controller.end_resize

    def refresh_geometry(force=False):
        original_refresh(force=force)
        target = controller.target
        if not _is_line(target):
            return

        # Lines are length-only objects on canvas: only the left and right
        # midpoint handles are available. Thickness lives in Properties.
        for kind, handle in controller.handles.items():
            handle.setVisible(kind in ("l", "r") and controller.outline.isVisible())

    def begin_resize(kind, scene_pos, modifiers):
        target = controller.target
        if _is_line(target) and kind not in ("l", "r"):
            controller.drag_kind = None
            return
        return original_begin(kind, scene_pos, modifiers)

    def resize_to(scene_pos, modifiers):
        target = controller.target
        if not _is_line(target):
            return original_resize(scene_pos, modifiers)
        if controller.drag_kind not in ("l", "r"):
            return

        # Ignore Shift for line resizing: a line has no editable height here.
        # Alt is preserved so users can lengthen/shorten symmetrically from centre.
        safe_modifiers = modifiers & Qt.AltModifier
        return original_resize(scene_pos, safe_modifiers)

    def end_resize():
        target = controller.target
        original_end()
        # V5.8 converts the horizontal scale into actual path geometry while
        # preserving QPen width. Refresh once more so only L/R handles remain.
        if _is_line(target):
            QTimer.singleShot(0, lambda: refresh_geometry(True))

    controller.refresh_geometry = refresh_geometry
    controller.begin_resize = begin_resize
    controller.resize_to = resize_to
    controller.end_resize = end_resize

    # V5.5/V5.6 timers may still reference older bound refresh callables.
    try:
        controller.timer.timeout.connect(lambda: refresh_geometry(False))
    except Exception:
        pass
    refresh_geometry(True)


def enhance(window):
    _install_properties_restore_button(window)
    _install_line_length_only_resize(window)
    window.statusBar().showMessage(
        "V5.9 · botón Propiedades permanente · líneas: sólo alargar/acortar desde el lienzo",
        5500,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v59_installed", False):
        return
    MainWindow._v59_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
