import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v605-")

from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication, QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem, QGraphicsView
)

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas
from phomemo_studio.v5101_exact_print import (
    DEFAULT_PRINT_RADIUS_MM, PRINT_RADIUS_ROLE, PRINT_ZONE_ROLE, WORKBOARD_ROLE,
    _label_source_rect, _print_zone_item, render_visible_label,
)
from phomemo_studio.v56_text_lines_rotation import insert_line
from phomemo_studio.v603_print_queue_concentration import (
    _image_to_d30_dithered_raster,
)
from phomemo_studio.v605_canvas_workspace import (
    _ensure_workspace, _refresh_transform_tools,
)

w = MainWindow()
QApplication.processEvents()
_ensure_workspace(w, recenter=False)
QApplication.processEvents()

view = _find_canvas(w)
assert view is not None and view.scene() is not None
scene = view.scene()

zone = _print_zone_item(scene)
assert zone is not None
assert bool(zone.data(PRINT_ZONE_ROLE))
assert abs(float(zone.data(PRINT_RADIUS_ROLE)) - DEFAULT_PRINT_RADIUS_MM) < 0.01

source = _label_source_rect(scene)
assert abs(source.width() - 320.0) < 0.01, source
assert abs(source.height() - 96.0) < 0.01, source
assert scene.sceneRect().width() > source.width() + 150
assert scene.sceneRect().height() > source.height() + 120

boards = [it for it in scene.items() if it.data(WORKBOARD_ROLE) and not it.data(PRINT_ZONE_ROLE)]
assert boards
assert any(it.sceneBoundingRect().width() > source.width() for it in boards)

# Rounded geometry is genuinely rounded, not a rectangular visual shortcut.
local_path = zone.path()
local_rect = local_path.boundingRect()
assert local_path.contains(local_rect.center())
assert not local_path.contains(QPointF(local_rect.left() + 1, local_rect.top() + 1))

# The renderer uses only the explicit print zone and clips its rounded corners.
cover = QGraphicsRectItem(QRectF(source))
cover.setBrush(QBrush(QColor("black")))
cover.setPen(Qt.NoPen)
cover.setZValue(100)
scene.addItem(cover)
rendered = render_visible_label(w)
assert rendered.size == (320, 96), rendered.size
assert rendered.getpixel((160, 48)) < 10
assert rendered.getpixel((0, 0)) > 245
assert rendered.getpixel((319, 0)) > 245
assert rendered.getpixel((0, 95)) > 245
assert rendered.getpixel((319, 95)) > 245
scene.removeItem(cover)

# Ordered thermal halftone is deterministic and neither all-white nor all-black.
gray = Image.new("L", (320, 96), 170)
r1, rw1, rh1 = _image_to_d30_dithered_raster(w, gray)
r2, rw2, rh2 = _image_to_d30_dithered_raster(w, gray)
assert (rw1, rh1) == (96, 320)
assert (rw2, rh2) == (96, 320)
assert r1 == r2
black_bits = sum(bin(byte).count("1") for byte in r1)
assert 0 < black_bits < rw1 * rh1

# Rebuild after session restore must restore visible resize/rotation controls.
text = QGraphicsTextItem("Tiradores")
text.setFlags(
    QGraphicsItem.ItemIsMovable
    | QGraphicsItem.ItemIsSelectable
    | QGraphicsItem.ItemIsFocusable
)
text.setPos(source.left() + 80, source.top() + 30)
scene.addItem(text)
scene.clearSelection()
text.setSelected(True)
_refresh_transform_tools(w)
QApplication.processEvents()
controller = getattr(w, "_v55_transform_controller", None)
assert controller is not None
controller.refresh_selection()
controller.refresh_geometry(force=True)
visible = {k for k, h in controller.handles.items() if h.isVisible()}
assert visible == {"tl", "t", "tr", "r", "br", "b", "bl", "l"}, visible
rotate = getattr(controller, "rotate_handles", {})
assert len(rotate) == 4 and all(h.isVisible() for h in rotate.values())

# A line has only the two length endpoints plus rotation; thickness is properties-only.
line = insert_line(w, "Línea", "solid")
QApplication.processEvents()
controller.refresh_selection()
controller.refresh_geometry(force=True)
visible_line = {k for k, h in controller.handles.items() if h.isVisible()}
assert visible_line == {"l", "r"}, visible_line
assert all(h.isVisible() for h in controller.rotate_handles.values())

multi = getattr(w, "_v604_multi_select", None)
assert multi is not None
assert view.dragMode() == QGraphicsView.DragMode.RubberBandDrag
assert view.rubberBandSelectionMode() == Qt.ItemSelectionMode.ContainsItemShape

# Re-enforcing the workspace must not create duplicate print zones.
_ensure_workspace(w, recenter=False)
zones = [it for it in scene.items() if it.data(PRINT_ZONE_ROLE)]
assert len(zones) == 1, len(zones)

w.close()
print("V6.0.5 rebuilt canvas + rounded print zone + halftone + transform handles smoke OK")
