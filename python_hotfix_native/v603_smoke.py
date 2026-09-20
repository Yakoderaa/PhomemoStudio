import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v603-")

from PIL import Image
from PySide6.QtWidgets import QApplication, QComboBox, QFrame

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.v603_print_queue_concentration import (
    DENSITY_LEVELS,
    LABEL_40X12_X_OFFSET_PX,
    _apply_d30_alignment,
)

w = MainWindow()
QApplication.processEvents()

assert tuple(w.size_combo.currentData()) == (40, 12)

# Concentration is a separate header control immediately before printer status.
combo = w.findChild(QComboBox, "v603Concentration")
box = w.findChild(QFrame, "v603ConcentrationBox")
status = w.findChild(QFrame, "v5103PrinterStatus")
header = w.findChild(QFrame, "v51Header")
assert combo is not None and box is not None and status is not None and header is not None
assert header.layout().indexOf(box) < header.layout().indexOf(status)

for name, expected in DENSITY_LEVELS.items():
    combo.setCurrentText(name)
    QApplication.processEvents()
    assert w.density.value() == expected, (name, w.density.value(), expected)

# Mechanical compensation for 40x12 is exactly one millimetre at 203 dpi.
assert LABEL_40X12_X_OFFSET_PX == -8
probe = Image.new("L", (320, 96), 255)
for y in range(10, 20):
    probe.putpixel((20, y), 0)
aligned = _apply_d30_alignment(w, probe)
assert aligned.getpixel((12, 10)) == 0
assert aligned.getpixel((20, 10)) == 255

# Normal print goes through the compensated raster.
combo.setCurrentText("Estándar")
normal_packets = w._pack_current()
debug = getattr(w, "_v603_last_print_debug")
assert debug["design_size"] == (320, 96), debug
assert debug["raster_size"] == (96, 320), debug
assert debug["offset_x"] == -8, debug
assert debug["density"] == 6, debug

# Queue stores the exact same raster route as normal print.
queue = getattr(w, "_v603_queue", None)
assert queue is not None
queue.clear()
queue.add_current()
assert len(queue.jobs) == 1
queue_packets = queue.packets_for_all()
assert queue_packets == w._pack_current(), "Queue and normal print packets differ"

# Changing concentration affects both paths identically at print time.
combo.setCurrentText("Concentrada")
assert w.density.value() == 8
assert queue.packets_for_all() == w._pack_current()

w.close()
print("V6.0.3 centered 40x12 print + concentration + unified queue smoke OK")
