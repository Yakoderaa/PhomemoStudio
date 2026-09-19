import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v58-")

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTransform, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QGraphicsItem, QGraphicsPathItem, QGraphicsTextItem, QStackedWidget
)

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas
from phomemo_studio.v54_assets_session import _serialize_item
from phomemo_studio.v56_text_lines_rotation import insert_line
from phomemo_studio.v58_text_clipboard_layers import (
    ROLE_LOCKED, _normalize_line_geometry, set_item_locked
)

w = MainWindow()
view = _find_canvas(w)
scene = view.scene()

# Text formatting must affect the full document live.
text = QGraphicsTextItem("Linea uno\nLinea dos")
text.setFlags(
    QGraphicsItem.ItemIsMovable
    | QGraphicsItem.ItemIsSelectable
    | QGraphicsItem.ItemIsFocusable
)
scene.addItem(text)
scene.clearSelection()
text.setSelected(True)

binder = getattr(w, "_v56_text_binder")
binder.sync_from_selection()

weight = binder.fields["grosor"]
weight.setCurrentIndex(max(0, weight.findData(700)))
binder.apply("grosor")
assert int(text.font().weight()) >= 700

tracking = binder.fields["espaciado"]
tracking.setValue(3.5)
binder.apply("espaciado")
assert text.font().letterSpacingType() == QFont.AbsoluteSpacing
assert abs(text.font().letterSpacing() - 3.5) < 0.1

leading = binder.fields["interlineado"]
leading.setValue(1.8)
binder.apply("interlineado")
block = text.document().begin()
while block.isValid():
    assert abs(block.blockFormat().lineHeight() - 180.0) < 0.5
    block = block.next()

align = binder.fields["alineacion"]
align.setCurrentText("Derecha")
binder.apply("alineacion")
block = text.document().begin()
while block.isValid():
    assert block.blockFormat().alignment() & Qt.AlignRight
    block = block.next()

# Clipboard shortcuts and Illustrator Ctrl+B paste-behind.
clip = getattr(w, "_v58_clipboard")
assert clip.copy_action.shortcut().toString() == "Ctrl+C"
assert clip.paste_action.shortcut().toString() == "Ctrl+V"
assert clip.paste_back_action.shortcut().toString() == "Ctrl+B"

scene.clearSelection()
text.setSelected(True)
clip.copy()
before = len([x for x in scene.items() if isinstance(x, QGraphicsTextItem) and not x.data(1098)])
clip.paste(True)
after = len([x for x in scene.items() if isinstance(x, QGraphicsTextItem) and not x.data(1098)])
assert after == before + 1

# Line width stays independent from length scaling after geometry normalization.
line = insert_line(w, "Línea", "solid")
assert isinstance(line, QGraphicsPathItem)
pen_width = line.pen().widthF()
line.setTransform(QTransform().scale(2.5, 1.0))
assert _normalize_line_geometry(line)
assert line.transform().isIdentity()
assert abs(line.pen().widthF() - pen_width) < 0.001
assert line.boundingRect().width() > 400

line_props = getattr(w, "_v58_line_properties")
scene.clearSelection()
line.setSelected(True)
line_props.sync()
line_props.width.setValue(5.25)
line_props.apply(5.25)
assert abs(line.pen().widthF() - 5.25) < 0.01

# Layers page + lock persistence.
pages = getattr(w, "_v51_drawer_pages")
assert "Capas" in pages
stack = w.findChild(QStackedWidget, "v51DrawerStack")
assert stack is not None
layers = getattr(w, "_v58_layers")
assert layers is not None

set_item_locked(w, line, True)
assert bool(line.data(ROLE_LOCKED))
assert not (line.flags() & QGraphicsItem.ItemIsMovable)
assert not (line.flags() & QGraphicsItem.ItemIsSelectable)
saved = _serialize_item(line)
assert saved and saved.get("locked") is True

set_item_locked(w, line, False)
assert not bool(line.data(ROLE_LOCKED))
assert line.flags() & QGraphicsItem.ItemIsMovable
assert line.flags() & QGraphicsItem.ItemIsSelectable

w.close()
print("V5.8 text formatting + clipboard + line width + layers smoke OK")
