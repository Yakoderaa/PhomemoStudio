from __future__ import annotations

from io import BytesIO

from PIL import Image
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QMessageBox, QGraphicsRectItem

from .studio_pro import _find_canvas
from .v54_assets_session import _is_user_item

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


def _label_source_rect(scene) -> QRectF:
    """Return the physical white label rectangle, not the whole gray workspace."""
    candidates = []
    for item in scene.items():
        try:
            if item.data(OVERLAY_ROLE):
                continue
            if _is_user_item(item):
                continue
            if not hasattr(item, "brush"):
                continue
            brush = item.brush()
            color = brush.color()
            # Use the rectangle's logical page geometry, excluding its
            # cosmetic/outline pen. sceneBoundingRect() includes half the pen
            # on every edge (320x96 becomes ~321x97) and then forces another
            # rescale at print time.
            if isinstance(item, QGraphicsRectItem):
                rect = item.mapRectToScene(item.rect()).boundingRect()
            else:
                rect = item.sceneBoundingRect()
            if (
                color.alpha() >= 240
                and color.red() >= 238
                and color.green() >= 238
                and color.blue() >= 238
                and rect.width() > 40
                and rect.height() > 20
            ):
                candidates.append(rect)
        except Exception:
            continue

    if candidates:
        # The page/label is the largest static white rectangle in the scene.
        return max(candidates, key=lambda r: r.width() * r.height())

    source = scene.sceneRect()
    if source.isNull() or source.width() <= 0 or source.height() <= 0:
        source = scene.itemsBoundingRect()
    return source


def render_visible_label(window, label_pixels=None) -> Image.Image:
    """Render exactly the editable scene, excluding editor-only overlays."""
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        raise RuntimeError("No encontré el lienzo activo.")
    scene = view.scene()
    source = _label_source_rect(scene)
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


def _validate_raster(raster: bytes, width_px: int, height_px: int):
    width_bytes = (int(width_px) + 7) // 8
    expected = width_bytes * int(height_px)
    if len(raster) != expected:
        raise ValueError(f"Raster de impresión inválido: {len(raster)} != {expected}")


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
    make_print_packet = globals_.get("make_print_packet")
    if not callable(image_to_d30_raster) or not callable(make_print_packet):
        return

    def pack_current(self):
        # Important: never serialize individual graphics items for printing.
        # Render the exact live scene so text, imported images, SVGs, icons,
        # lines, rotations, scaling and layer visibility match the canvas.
        design = render_visible_label(self, label_pixels)

        # image_to_d30_raster() already performs the clockwise rotation used by
        # the original working D30 print path. Do NOT rotate the scene before
        # calling it: doing so rotates twice and makes the long side become the
        # thermal-head width, which the D30 silently ignores.
        raster, rw, rh = image_to_d30_raster(design)

        rw, rh = int(rw), int(rh)
        if rw <= 0 or rh <= 0:
            raise RuntimeError("La conversión de impresión devolvió dimensiones inválidas.")

        _validate_raster(raster, rw, rh)

        # IMPORTANT: use the D30 protocol builder from the original working
        # print path. The V5.10.1 regression came from replacing this with the
        # much simpler calibration-style packet sequence; calibration could
        # still feed paper, while a normal print job was never committed by
        # the printer firmware.
        density = int(self.density.value())
        continuous = bool(self.continuous.isChecked())
        feed = int(self.feed.value())
        packets = make_print_packet(raster, rw, rh, density, continuous, feed)

        self._v5101_last_print_debug = {
            "design_size": tuple(design.size),
            "printer_size": (rw, rh),
            "raster_size": (rw, rh),
            "rotated": bool(design.width > design.height and rw < rh),
            "raster_bytes": len(raster),
            "density": density,
            "continuous": continuous,
            "feed": feed,
            "packet_count": len(packets),
        }
        return packets

    MainWindow._v5101_original_pack_current = original_pack
    MainWindow._pack_current = pack_current
