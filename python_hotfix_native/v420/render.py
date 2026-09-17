from __future__ import annotations

from pathlib import Path
from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QBrush

from .core import Element, label_pixels, pack_mono_pixels
from .shapes import shape_path


def _qimage_to_pil(img: QImage) -> Image.Image:
    rgba = img.convertToFormat(QImage.Format.Format_RGBA8888)
    bits = rgba.constBits()
    try:
        data = bits.tobytes()
    except AttributeError:
        data = bytes(bits)
    return Image.frombuffer(
        "RGBA", (rgba.width(), rgba.height()), data,
        "raw", "RGBA", rgba.bytesPerLine(), 1
    ).copy().convert("L")


def render_label(elements: list[Element], width_mm=40, height_mm=12, threshold=180) -> Image.Image:
    """Render with Qt so every font Windows/Adobe exposes to Qt prints exactly like the editor."""
    w,h=label_pixels(width_mm,height_mm)
    q=QImage(w,h,QImage.Format.Format_ARGB32_Premultiplied); q.fill(QColor("white"))
    p=QPainter(q); p.setRenderHint(QPainter.RenderHint.Antialiasing, True); p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    for e in elements:
        p.save()
        p.setOpacity(max(0.0,min(1.0,float(getattr(e,"opacity",1.0)))))
        if getattr(e,"rotation",0):
            cx=e.x+e.w/2; cy=e.y+e.h/2; p.translate(cx,cy); p.rotate(float(e.rotation)); p.translate(-cx,-cy)
        if e.kind=="text":
            font=QFont(e.font or "Arial", max(1,int(e.font_size))); font.setBold(bool(e.bold)); p.setFont(font); p.setPen(QColor("black"))
            p.drawText(QRectF(e.x,e.y,max(2,e.w),max(2,e.h)), Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop|Qt.TextFlag.TextWordWrap, e.text)
        elif e.kind in ("rect","shape"):
            shape = "rect" if e.kind=="rect" else (getattr(e,"shape",None) or "rect")
            p.setPen(QPen(QColor("black"), max(1,int(e.stroke)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(QBrush(QColor("black")) if getattr(e,"fill",False) else Qt.BrushStyle.NoBrush)
            inset=max(1,int(e.stroke))/2
            p.drawPath(shape_path(shape,QRectF(e.x+inset,e.y+inset,max(2,e.w-2*inset),max(2,e.h-2*inset))))
        elif e.kind=="line":
            p.setPen(QPen(QColor("black"),max(1,int(e.stroke)),Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); p.drawLine(int(e.x),int(e.y),int(e.x+e.w),int(e.y+e.h))
        elif e.kind=="image" and e.path and Path(e.path).exists():
            src=QImage(e.path)
            if not src.isNull():
                src=src.convertToFormat(QImage.Format.Format_Grayscale8)
                p.drawImage(QRectF(e.x,e.y,max(1,e.w),max(1,e.h)),src)
        p.restore()
    p.end()
    pil=_qimage_to_pil(q)
    if threshold is not None:
        pil=pil.point(lambda px: 0 if px < threshold else 255)
    return pil


def image_to_d30_raster(img: Image.Image) -> tuple[bytes,int,int]:
    mono=img.convert("L").point(lambda p:255 if p>180 else 0)
    rot=mono.transpose(Image.Transpose.ROTATE_270)
    w,h=rot.size; px=rot.load()
    rows=[[px[x,y] < 128 for x in range(w)] for y in range(h)]
    return pack_mono_pixels(rows)
