import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v510-")

import shiboken6
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsTextItem, QSlider

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas
from phomemo_studio.v510_print_designs import _load_index, load_design, save_design

w = MainWindow()
QApplication.processEvents()

# V5.1 must keep the hidden legacy central widget alive. The printer backend
# still reads legacy controls (including sliders) even though the modern UI
# displays proxies/new controls.
legacy = getattr(w, "_v51_legacy_central", None)
assert legacy is not None
assert shiboken6.isValid(legacy)
legacy_sliders = legacy.findChildren(QSlider)
for slider in legacy_sliders:
    assert shiboken6.isValid(slider)
    slider.value()

# Direct QSlider attributes kept by the backend must also remain valid.
for value in vars(w).values():
    if isinstance(value, QSlider):
        assert shiboken6.isValid(value)
        value.value()

# Packing the current label is the exact pre-print path that previously raised
# "Internal C++ object (QSlider) already deleted".
pack = getattr(w, "_pack_current", None)
assert callable(pack)
packets = pack()
assert packets is not None

# Real persistent Designs library.
view = _find_canvas(w)
assert view is not None and view.scene() is not None
scene = view.scene()

item = QGraphicsTextItem("Diseño persistente V5.10")
item.setFlags(
    QGraphicsItem.ItemIsMovable
    | QGraphicsItem.ItemIsSelectable
    | QGraphicsItem.ItemIsFocusable
)
item.setPos(77, 44)
scene.addItem(item)

design_id = save_design(w, "Etiqueta guardada")
assert design_id
index = _load_index()
assert any(e.get("id") == design_id and e.get("name") == "Etiqueta guardada" for e in index)
assert getattr(w, "_v510_design_count").text().startswith("1 ")

scene.removeItem(item)
assert not any(
    isinstance(x, QGraphicsTextItem) and "Diseño persistente V5.10" in x.toPlainText()
    for x in scene.items()
)
assert load_design(w, design_id)
restored = [
    x for x in scene.items()
    if isinstance(x, QGraphicsTextItem) and "Diseño persistente V5.10" in x.toPlainText()
]
assert restored
assert abs(restored[0].pos().x() - 77) < 0.01

w.close()
QApplication.processEvents()

# Library survives a complete window close/reopen.
w2 = MainWindow()
assert any(e.get("name") == "Etiqueta guardada" for e in _load_index())
assert "1 diseño" in getattr(w2, "_v510_design_count").text()
w2.close()

print("V5.10 print QSlider lifetime + persistent Designs library smoke OK")
