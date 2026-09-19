from __future__ import annotations

import json

from PySide6.QtCore import QEvent, QObject, QRectF, QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QGraphicsItem, QGraphicsTextItem, QMenu

from .studio_pro import _find_canvas
from .v54_assets_session import _is_user_item, _restore_item, _serialize_item, save_session

OVERLAY_ROLE = 1098
MAX_HISTORY = 80


def _capture(window):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return None
    scene = view.scene()
    rect = scene.sceneRect()
    items = []
    for item in reversed(scene.items()):
        if item.data(OVERLAY_ROLE):
            continue
        if not _is_user_item(item):
            continue
        data = _serialize_item(item)
        if data is not None:
            items.append(data)
    return {
        "scene_rect": [float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height())],
        "items": items,
    }


def _fingerprint(state) -> str:
    return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class _ExclusiveSelectionFilter(QObject):
    """Keep canvas selection exclusive and release stale text edit focus."""

    def __init__(self, window, view, parent=None):
        super().__init__(parent)
        self.window = window
        self.view = view
        self.scene = view.scene()

    def _release_text(self, item):
        if not isinstance(item, QGraphicsTextItem):
            return
        try:
            cursor = item.textCursor()
            cursor.clearSelection()
            item.setTextCursor(cursor)
        except Exception:
            pass
        try:
            item.clearFocus()
        except Exception:
            pass
        try:
            item.setTextInteractionFlags(Qt.NoTextInteraction)
        except Exception:
            pass

    def prepare_switch(self, target, modifiers):
        if self.scene is None or target is None or target.data(OVERLAY_ROLE):
            return

        # Release every other text item's internal cursor/focus. This fixes the
        # blue selection highlight that can otherwise remain after choosing a
        # different image/shape/line.
        for item in self.scene.items():
            if isinstance(item, QGraphicsTextItem) and item is not target:
                self._release_text(item)

        # Normal click behaves like Illustrator: one active object. Ctrl/Shift
        # keep Qt's multi-selection semantics available.
        if not (modifiers & (Qt.ControlModifier | Qt.ShiftModifier)):
            for item in list(self.scene.selectedItems()):
                if item is not target and not item.data(OVERLAY_ROLE):
                    item.setSelected(False)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and getattr(event, "button", lambda: None)() == Qt.LeftButton:
            try:
                scene_pos = self.view.mapToScene(event.position().toPoint())
                target = self.scene.itemAt(scene_pos, self.view.transform())
                self.prepare_switch(target, event.modifiers())
            except Exception:
                pass
        return False


class _CanvasReleaseFilter(QObject):
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.history = history

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.MouseButtonRelease, QEvent.TabletRelease):
            QTimer.singleShot(0, self.history.commit)
        return False


