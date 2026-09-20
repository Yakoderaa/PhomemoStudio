import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v601-")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QToolButton

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas
from phomemo_studio.v5101_exact_print import _label_source_rect, render_visible_label

w = MainWindow()
QApplication.processEvents()

# Physical label truth: 40 x 12 mm at 203 dpi => ~320 x 96 px.
assert tuple(w.size_combo.currentData()) == (40, 12), w.size_combo.currentData()

view = _find_canvas(w)
scene = view.scene()
source = _label_source_rect(scene)
assert abs(source.width() - 320.0) < 0.01, source
assert abs(source.height() - 96.0) < 0.01, source

original = getattr(type(w), "_v5101_original_pack_current", None)
assert callable(original)
globals_ = getattr(original, "__globals__", {})
label_pixels = globals_.get("label_pixels")
assert callable(label_pixels)
assert tuple(label_pixels(40, 12)) == (320, 96), label_pixels(40, 12)

rendered = render_visible_label(w, label_pixels)
assert rendered.size == (320, 96), rendered.size

image_to_d30_raster = globals_.get("image_to_d30_raster")
assert callable(image_to_d30_raster)
raster, rw, rh = image_to_d30_raster(rendered)
assert (rw, rh) == (96, 320), (rw, rh)

# Zoom buttons must modify the actual QGraphicsView transform.
bar = w.findChild(QFrame, "v51CanvasBar")
label = w.findChild(QLabel, "v51ZoomLabel")
controller = getattr(w, "_v601_zoom_controller", None)
assert controller is not None
assert bar is not None and label is not None

plus = next(b for b in bar.findChildren(QToolButton) if b.text().strip() == "+")
minus = next(b for b in bar.findChildren(QToolButton) if b.text().strip() in ("−", "-"))
reset = next(b for b in bar.findChildren(QPushButton) if b.text().strip() == "100%")

controller.set_zoom(100)
assert abs(view.transform().m11() - 1.0) < 0.001
plus.click()
QApplication.processEvents()
assert label.text() == "110%", label.text()
assert abs(view.transform().m11() - 1.1) < 0.001, view.transform().m11()
minus.click()
QApplication.processEvents()
assert label.text() == "100%"
assert abs(view.transform().m11() - 1.0) < 0.001
controller.set_zoom(170)
assert abs(view.transform().m11() - 1.7) < 0.001
reset.click()
QApplication.processEvents()
assert label.text() == "100%"
assert abs(view.transform().m11() - 1.0) < 0.001

# V6.0.1 must append a global dark rule; the white label is a scene item,
# not a white QWidget island.
style = w.styleSheet()
assert "QMainWindow QWidget" in style
assert "background:#2B2B2B" in style
assert "QFrame#v51CanvasHost" in style

w.close()
print("V6.0.1 40x12 exact print mapping + dark UI + functional zoom smoke OK")
