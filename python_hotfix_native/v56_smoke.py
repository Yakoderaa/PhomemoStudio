import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v56-")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QGraphicsItem, QGraphicsPathItem, QGraphicsTextItem,
    QLineEdit, QSpinBox, QDoubleSpinBox, QTabWidget, QTextEdit, QPlainTextEdit
)

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas
from phomemo_studio.v56_text_lines_rotation import insert_line

w = MainWindow()
view = _find_canvas(w)
assert view is not None and view.scene() is not None
scene = view.scene()

binder = getattr(w, "_v56_text_binder", None)
assert binder is not None
assert {"contenido", "fuente", "tamano"}.issubset(set(binder.fields)), binder.fields.keys()

text_item = QGraphicsTextItem("Texto original")
text_item.setFlags(
    QGraphicsItem.ItemIsMovable
    | QGraphicsItem.ItemIsSelectable
    | QGraphicsItem.ItemIsFocusable
)
scene.addItem(text_item)
scene.clearSelection()
text_item.setSelected(True)
binder.sync_from_selection()

content = binder.fields["contenido"]
if isinstance(content, QLineEdit):
    content.setText("Texto actualizado")
elif isinstance(content, (QTextEdit, QPlainTextEdit)):
    content.setPlainText("Texto actualizado")
else:
    raise AssertionError(type(content))
binder.apply("contenido")
assert text_item.toPlainText() == "Texto actualizado"

font_combo = binder.fields["fuente"]
assert isinstance(font_combo, QComboBox)
family = font_combo.itemText(0) if font_combo.count() else text_item.font().family()
font_combo.setCurrentText(family)
binder.apply("fuente")
assert text_item.font().family()

size = binder.fields["tamano"]
assert isinstance(size, (QSpinBox, QDoubleSpinBox))
size.setValue(28)
binder.apply("tamano")
assert abs(text_item.font().pointSizeF() - 28) < 0.1

# Lines library must exist and add real editable vector items.
tabs = w.findChild(QTabWidget, "v52OpenLibraryTabs")
assert tabs is not None
names = [tabs.tabText(i) for i in range(tabs.count())]
assert "Líneas" in names, names
line = insert_line(w, "Discontinua", "dash")
assert isinstance(line, QGraphicsPathItem)
assert line.data(1001) == "studio-line"
assert line.flags() & QGraphicsItem.ItemIsSelectable
assert not line.path().isEmpty()

# Four external-corner rotate zones, separate from the eight resize handles.
controller = getattr(w, "_v55_transform_controller", None)
assert controller is not None
assert len(controller.handles) == 8
assert len(getattr(controller, "rotate_handles", {})) == 4

scene.clearSelection()
line.setSelected(True)
controller.refresh_selection()
controller.refresh_geometry(True)
assert controller.target is line
assert all(h.isVisible() for h in controller.rotate_handles.values())

center = line.mapToScene(line.boundingRect().center())
start = QPointF(center.x() + 100, center.y())
end = QPointF(center.x(), center.y() + 100)
controller.begin_rotate(start)
controller.rotate_to(end, Qt.NoModifier)
controller.end_rotate()
assert abs(line.rotation() - 90.0) < 1.0, line.rotation()

line.setRotation(0)
controller.refresh_geometry(True)
controller.begin_rotate(start)
controller.rotate_to(QPointF(center.x() + 70, center.y() + 70), Qt.ShiftModifier)
controller.end_rotate()
assert abs(line.rotation() - 45.0) < 1.0, line.rotation()

w.close()
print("V5.6 live text + lines library + free corner rotation smoke OK")
