import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v604-")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QApplication, QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem
)

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas
from phomemo_studio.v5101_exact_print import _label_source_rect
from phomemo_studio.v56_text_lines_rotation import insert_line
from phomemo_studio.v604_alignment_multiselect import align_selection

w = MainWindow()
QApplication.processEvents()
view = _find_canvas(w)
scene = view.scene()
multi = getattr(w, "_v604_multi_select", None)
controller = getattr(w, "_v55_transform_controller", None)
assert multi is not None
assert controller is not None
assert getattr(w, "_v604_alignment_card", None) is not None

# Clear user items but keep the white label/background/overlays.
for it in list(scene.items()):
    if it.data(1098):
        continue
    if it.flags() & QGraphicsItem.ItemIsSelectable:
        try:
            scene.removeItem(it)
        except Exception:
            pass

# Normal object gets 8 resize handles + 4 rotate handles.
text = QGraphicsTextItem("Objeto")
text.setFlags(
    QGraphicsItem.ItemIsMovable |
    QGraphicsItem.ItemIsSelectable |
    QGraphicsItem.ItemIsFocusable
)
text.setPos(70, 30)
scene.addItem(text)
scene.clearSelection()
text.setSelected(True)
controller.refresh_selection()
controller.refresh_geometry(True)
visible = {k for k, h in controller.handles.items() if h.isVisible()}
assert visible == {"tl","t","tr","r","br","b","bl","l"}, visible
assert len(getattr(controller, "rotate_handles", {})) == 4
assert all(h.isVisible() for h in controller.rotate_handles.values())

# Lines keep only two length handles, plus rotation controls.
line = insert_line(w, "Línea", "solid")
QApplication.processEvents()
controller.refresh_selection()
controller.refresh_geometry(True)
visible_line = {k for k, h in controller.handles.items() if h.isVisible()}
assert visible_line == {"l", "r"}, visible_line
assert all(h.isVisible() for h in controller.rotate_handles.values())

# Single-object alignment centers object against the exact physical label.
scene.clearSelection()
text.setSelected(True)
assert align_selection(w, "center")
label = _label_source_rect(scene)
assert abs(text.sceneBoundingRect().center().x() - label.center().x()) < 0.5
assert abs(text.sceneBoundingRect().center().y() - label.center().y()) < 0.5

# Multi-selection alignment treats the selection as a group.
second = QGraphicsTextItem("Dos")
second.setFlags(
    QGraphicsItem.ItemIsMovable |
    QGraphicsItem.ItemIsSelectable |
    QGraphicsItem.ItemIsFocusable
)
second.setPos(210, 55)
scene.addItem(second)
scene.clearSelection()
text.setSelected(True)
second.setSelected(True)
before_dx = second.scenePos().x() - text.scenePos().x()
assert align_selection(w, "top")
after_dx = second.scenePos().x() - text.scenePos().x()
assert abs(after_dx - before_dx) < 0.01
group = text.sceneBoundingRect().united(second.sceneBoundingRect())
assert abs(group.top() - label.top()) < 0.6
assert abs(group.center().x() - label.center().x()) < 0.6

# Rubber-band selection is enabled for box selection.
assert view.dragMode() == view.RubberBandDrag
assert view.rubberBandSelectionMode() == Qt.ContainsItemShape

# Ctrl+A selects all unlocked user items.
scene.clearSelection()
multi.select_all()
selected = multi.selected()
assert text in selected and second in selected and line in selected

# Shift-click add, Ctrl-click toggle, Alt drag duplicate and Shift orthogonal drag.
class FakeMouse:
    def __init__(self, typ, pos, mods=Qt.NoModifier, button=Qt.LeftButton, buttons=Qt.LeftButton):
        self._typ = typ
        self._pos = QPointF(pos)
        self._mods = mods
        self._button = button
        self._buttons = buttons
        self.accepted = False
    def type(self): return self._typ
    def position(self): return self._pos
    def modifiers(self): return self._mods
    def button(self): return self._button
    def buttons(self): return self._buttons
    def accept(self): self.accepted = True

def vp(scene_point):
    return QPointF(view.mapFromScene(scene_point))

# Shift-click adds second to an existing selection without clearing text.
scene.clearSelection()
text.setSelected(True)
p2 = vp(second.sceneBoundingRect().center())
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseButtonPress, p2, Qt.ShiftModifier))
multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseButtonRelease, p2, Qt.ShiftModifier, buttons=Qt.NoButton))
assert text.isSelected() and second.isSelected()

# Ctrl-click removes one item from the group.
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseButtonPress, p2, Qt.ControlModifier))
assert text.isSelected() and not second.isSelected()

# Alt drag duplicates the selected object and moves the duplicate.
scene.clearSelection()
text.setSelected(True)
start = vp(text.sceneBoundingRect().center())
end = QPointF(start.x() + 55, start.y() + 22)
before_texts = len([i for i in scene.items() if isinstance(i, QGraphicsTextItem)])
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseButtonPress, start, Qt.AltModifier))
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseMove, end, Qt.AltModifier))
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseButtonRelease, end, Qt.AltModifier, buttons=Qt.NoButton))
after_texts = len([i for i in scene.items() if isinstance(i, QGraphicsTextItem)])
assert after_texts == before_texts + 1

# Shift drag constrains movement to the dominant horizontal axis.
clone = next(i for i in multi.selected() if isinstance(i, QGraphicsTextItem))
clone_start = QPointF(clone.pos())
sp = vp(clone.sceneBoundingRect().center())
ep = QPointF(sp.x() + 60, sp.y() + 18)
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseButtonPress, sp, Qt.ShiftModifier))
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseMove, ep, Qt.ShiftModifier))
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseButtonRelease, ep, Qt.ShiftModifier, buttons=Qt.NoButton))
assert clone.pos().x() > clone_start.x() + 40
assert abs(clone.pos().y() - clone_start.y()) < 0.5

# Alt+Shift duplicates while moving orthogonally.
scene.clearSelection()
clone.setSelected(True)
count_before = len([i for i in scene.items() if isinstance(i, QGraphicsTextItem)])
sp = vp(clone.sceneBoundingRect().center())
ep = QPointF(sp.x() + 15, sp.y() + 65)
mods = Qt.AltModifier | Qt.ShiftModifier
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseButtonPress, sp, mods))
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseMove, ep, mods))
assert multi.eventFilter(multi.viewport, FakeMouse(QEvent.MouseButtonRelease, ep, mods, buttons=Qt.NoButton))
count_after = len([i for i in scene.items() if isinstance(i, QGraphicsTextItem)])
assert count_after == count_before + 1
new_clone = next(i for i in multi.selected() if isinstance(i, QGraphicsTextItem))
assert abs(new_clone.pos().x() - clone.pos().x()) < 0.5
assert new_clone.pos().y() > clone.pos().y() + 45

# Delete removes the entire current selection.
scene.clearSelection()
text.setSelected(True)
second.setSelected(True)
before_count = len(scene.items())
multi.delete_selected()
assert text.scene() is None and second.scene() is None
assert len(scene.items()) <= before_count - 2

w.close()
print("V6.0.4 alignment + handles + multiselect + Alt/Shift drag smoke OK")