class HistoryManager(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.view = _find_canvas(window)
        self.scene = self.view.scene() if self.view is not None else None
        self.undo_stack = []
        self.redo_stack = []
        self._applying = False
        self._initialized = False

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(420)
        self.timer.timeout.connect(self.commit)

        self.undo_action = QAction("Deshacer", window)
        self.undo_action.setObjectName("v57UndoAction")
        self.undo_action.setShortcuts([QKeySequence("Ctrl+Z")])
        self.undo_action.setShortcutContext(Qt.ApplicationShortcut)
        self.undo_action.triggered.connect(self.undo)

        self.redo_action = QAction("Rehacer", window)
        self.redo_action.setObjectName("v57RedoAction")
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.redo_action.setShortcutContext(Qt.ApplicationShortcut)
        self.redo_action.triggered.connect(self.redo)

        window.addAction(self.undo_action)
        window.addAction(self.redo_action)
        self._install_menu()

        if self.scene is not None:
            self.scene.changed.connect(self.schedule)
        if self.view is not None:
            self.selection_filter = _ExclusiveSelectionFilter(window, self.view, self.view.viewport())
            self.view.viewport().installEventFilter(self.selection_filter)
            window._v57_selection_filter = self.selection_filter

            self.release_filter = _CanvasReleaseFilter(self, self.view.viewport())
            self.view.viewport().installEventFilter(self.release_filter)
        else:
            self.selection_filter = None
            self.release_filter = None

        self._hook_transform_gestures()
        self._update_actions()
        # V5.4 restores the autosave shortly after window creation. Capture the
        # restored document as the first history state, not the temporary empty scene.
        QTimer.singleShot(900, self.initialize)

    def _install_menu(self):
        bar = self.window.menuBar()
        edit = None
        for action in bar.actions():
            menu = action.menu()
            if menu and action.text().replace("&", "").strip().casefold() in ("editar", "edit"):
                edit = menu
                break
        if edit is None:
            edit = QMenu("Editar", bar)
            actions = bar.actions()
            before = actions[1] if len(actions) > 1 else None
            if before is not None:
                bar.insertMenu(before, edit)
            else:
                bar.addMenu(edit)
        edit.insertAction(edit.actions()[0] if edit.actions() else None, self.undo_action)
        edit.insertAction(
            edit.actions()[1] if len(edit.actions()) > 1 else None,
            self.redo_action,
        )
        if len(edit.actions()) == 2:
            edit.addSeparator()
        self.window._v57_edit_menu = edit

    def _hook_transform_gestures(self):
        controller = getattr(self.window, "_v55_transform_controller", None)
        if controller is None:
            return
        if not getattr(controller, "_v57_history_resize_hook", False):
            original = controller.end_resize

            def end_resize():
                original()
                QTimer.singleShot(0, self.commit)

            controller.end_resize = end_resize
            controller._v57_history_resize_hook = True

        if hasattr(controller, "end_rotate") and not getattr(controller, "_v57_history_rotate_hook", False):
            original_rotate = controller.end_rotate

            def end_rotate():
                original_rotate()
                QTimer.singleShot(0, self.commit)

            controller.end_rotate = end_rotate
            controller._v57_history_rotate_hook = True

    def initialize(self):
        if self._initialized:
            return
        state = _capture(self.window)
        if state is None:
            return
        self.undo_stack = [state]
        self.redo_stack = []
        self._initialized = True
        self._update_actions()

    def schedule(self, *_args):
        if self._applying:
            return
        self.timer.start()

    def commit(self):
        if self._applying:
            return
        state = _capture(self.window)
        if state is None:
            return
        if not self._initialized:
            self.undo_stack = [state]
            self.redo_stack = []
            self._initialized = True
            self._update_actions()
            return

        if self.undo_stack and _fingerprint(state) == _fingerprint(self.undo_stack[-1]):
            self._update_actions()
            return

        self.undo_stack.append(state)
        if len(self.undo_stack) > MAX_HISTORY:
            self.undo_stack = self.undo_stack[-MAX_HISTORY:]
        self.redo_stack.clear()
        self._update_actions()

    def _apply(self, state):
        if self.scene is None:
            return
        self._applying = True
        try:
            self.timer.stop()
            self.scene.clearSelection()
            for item in list(self.scene.items()):
                if item.data(OVERLAY_ROLE):
                    continue
                if _is_user_item(item):
                    self.scene.removeItem(item)

            rect = state.get("scene_rect")
            if isinstance(rect, list) and len(rect) == 4:
                self.scene.setSceneRect(QRectF(*[float(v) for v in rect]))

            for data in state.get("items", []):
                if not isinstance(data, dict):
                    continue
                item = _restore_item(data)
                if item is not None:
                    self.scene.addItem(item)

            controller = getattr(self.window, "_v55_transform_controller", None)
            if controller is not None:
                controller.target = None
                controller.refresh_selection()

            binder = getattr(self.window, "_v56_text_binder", None)
            if binder is not None:
                binder.sync_from_selection()

            save_session(self.window, announce=False)
        finally:
            self._applying = False
        self._update_actions()

    def undo(self):
        # Capture a just-finished gesture even if its debounce timer has not fired yet.
        self.timer.stop()
        self.commit()
        if len(self.undo_stack) <= 1:
            self.window.statusBar().showMessage("No hay más acciones para deshacer", 1800)
            return
        current = self.undo_stack.pop()
        self.redo_stack.append(current)
        self._apply(self.undo_stack[-1])
        self.window.statusBar().showMessage("Deshacer", 1200)

    def redo(self):
        self.timer.stop()
        if not self.redo_stack:
            self.window.statusBar().showMessage("No hay acciones para rehacer", 1800)
            return
        state = self.redo_stack.pop()
        self.undo_stack.append(state)
        self._apply(state)
        self.window.statusBar().showMessage("Rehacer", 1200)

    def _update_actions(self):
        self.undo_action.setEnabled(len(self.undo_stack) > 1)
        self.redo_action.setEnabled(bool(self.redo_stack))


def enhance(window):
    manager = HistoryManager(window)
    window._v57_history = manager
    window.statusBar().showMessage(
        "V5.7 · Ctrl+Z Deshacer · Ctrl+Y / Ctrl+Shift+Z Rehacer",
        5000,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v57_history_installed", False):
        return
    MainWindow._v57_history_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
