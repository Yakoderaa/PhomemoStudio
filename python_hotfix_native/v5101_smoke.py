import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v5101-")

from PIL import ImageStat
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QBrush, QImage, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QGraphicsEllipseItem, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsTextItem
)

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas
from phomemo_studio.v5101_exact_print import render_visible_label, orient_for_d30

w = MainWindow()
view = _find_canvas(w)
assert view is not None and view.scene() is not None
scene = view.scene()

# Force a known landscape source area comparable to the user's long label.
scene.setSceneRect(QRectF(0, 0, 500, 150))
for item in list(scene.items()):
    if not item.data(1098):
        try:
            scene.removeItem(item)
        except Exception:
            pass

# Left: raster image
img = QImage(72, 72, QImage.Format_ARGB32)
img.fill(Qt.black)
pix = QGraphicsPixmapItem(QPixmap.fromImage(img))
pix.setPos(25, 38)
pix.setFlags(pix.flags() | pix.ItemIsSelectable | pix.ItemIsMovable)
scene.addItem(pix)

# Centre: text
text = QGraphicsTextItem("Vainilla\nChips negras")
text.setDefaultTextColor(QColor("black"))
text.setPos(185, 30)
text.setFlags(text.flags() | text.ItemIsSelectable | text.ItemIsMovable)
scene.addItem(text)

# Right: shape + line/frame fragment
ellipse = QGraphicsEllipseItem(420, 30, 55, 55)
ellipse.setBrush(QBrush(QColor("black")))
ellipse.setPen(QPen(Qt.NoPen))
ellipse.setFlags(ellipse.flags() | ellipse.ItemIsSelectable | ellipse.ItemIsMovable)
scene.addItem(ellipse)

frame = QGraphicsRectItem(8, 8, 484, 134)
frame.setPen(QPen(QColor("black"), 2))
frame.setBrush(Qt.NoBrush)
frame.setFlags(frame.flags() | frame.ItemIsSelectable | frame.ItemIsMovable)
scene.addItem(frame)

# Use a landscape label option if the legacy size combo has one.
combo = getattr(w, "size_combo", None)
if combo is not None:
    for i in range(combo.count()):
        data = combo.itemData(i)
        try:
            if data and float(data[0]) > float(data[1]):
                combo.setCurrentIndex(i)
                break
        except Exception:
            pass

original = getattr(type(w), "_v5101_original_pack_current", None)
assert callable(original)
assert type(w)._pack_current is not original

# Exact scene render must preserve content across the full width, including
# imported/raster items and vector items, before printer orientation.
globals_ = getattr(original, "__globals__", {})
label_pixels = globals_.get("label_pixels")
design = render_visible_label(w, label_pixels)
assert design.width > design.height, design.size
gray = design.convert("L")

third = design.width // 3
left_mean = ImageStat.Stat(gray.crop((0, 0, third, design.height))).mean[0]
mid_mean = ImageStat.Stat(gray.crop((third, 0, third * 2, design.height))).mean[0]
right_mean = ImageStat.Stat(gray.crop((third * 2, 0, design.width, design.height))).mean[0]
assert left_mean < 250, left_mean
assert mid_mean < 254, mid_mean
assert right_mean < 250, right_mean

printer = orient_for_d30(design)
assert printer.width == design.height
assert printer.height == design.width
assert printer.width < printer.height

packets = w._pack_current()
assert isinstance(packets, list) and len(packets) == 3
assert packets[0] == bytes([0x1F, 0x11, 0x24, 0x00])
cmd = packets[1]
assert cmd[:6] == bytes([0x1B, 0x40, 0x1D, 0x76, 0x30, 0x00])
width_bytes = cmd[6] | (cmd[7] << 8)
height_px = cmd[8] | (cmd[9] << 8)
debug = getattr(w, "_v5101_last_print_debug")
assert debug["rotated"] is True
assert debug["printer_size"][0] < debug["printer_size"][1]
assert width_bytes == (debug["raster_size"][0] + 7) // 8
assert height_px == debug["raster_size"][1]
assert len(packets[2]) == width_bytes * height_px

w.close()
print("V5.10.1 exact full-scene print + D30 landscape orientation smoke OK")
