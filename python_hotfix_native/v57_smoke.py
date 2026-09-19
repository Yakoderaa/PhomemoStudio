import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v57-")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication, QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem, QToolButton
)

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas

w = MainWindow()
view = _find_canvas(w)
assert view is not None and view.scene() is not None
scene = view.scene()

history = getattr(w, "_v57_history", None)
assert history is not None
history.initialize()
assert any(s.toString() == "Ctrl+Z" for s in history.undo_action.shortcuts())
redo_keys = {s.toString() for s in history.redo_action.shortcuts()}
assert "Ctrl+Y" in redo_keys
assert "Ctrl+Shift+Z" in redo_keys

item = QGraphicsRectItem(0, 0, 80, 50)
item.setPen(QPen(QColor("#111111"), 2))
item.setBrush(QBrush(QColor("#dddddd")))
item.setFlags(
    QGraphicsItem.ItemIsMovable
    | QGraphicsItem.ItemIsSelectable
    | QGraphicsItem.ItemIsFocusable
)
scene.addItem(item)
item.setPos(10, 20)
history.commit()

item.setPos(120, 90)
history.commit()
assert abs(item.pos().x() - 120) < 0.01

history.undo()
rects = [
    x for x in scene.items()
    if isinstance(x, QGraphicsRectItem)
    and not x.data(1098)
    and (x.flags() & QGraphicsItem.ItemIsSelectable)
]
assert rects
assert abs(rects[0].pos().x() - 10) < 0.01
assert history.redo_action.isEnabled()

history.redo()
rects = [
    x for x in scene.items()
    if isinstance(x, QGraphicsRectItem)
    and not x.data(1098)
    and (x.flags() & QGraphicsItem.ItemIsSelectable)
]
assert rects
assert abs(rects[0].pos().x() - 120) < 0.01

# Visible alignment choices and live application to selected text.
buttons = getattr(w, "_v56_alignment_buttons", None)
assert buttons and len(buttons) == 4
labels = {button.text() for button, _value in buttons}
assert {"Izq.", "Centro", "Der.", "Justif."}.issubset(labels)

text = QGraphicsTextItem("Uno\nDos")
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
alignment = binder.fields["alineacion"]
alignment.setCurrentText("Centro")
binder.apply("alineacion")
assert text.textCursor().blockFormat().alignment() & Qt.AlignHCenter

alignment.setCurrentText("Derecha")
binder.apply("alineacion")
assert text.textCursor().blockFormat().alignment() & Qt.AlignRight

alignment.setCurrentText("Justificado")
binder.apply("alineacion")
assert text.textCursor().blockFormat().alignment() & Qt.AlignJustify

# Live text updates must happen while the item remains selected.
content = binder.fields["contenido"]
content.setPlainText("Cambio en vivo")
binder.apply("contenido")
assert text.toPlainText() == "Cambio en vivo"
assert text.isSelected()

size = binder.fields["tamano"]
size.setValue(31)
binder.apply("tamano")
assert abs(text.font().pointSizeF() - 31) < 0.1
assert text.isSelected()

# Clicking/switching to another object must release text focus/selection.
text.setTextInteractionFlags(Qt.TextEditorInteraction)
text.setFocus()
other = QGraphicsRectItem(0, 0, 40, 30)
other.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
scene.addItem(other)
selection_filter = getattr(w, "_v57_selection_filter", None)
assert selection_filter is not None
selection_filter.prepare_switch(other, Qt.NoModifier)
other.setSelected(True)
assert other.isSelected()
assert not text.isSelected()
assert not text.hasFocus()
assert text.textInteractionFlags() == Qt.NoTextInteraction

w.close()
print("V5.7 undo/redo + alignment + live text + exclusive selection smoke OK")
