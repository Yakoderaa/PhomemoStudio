import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
root = tempfile.mkdtemp(prefix="phomemo-v54-")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = root

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainterPath, QBrush, QPen
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsPathItem, QGraphicsPixmapItem, QGraphicsTextItem, QTabWidget

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas
from phomemo_studio.v54_assets_session import (
    ROLE_KIND, _import_paths, _load_library, _session_path, restore_session, save_session
)

w = MainWindow()
tabs = w.findChild(QTabWidget, "v54ImageLibraryTabs")
assert tabs is not None and tabs.count() == 2
assert tabs.tabText(0) == "Biblioteca"

sample = Path(root) / "sample.png"
img = QImage(80, 50, QImage.Format_ARGB32)
img.fill(QColor("#3355aa"))
assert img.save(str(sample), "PNG")

entries = _import_paths(w, [str(sample)], insert=True)
assert len(entries) == 1
assert len(_load_library()) == 1

view = _find_canvas(w)
assert view is not None and view.scene() is not None
images = [i for i in view.scene().items() if isinstance(i, QGraphicsPixmapItem) and i.data(ROLE_KIND) == "imported-image"]
assert images and not images[0].pixmap().isNull()
images[0].setPos(123.0, 45.0)
images[0].setRotation(17.0)

text = QGraphicsTextItem("Sesión V5.4")
text.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
text.setPos(22.0, 33.0)
view.scene().addItem(text)

path = QPainterPath()
path.moveTo(0, 0)
path.cubicTo(20, 5, 30, 40, 55, 60)
path.lineTo(4, 70)
path.closeSubpath()
vector = QGraphicsPathItem(path)
vector.setPen(QPen(QColor("#111111"), 2))
vector.setBrush(QBrush(QColor("#dddddd")))
vector.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
vector.setPos(70.0, 80.0)
view.scene().addItem(vector)

assert save_session(w)
assert _session_path().exists()

for item in list(view.scene().items()):
    flags = item.flags()
    if item.data(ROLE_KIND) or (flags & (QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)):
        view.scene().removeItem(item)

assert restore_session(w)
restored_images = [i for i in view.scene().items() if isinstance(i, QGraphicsPixmapItem) and i.data(ROLE_KIND) == "imported-image"]
restored_text = [i for i in view.scene().items() if isinstance(i, QGraphicsTextItem) and "Sesión V5.4" in i.toPlainText()]
assert restored_images and not restored_images[0].pixmap().isNull()
assert abs(restored_images[0].pos().x() - 123.0) < 0.01
assert abs(restored_images[0].rotation() - 17.0) < 0.01
assert restored_text
assert any(isinstance(i, QGraphicsPathItem) for i in view.scene().items())
assert getattr(w, "_v54_save_timer").isSingleShot()
assert getattr(w, "_v54_periodic_timer").isActive()

w.close()
print("V5.4 persistent image library + autosave/restore smoke OK")
