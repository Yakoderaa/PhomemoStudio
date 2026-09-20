import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v602-")

from PySide6.QtWidgets import QApplication, QFrame, QMenu, QPushButton

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow

w = MainWindow()
QApplication.processEvents()

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
