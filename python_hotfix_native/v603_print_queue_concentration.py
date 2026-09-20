from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PIL import Image
from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout
)

from .v5101_exact_print import render_visible_label


# The visible white 40x12 mm canvas is the complete usable print area.
# Never shift/crop the artwork behind the user's back.
LABEL_40X12_X_OFFSET_PX = 0

DENSITY_LEVELS = {
    "Liviana": 3,
    "Estándar": 6,
    "Concentrada": 8,
}


def _printer_globals(window):
    original = getattr(type(window), "_v5101_original_pack_current", None)
    if not callable(original):
        raise RuntimeError("No encontré la ruta original de impresión D30.")
    g = getattr(original, "__globals__", {})
    label_pixels = g.get("label_pixels")
    image_to_d30_raster = g.get("image_to_d30_raster")
    make_print_packet = g.get("make_print_packet")
    if not callable(label_pixels) or not callable(image_to_d30_raster) or not callable(make_print_packet):
        raise RuntimeError("No están disponibles las funciones de impresión D30.")
    return label_pixels, image_to_d30_raster, make_print_packet


def _physical_size(window):
    try:
        data = window.size_combo.currentData()
        return float(data[0]), float(data[1])
    except Exception:
        return 40.0, 12.0


def _apply_d30_alignment(window, image: Image.Image) -> Image.Image:
    """WYSIWYG: the white canvas already is the entire usable physical label."""
    return image.convert("L")


STIPPLE_THRESHOLD = 205

BAYER_8X8 = (
    (0, 48, 12, 60, 3, 51, 15, 63),
    (32, 16, 44, 28, 35, 19, 47, 31),
    (8, 56, 4, 52, 11, 59, 7, 55),
    (40, 24, 36, 20, 43, 27, 39, 23),
    (2, 50, 14, 62, 1, 49, 13, 61),
    (34, 18, 46, 30, 33, 17, 45, 29),
    (10, 58, 6, 54, 9, 57, 5, 53),
    (42, 26, 38, 22, 41, 25, 37, 21),
)


def _pack_black_rows(rows):
    """Pack True=black pixels as ESC/POS MSB-first raster bytes."""
    height = len(rows)
    width = len(rows[0]) if height else 0
    width_bytes = (width + 7) // 8
    out = bytearray(width_bytes * height)
    for y, row in enumerate(rows):
        base = y * width_bytes
        for x, black in enumerate(row):
            if black:
                out[base + (x >> 3)] |= 0x80 >> (x & 7)
    return bytes(out), width, height


def _intentional_stipple_mask(gray: Image.Image) -> Image.Image:
    """
    Detect small isolated dark components already present in the artwork.

    These are treated as intentional stippling rather than continuous gray.
    The mask is slightly reinforced so single-pixel/very small dots survive
    the 203 dpi thermal transfer.
    """
    src = gray.convert("L")
    w, h = src.size
    px = src.load()
    visited = bytearray(w * h)
    mask = Image.new("1", (w, h), 0)
    out = mask.load()

    def idx(x, y):
        return y * w + x

    for sy in range(h):
        for sx in range(w):
            i0 = idx(sx, sy)
            if visited[i0] or px[sx, sy] > STIPPLE_THRESHOLD:
                continue

            stack = [(sx, sy)]
            visited[i0] = 1
            comp = []
            minx = maxx = sx
            miny = maxy = sy

            while stack:
                x, y = stack.pop()
                comp.append((x, y))
                minx = min(minx, x); maxx = max(maxx, x)
                miny = min(miny, y); maxy = max(maxy, y)

                # Always traverse the full component so a large shape cannot
                # be split into artificial "small dots" on later scans.
                for ny in range(max(0, y - 1), min(h, y + 2)):
                    for nx in range(max(0, x - 1), min(w, x + 2)):
                        if nx == x and ny == y:
                            continue
                        ii = idx(nx, ny)
                        if not visited[ii] and px[nx, ny] <= STIPPLE_THRESHOLD:
                            visited[ii] = 1
                            stack.append((nx, ny))

            bw = maxx - minx + 1
            bh = maxy - miny + 1
            if 1 <= len(comp) <= 18 and bw <= 7 and bh <= 7:
                # Preserve the original component. Very tiny dots are expanded
                # to at least a 2px footprint so the thermal head can show them.
                reinforce = 1 if len(comp) <= 4 else 0
                for x, y in comp:
                    for yy in range(max(0, y - reinforce), min(h, y + reinforce + 1)):
                        for xx in range(max(0, x - reinforce), min(w, x + reinforce + 1)):
                            out[xx, yy] = 1

    return mask


