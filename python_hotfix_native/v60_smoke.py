import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v60-")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsTextItem, QLabel, QListWidget, QTabWidget
)

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.v5101_exact_print import _label_source_rect
from phomemo_studio.v58_text_clipboard_layers import set_item_locked

w = MainWindow()
QApplication.processEvents()

# Illustrator-style overall structure.
right = w.findChild(QFrame, "v60RightPanel")
tabs = w.findChild(QTabWidget, "v60RightTabs")
assert right is not None
assert tabs is not None
assert [tabs.tabText(i) for i in range(tabs.count())] == ["Propiedades", "Capas", "Cola"]

rail = w.findChild(QFrame, "v51Rail")
drawer = getattr(w, "_v51_drawer", None)
assert rail is not None and rail.width() == 58
assert drawer is not None and drawer.maximumWidth() <= 320

buttons = getattr(w, "_v51_nav_buttons")
for name in ("Diseños", "Texto", "Formas", "Imágenes"):
    assert buttons[name].isVisible() or not w.isVisible()
for name in ("Cola", "Capas"):
    if name in buttons:
        assert buttons[name].isHidden()

# Printer status remains in top header even with the new workspace.
status = w.findChild(QFrame, "v5103PrinterStatus")
assert status is not None
for attr in ("connect_btn", "battery", "paper", "roll_status"):
    widget = getattr(w, attr)
    assert widget.parentWidget() is status

# Layers are on the right and clearly differentiate selected/locked states.
layers = getattr(w, "_v58_layers")
assert layers is not None
scene = layers.scene
text = QGraphicsTextItem("Capa seleccionada")
text.setFlags(
    QGraphicsItem.ItemIsMovable
    | QGraphicsItem.ItemIsSelectable
    | QGraphicsItem.ItemIsFocusable
)
scene.addItem(text)
scene.clearSelection()
text.setSelected(True)
layers.refresh(force=True)

listing = layers.list
assert isinstance(listing, QListWidget) and listing.count() >= 1
selected_styles = []
selected_labels = []
for i in range(listing.count()):
    row = listing.itemWidget(listing.item(i))
    if row:
        selected_styles.append(row.styleSheet())
        selected_labels.extend(lbl.text() for lbl in row.findChildren(QLabel))
assert any("#294D75" in style for style in selected_styles), selected_styles
assert any("SELEC." in label for label in selected_labels), selected_labels

set_item_locked(w, text, True)
layers.refresh(force=True)
locked_styles = []
locked_labels = []
for i in range(listing.count()):
    row = listing.itemWidget(listing.item(i))
    if row:
        locked_styles.append(row.styleSheet())
        locked_labels.extend(lbl.text() for lbl in row.findChildren(QLabel))
assert any("#3A332A" in style for style in locked_styles), locked_styles
assert any("BLOQ." in label for label in locked_labels), locked_labels

# Print crop must choose the physical white label, not the gray workspace.
probe = QGraphicsScene()
probe.setSceneRect(QRectF(0, 0, 1000, 700))
page = QGraphicsRectItem(QRectF(120, 210, 500, 150))
page.setBrush(QBrush(QColor("#FFFFFF")))
page.setPen(QPen(QColor("#BFC2C8"), 1))
probe.addItem(page)

source = _label_source_rect(probe)
assert abs(source.x() - 120.0) < 1.0, source
assert abs(source.y() - 210.0) < 1.0, source
assert abs(source.width() - 500.0) < 2.0, source
assert abs(source.height() - 150.0) < 2.0, source
assert source.width() < probe.sceneRect().width()
assert source.height() < probe.sceneRect().height()

w.close()
print("V6 Illustrator-style workspace + clear layers + physical-label print crop smoke OK")
