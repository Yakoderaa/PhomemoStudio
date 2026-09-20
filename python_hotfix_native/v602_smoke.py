import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v602-")

from PySide6.QtWidgets import QApplication, QFrame, QMenu, QPushButton

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow

w = MainWindow()
QApplication.processEvents()

import inspect
print("V603_DIAG_START")
for _name in ("add_to_queue", "print_queue", "_pack_current", "print_current"):
    _obj = getattr(type(w), _name, None)
    print("METHOD", _name)
    try:
        print(inspect.getsource(_obj))
    except Exception as _exc:
        print("METHOD_ERROR", _name, repr(_exc))
_original_pack = getattr(type(w), "_v5101_original_pack_current", None)
_globals = getattr(_original_pack, "__globals__", {}) if callable(_original_pack) else {}
for _name in ("make_print_packet", "image_to_d30_raster"):
    _obj = _globals.get(_name)
    print("GLOBAL", _name)
    try:
        print(inspect.getsource(_obj))
    except Exception as _exc:
        print("GLOBAL_ERROR", _name, repr(_exc))
for _attr in ("density", "feed", "continuous"):
    _w = getattr(w, _attr, None)
    try:
        print("WIDGET", _attr, type(_w).__name__, "value", _w.value() if hasattr(_w,"value") else _w.isChecked(), "min", _w.minimum() if hasattr(_w,"minimum") else None, "max", _w.maximum() if hasattr(_w,"maximum") else None)
    except Exception as _exc:
        print("WIDGET_ERROR", _attr, repr(_exc))
print("V603_DIAG_END")

header = w.findChild(QFrame, "v51Header")
assert header is not None
header_texts = {b.text().replace("&","").strip().casefold() for b in header.findChildren(QPushButton)}
assert "guardar" not in header_texts
assert "duplicar" not in header_texts
assert "png" not in header_texts

# Designs keeps its own save/duplicate buttons.
pages = getattr(w, "_v51_drawer_pages")
designs = pages.get("Diseños")
assert designs is not None
design_texts = {b.text().replace("&","").strip().casefold() for b in designs.findChildren(QPushButton)}
assert "guardar diseño" in design_texts or "guardar" in design_texts, design_texts
assert "duplicar" in design_texts, design_texts

# Images no longer exposes Export PNG directly.
images = pages.get("Imágenes")
assert images is not None
image_texts = {b.text().replace("&","").strip().casefold() for b in images.findChildren(QPushButton)}
assert "exportar png" not in image_texts
assert "png" not in image_texts

# File > Save As > PNG.
archivo = None
for action in w.menuBar().actions():
    if action.text().replace("&","").strip().casefold() == "archivo":
        archivo = action.menu()
        break
assert archivo is not None
guardar_como = getattr(w, "_v602_save_as_menu", None)
assert guardar_como is not None
assert guardar_como.title().replace("&","").strip().casefold() == "guardar como"
assert any(a.menu() is guardar_como for a in archivo.actions())
png_actions = [a for a in guardar_como.actions() if a.text().replace("&","").strip().casefold().startswith("png")]
assert len(png_actions) == 1
assert png_actions[0].isEnabled()

w.close()
print("V6.0.2 header cleanup + File/Save As/PNG smoke OK")
