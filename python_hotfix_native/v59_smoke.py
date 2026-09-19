import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v59-")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QPushButton

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.v56_text_lines_rotation import insert_line

w = MainWindow()

# Permanent Properties button must restore the inspector after hiding it.
inspector = getattr(w, "_v51_inspector", None)
button = w.findChild(QPushButton, "v59ShowPropertiesButton")
assert inspector is not None
assert button is not None
inspector.hide()
assert inspector.isHidden()
button.click()
QApplication.processEvents()
assert not inspector.isHidden()

# A line gets ONLY left/right resize handles.
line = insert_line(w, "Línea", "solid")
controller = getattr(w, "_v55_transform_controller", None)
assert controller is not None
controller.refresh_selection()
controller.refresh_geometry(True)
assert controller.target is line

visible_resize = {k for k, h in controller.handles.items() if h.isVisible()}
assert visible_resize == {"l", "r"}, visible_resize

# Changing length via the right handle must not change stroke width or height.
before_pen = line.pen().widthF()
before_rect = line.boundingRect()
right = line.mapToScene(QPointF(before_rect.right(), before_rect.center().y()))
further = line.mapToScene(QPointF(before_rect.right() + 120.0, before_rect.center().y()))
controller.begin_resize("r", right, Qt.NoModifier)
controller.resize_to(further, Qt.NoModifier)
controller.end_resize()
QApplication.processEvents()

after_rect = line.boundingRect()
assert after_rect.width() > before_rect.width() + 80.0, (before_rect.width(), after_rect.width())
assert abs(after_rect.height() - before_rect.height()) < 0.25, (before_rect.height(), after_rect.height())
assert abs(line.pen().widthF() - before_pen) < 0.001

# Vertical/corner resize attempts are disabled for lines.
transform_before = line.transform()
controller.begin_resize("t", line.mapToScene(QPointF(after_rect.center().x(), after_rect.top())), Qt.NoModifier)
assert controller.drag_kind is None
assert line.transform() == transform_before

# Thickness remains exclusively controlled from Properties.
props = getattr(w, "_v58_line_properties", None)
assert props is not None
props.sync()
props.width.setValue(7.0)
props.apply(7.0)
assert abs(line.pen().widthF() - 7.0) < 0.01

w.close()
print("V5.9 Properties restore + line length-only resize smoke OK")
