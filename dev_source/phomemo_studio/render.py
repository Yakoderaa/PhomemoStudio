from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pathlib import Path
from .core import Element, label_pixels, pack_mono_pixels


def _font(name: str, size: int, bold: bool):
    candidates=[]
    if bold:
        candidates += [f"C:/Windows/Fonts/arialbd.ttf", f"C:/Windows/Fonts/segoeuib.ttf"]
    candidates += [f"C:/Windows/Fonts/arial.ttf", f"C:/Windows/Fonts/segoeui.ttf"]
    for p in candidates:
        try: return ImageFont.truetype(p,size)
        except Exception: pass
    return ImageFont.load_default()


def render_label(elements: list[Element], width_mm=40, height_mm=12, threshold=180) -> Image.Image:
    w,h=label_pixels(width_mm,height_mm)
    img=Image.new("L",(w,h),255); d=ImageDraw.Draw(img)
    for e in elements:
        x,y,x2,y2=map(int,[e.x,e.y,e.x+e.w,e.y+e.h])
        if e.kind=="text":
            d.multiline_text((x,y),e.text,fill=0,font=_font(e.font,e.font_size,e.bold),spacing=1)
        elif e.kind=="rect":
            for i in range(max(1,e.stroke)): d.rectangle((x+i,y+i,x2-i,y2-i),outline=0)
        elif e.kind=="line":
            d.line((x,y,x2,y2),fill=0,width=max(1,e.stroke))
        elif e.kind=="image" and e.path and Path(e.path).exists():
            src=Image.open(e.path).convert("L")
            if e.image_mode=="lineart": src=src.point(lambda p: 0 if p<threshold else 255)
            src=ImageOps.contain(src,(max(1,int(e.w)),max(1,int(e.h))))
            img.paste(src,(x,y))
    return img


def image_to_d30_raster(img: Image.Image) -> tuple[bytes,int,int]:
    # Printer expects the logical label rotated clockwise, same strategy used by the older working app.
    mono=img.convert("L").point(lambda p:255 if p>180 else 0)
    rot=mono.transpose(Image.Transpose.ROTATE_270)
    w,h=rot.size; px=rot.load()
    rows=[[px[x,y] < 128 for x in range(w)] for y in range(h)]
    return pack_mono_pixels(rows)
