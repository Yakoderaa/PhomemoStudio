from __future__ import annotations

from io import BytesIO

from PIL import Image
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QMessageBox

from .studio_pro import _find_canvas

OVERLAY_ROLE = 1098


def _qimage_to_pil(image: QImage) -> Image.Image:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("No se pudo convertir el lienzo para imprimir.")
    buffer.close()
    return Image.open(BytesIO(bytes(data))).convert("L")


def _label_size_px(window, label_pixels):
    try:
        current = window.size_combo.currentData()
        if current and len(current) >= 2:
            wmm, hmm = float(current[0]), float(current[1])
            if callable(label_pixels):
                w, h = label_pixels(wmm, hmm)
                return max(1, int(w)), max(1, int(h))
            return max(1, round(wmm * 203.0 / 25.4)), max(1, round(hmm * 203.0 / 25.4))
    except Exception:
        pass

    view = _find_canvas(window)
    if view is not None and view.scene() is not None:
        r = view.scene().sceneRect()
        if r.width() > 0 and r.height() > 0:
            return max(1, round(r.width())), max(1, round(r.height()))
    return 320, 120


def render_visible_label(window, label_pixels=None) -> Image.Image:
    """Render exactly the editable scene, excluding editor-only overlays."""
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        raise RuntimeError("No encontré el lienzo activo.")
    scene = view.scene()
    source = scene.sceneRect()
    if source.isNull() or source.width() <= 0 or source.height() <= 0:
        source = scene.itemsBoundingRect()
    if source.isNull() or source.width() <= 0 or source.height() <= 0:
        raise RuntimeError("El lienzo está vacío.")

    design_w, design_h = _label_size_px(window, label_pixels)
    image = QImage(design_w, design_h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.white)

    overlays = [item for item in scene.items() if item.data(OVERLAY_ROLE)]
    visible_states = [(item, item.isVisible()) for item in overlays]
    try:
        for item, _visible in visible_states:
            item.setVisible(False)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        scene.render(
            painter,
            QRectF(0, 0, design_w, design_h),
            source,
            Qt.IgnoreAspectRatio,
        )
        painter.end()
    finally:
        for item, visible in visible_states:
            try:
                item.setVisible(visible)
            except Exception:
                pass

    return _qimage_to_pil(image)


def orient_for_d30(image: Image.Image) -> Image.Image:
    """
    D30 feeds along the label's long axis. The raster width is the dimension
    across the thermal head, so a landscape editor label must be rotated before
    sending or the printer clips/reorients the artwork.
    """
    if image.width > image.height:
        # PIL ROTATE_90 is counter-clockwise and expands, yielding
        # (short_side, long_side) as required by the D30 raster command.
        return image.transpose(Image.Transpose.ROTATE_90)
    return image


def _build_packets(raster: bytes, width_px: int, height_px: int):
    width_bytes = (int(width_px) + 7) // 8
    expected = width_bytes * int(height_px)
    if len(raster) != expected:
        raise ValueError(f"Raster de impresión inválido: {len(raster)} != {expected}")
    return [
        bytes([0x1F, 0x11, 0x24, 0x00]),
        bytes([
            0x1B, 0x40, 0x1D, 0x76, 0x30, 0x00,
            width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,
            int(height_px) & 0xFF, (int(height_px) >> 8) & 0xFF,
        ]),
        raster,
    ]


def install(MainWindow):
    if getattr(MainWindow, "_v5101_installed", False):
        return
    MainWindow._v5101_installed = True

    original_pack = getattr(MainWindow, "_pack_current", None)
    if not callable(original_pack):
        return

    globals_ = getattr(original_pack, "__globals__", {})
    label_pixels = globals_.get("label_pixels")
    image_to_d30_raster = globals_.get("image_to_d30_raster")
    if not callable(image_to_d30_raster):
        return

    def pack_current(self):
        # Important: never serialize individual graphics items for printing.
        # Render the exact live scene so text, imported images, SVGs, icons,
        # lines, rotations, scaling and layer visibility match the canvas.
        design = render_visible_label(self, label_pixels)
        printer_image = orient_for_d30(design)
        raster, rw, rh = image_to_d30_raster(printer_image)

        rw, rh = int(rw), int(rh)
        if (rw, rh) != printer_image.size:
            # The helper owns any padding to byte boundaries, but dimensions
            # must still describe the image sent to the D30.
            if rw <= 0 or rh <= 0:
                raise RuntimeError("La conversión de impresión devolvió dimensiones inválidas.")

        packets = _build_packets(raster, rw, rh)
        self._v5101_last_print_debug = {
            "design_size": tuple(design.size),
            "printer_size": tuple(printer_image.size),
            "raster_size": (rw, rh),
            "rotated": bool(design.width > design.height),
            "raster_bytes": len(raster),
        }
        return packets

    MainWindow._v5101_original_pack_current = original_pack
    MainWindow._pack_current = pack_current
