import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v591-")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.v56_text_lines_rotation import insert_line

w = MainWindow()
line = insert_line(w, "Línea", "solid")
controller = getattr(w, "_v55_transform_controller", None)
assert controller is not None

line.setRotation(90.0)
controller.refresh_selection()
controller.refresh_geometry(True)
assert controller.target is line

visible_resize = {k for k, h in controller.handles.items() if h.isVisible()}
assert visible_resize == {"l", "r"}, visible_resize

before_pen = line.pen().widthF()
before_path_rect = line.path().boundingRect()
before_scene_rect = line.sceneBoundingRect()

# Drag the logical right endpoint further along the line's rotated axis.
right_local = QPointF(before_path_rect.right(), before_path_rect.center().y())
right_scene = line.mapToScene(right_local)
further_local = QPointF(before_path_rect.right() + 140.0, before_path_rect.center().y())
further_scene = line.mapToScene(further_local)

controller.begin_resize("r", right_scene, Qt.NoModifier)
controller.resize_to(further_scene, Qt.NoModifier)
controller.end_resize()
QApplication.processEvents()

after_path_rect = line.path().boundingRect()
after_scene_rect = line.sceneBoundingRect()

assert line.rotation() == 90.0
assert after_path_rect.width() > before_path_rect.width() + 100.0
# At 90°, increasing local line length increases scene height, not thickness/width.
assert after_scene_rect.height() > before_scene_rect.height() + 100.0
assert abs(after_scene_rect.width() - before_scene_rect.width()) < 0.5
assert abs(line.pen().widthF() - before_pen) < 0.001

# Same endpoint logic must work at an arbitrary angle too.
line.setRotation(37.0)
controller.refresh_geometry(True)
rect2 = line.path().boundingRect()
left_scene = line.mapToScene(QPointF(rect2.left(), rect2.center().y()))
shorter_scene = line.mapToScene(QPointF(rect2.left() + 45.0, rect2.center().y()))
width_before = rect2.width()

controller.begin_resize("l", left_scene, Qt.NoModifier)
controller.resize_to(shorter_scene, Qt.NoModifier)
controller.end_resize()
QApplication.processEvents()

assert line.rotation() == 37.0
assert line.path().boundingRect().width() < width_before
assert abs(line.pen().widthF() - before_pen) < 0.001

w.close()
print("V5.9.1 rotated/vertical line endpoint resize smoke OK")