def _image_to_d30_dithered_raster(window, image: Image.Image):
    """
    Ordered 8x8 thermal halftone.

    Pure black/white remain exact. Intermediate tones become a regular dot
    density. Packing is done directly instead of delegating to the legacy
    threshold converter, so the halftone cannot collapse back to solid black.
    """
    gray = image.convert("L")
    stipple = _intentional_stipple_mask(gray)
    rot = gray.transpose(Image.Transpose.ROTATE_270)
    stipple_rot = stipple.transpose(Image.Transpose.ROTATE_270)
    w, h = rot.size
    px = rot.load()
    stipple_px = stipple_rot.load()
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            value = int(px[x, y])
            if stipple_px[x, y]:
                # User-authored stipple/dot: preserve it as a real thermal dot.
                black = True
            elif value <= 28:
                black = True
            elif value >= 250:
                black = False
            else:
                threshold = ((BAYER_8X8[y & 7][x & 7] + 0.5) * 255.0) / 64.0
                black = value < threshold
            row.append(black)
        rows.append(row)
    return _pack_black_rows(rows)

def _current_raster(window):
    label_pixels, _image_to_d30_raster, _make_print_packet = _printer_globals(window)
    design = render_visible_label(window, label_pixels)
    aligned = _apply_d30_alignment(window, design)
    raster, rw, rh = _image_to_d30_dithered_raster(window, aligned)
    return {
        "design_size": tuple(design.size),
        "aligned_size": tuple(aligned.size),
        "raster": bytes(raster),
        "rw": int(rw),
        "rh": int(rh),
        "offset_x": 0,
        "dither": "Ordered Bayer 8x8 + stipple preservation",
    }


def _pack_from_raster(window, job):
    _label_pixels, _image_to_d30_raster, make_print_packet = _printer_globals(window)
    return make_print_packet(
        job["raster"],
        int(job["rw"]),
        int(job["rh"]),
        int(window.density.value()),
        bool(window.continuous.isChecked()),
        int(window.feed.value()),
    )


def _install_normal_print(window):
    def pack_current():
        job = _current_raster(window)
        packets = _pack_from_raster(window, job)
        window._v603_last_print_debug = {
            "design_size": job["design_size"],
            "raster_size": (job["rw"], job["rh"]),
            "offset_x": job["offset_x"],
            "density": int(window.density.value()),
            "packet_count": len(packets),
        }
        return packets

    window._pack_current = pack_current


def _install_concentration(window):
    if getattr(window, "_v603_concentration", None) is not None:
        return

    header = window.findChild(QFrame, "v51Header")
    status = window.findChild(QFrame, "v5103PrinterStatus")
    if header is None or header.layout() is None or status is None:
        return

    box = QFrame(header)
    box.setObjectName("v603ConcentrationBox")
    lay = QHBoxLayout(box)
    lay.setContentsMargins(8, 4, 8, 4)
    lay.setSpacing(7)

    label = QLabel("Concentración")
    combo = QComboBox()
    combo.setObjectName("v603Concentration")
    combo.addItems(list(DENSITY_LEVELS.keys()))
    combo.setMinimumWidth(118)

    lay.addWidget(label)
    lay.addWidget(combo)

    box.setStyleSheet("""
        QFrame#v603ConcentrationBox {
            background:#303030;
            border:1px solid #4C4C4C;
            border-radius:4px;
        }
        QFrame#v603ConcentrationBox QLabel {
            color:#E7E7E7;
            background:transparent;
            border:0;
        }
        QFrame#v603ConcentrationBox QComboBox {
            background:#232323;
            color:#F0F0F0;
            border:1px solid #555;
            border-radius:3px;
            padding:5px 8px;
        }
    """)

    def apply_level(text):
        value = DENSITY_LEVELS.get(str(text), 6)
        window.density.setValue(value)
        window.statusBar().showMessage(
            f"Concentración de impresión: {text} · densidad {value}/8",
            2500,
        )

    def sync_from_slider(value):
        nearest = min(DENSITY_LEVELS, key=lambda name: abs(DENSITY_LEVELS[name] - int(value)))
        if combo.currentText() != nearest:
            combo.blockSignals(True)
            combo.setCurrentText(nearest)
            combo.blockSignals(False)

    combo.currentTextChanged.connect(apply_level)
    window.density.valueChanged.connect(sync_from_slider)

    sync_from_slider(window.density.value())

    index = header.layout().indexOf(status)
    header.layout().insertWidget(max(0, index), box)

    window._v603_concentration = combo
    window._v603_concentration_box = box


