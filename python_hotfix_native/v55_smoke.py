import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
root = tempfile.mkdtemp(prefix="phomemo-v55-")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = root

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QBrush, QPen, QTransform
from PySide6.QtWidgets import (
    QApplication, QGraphicsItem, QGraphicsRectItem
)

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas
from phomemo_studio.v54_assets_session import _session_path, restore_session, save_session
from phomemo_studio.v55_transform_handles import OVERLAY_ROLE

w = MainWindow()
view = _find_canvas(w)
assert view is not None and view.scene() is not None
scene = view.scene()
controller = getattr(w, "_v55_transform_controller", None)
assert controller is not None
assert len(controller.handles) == 8

item = QGraphicsRectItem(0, 0, 100, 50)
item.setPen(QPen(QColor("#111111"), 2))
item.setBrush(QBrush(QColor("#dddddd")))
item.setFlags(
    QGraphicsItem.ItemIsMovable
    | QGraphicsItem.ItemIsSelectable
    | QGraphicsItem.ItemIsFocusable
)
item.setPos(30, 40)
scene.addItem(item)
item.setSelected(True)
controller.refresh_selection()
assert controller.target is item
assert all(h.isVisible() for h in controller.handles.values())

# Free corner resize: opposite corner must remain anchored.
rect = item.boundingRect()
anchor_before = item.mapToScene(rect.topLeft())
controller.begin_resize("br", item.mapToScene(rect.bottomRight()), Qt.NoModifier)
controller.resize_to(item.mapToScene(QPointF(160, 90)), Qt.NoModifier)
controller.end_resize()
anchor_after = item.mapToScene(rect.topLeft())
assert (anchor_after - anchor_before).manhattanLength() < 0.05
br_after = item.mapToScene(rect.bottomRight())
assert br_after.x() > anchor_after.x() + 120
assert br_after.y() > anchor_after.y() + 60

# Shift keeps proportions.
item.setTransform(QTransform())
controller.refresh_geometry(True)
controller.begin_resize("br", item.mapToScene(rect.bottomRight()), Qt.ShiftModifier)
controller.resize_to(item.mapToScene(QPointF(160, 100)), Qt.ShiftModifier)
controller.end_resize()
t = item.transform()
assert abs(abs(t.m11()) - abs(t.m22())) < 0.02
assert abs(t.m11()) > 1.5

# Side handles resize a single axis.
item.setTransform(QTransform())
controller.refresh_geometry(True)
controller.begin_resize("r", item.mapToScene(QPointF(rect.right(), rect.center().y())), Qt.NoModifier)
controller.resize_to(item.mapToScene(QPointF(180, rect.center().y())), Qt.NoModifier)
controller.end_resize()
t = item.transform()
assert abs(t.m11()) > 1.7
assert abs(t.m22() - 1.0) < 0.02

# Alt scales around the centre; Shift+Alt keeps proportions around the centre.
item.setTransform(QTransform())
center_before = item.mapToScene(rect.center())
controller.refresh_geometry(True)
controller.begin_resize("br", item.mapToScene(rect.bottomRight()), Qt.AltModifier | Qt.ShiftModifier)
controller.resize_to(item.mapToScene(QPointF(150, 75)), Qt.AltModifier | Qt.ShiftModifier)
controller.end_resize()
center_after = item.mapToScene(rect.center())
assert (center_after - center_before).manhattanLength() < 0.05
t = item.transform()
assert abs(abs(t.m11()) - abs(t.m22())) < 0.02
assert abs(t.m11()) > 1.9

# The transformation matrix must survive autosave/restoration.
assert save_session(w)
payload = json.loads(_session_path().read_text(encoding="utf-8"))
assert payload["items"]
assert all(not entry.get("data_kind") == "v55-overlay" for entry in payload["items"])
for overlay in [controller.outline, *controller.handles.values()]:
    assert overlay.data(OVERLAY_ROLE)

for scene_item in list(scene.items()):
    if scene_item is item:
        scene.removeItem(scene_item)

assert restore_session(w)
restored = [
    x for x in scene.items()
    if isinstance(x, QGraphicsRectItem)
    and not x.data(OVERLAY_ROLE)
    and (x.flags() & QGraphicsItem.ItemIsSelectable)
]
assert restored
rt = restored[0].transform()
assert abs(abs(rt.m11()) - abs(rt.m22())) < 0.02
assert abs(rt.m11()) > 1.9

# Selection UI can be hidden for export/print and restored afterward.
controller.refresh_selection()
controller.set_overlay_visible(False)
assert not controller.outline.isVisible()
assert not any(h.isVisible() for h in controller.handles.values())
controller.set_overlay_visible(True)

for name in ("export_png", "print_current"):
    fn = getattr(type(w), name, None)
    if callable(fn):
        assert getattr(fn, "_v55_overlay_safe", False)

w.close()
print("V5.5 Illustrator-style resize handles + modifiers + autosave smoke OK")