@dataclass
class QueueJob:
    name: str
    raster: bytes
    rw: int
    rh: int
    design_size: tuple
    offset_x: int


class UnifiedQueue(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.jobs: list[QueueJob] = []
        self.page = getattr(window, "_v51_drawer_pages", {}).get("Cola")
        self.list_widget: Optional[QListWidget] = None
        self._wire_ui()
        self.refresh()

    def _wire_ui(self):
        if self.page is None:
            return

        self.list_widget = self.page.findChild(QListWidget)
        if self.list_widget is None:
            self.list_widget = QListWidget()
            self.list_widget.setObjectName("v603QueueList")
            layout = self.page.layout()
            if layout is not None:
                layout.insertWidget(0, self.list_widget, 1)

        for button in self.page.findChildren(QPushButton):
            text = button.text().replace("&", "").strip().casefold()
            try:
                if "actual" in text and ("+" in text or "cola" in text or text == "actual"):
                    button.clicked.disconnect()
                    button.clicked.connect(self.add_current)
                elif "vaciar" in text:
                    button.clicked.disconnect()
                    button.clicked.connect(self.clear)
                elif ("imprimir" in text and ("todo" in text or "cola" in text)):
                    button.clicked.disconnect()
                    button.clicked.connect(self.print_all)
            except Exception:
                pass

        # Route every non-UI caller through the same implementation too.
        self.window.add_to_queue = self.add_current
        self.window.print_queue = self.print_all

    def refresh(self):
        if self.list_widget is None:
            return
        self.list_widget.clear()
        for i, job in enumerate(self.jobs, 1):
            item = QListWidgetItem(f"{job.name} · 1 copia")
            item.setData(Qt.UserRole, i - 1)
            self.list_widget.addItem(item)

    def add_current(self):
        try:
            raw = _current_raster(self.window)
        except Exception as exc:
            QMessageBox.warning(self.window, "Cola de impresión", str(exc))
            return

        name = getattr(self.window, "_v510_current_design_name", "") or f"Etiqueta {len(self.jobs) + 1}"
        self.jobs.append(
            QueueJob(
                name=str(name),
                raster=raw["raster"],
                rw=raw["rw"],
                rh=raw["rh"],
                design_size=raw["design_size"],
                offset_x=raw["offset_x"],
            )
        )
        self.refresh()
        self.window.statusBar().showMessage(f"Añadida a cola: {name}", 2500)

    def clear(self):
        self.jobs.clear()
        self.refresh()
        self.window.statusBar().showMessage("Cola vaciada", 1800)

    def packets_for_all(self):
        packets = []
        for job in self.jobs:
            packets.extend(
                _pack_from_raster(
                    self.window,
                    {
                        "raster": job.raster,
                        "rw": job.rw,
                        "rh": job.rh,
                    },
                )
            )
        return packets

    def print_all(self):
        if not self.jobs:
            return

        count = len(self.jobs)
        if self.window.usable_labels() < count:
            QMessageBox.warning(
                self.window,
                "Cola de impresión",
                f"No alcanzan las etiquetas utilizables para imprimir {count}.",
            )
            return

        try:
            packets = self.packets_for_all()
        except Exception as exc:
            QMessageBox.warning(self.window, "Cola de impresión", str(exc))
            return

        self.window.progress.setRange(0, 100)
        self.window.progress.setValue(0)
        self.window.progress.show()
        future = self.window.printer.send_packets(
            packets,
            lambda d, t: self.window.bridge.print_progress.emit(d, t),
        )
        future.add_done_callback(lambda f: self.window._print_done(f, count))


def enhance(window):
    _install_normal_print(window)
    _install_concentration(window)
    queue = UnifiedQueue(window)
    window._v603_queue = queue
    window.statusBar().showMessage(
        "V6.0.3 · impresión centrada · concentración · cola unificada",
        6000,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v603_installed", False):
        return
    MainWindow._v603_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
