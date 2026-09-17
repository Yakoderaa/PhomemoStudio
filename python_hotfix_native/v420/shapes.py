from __future__ import annotations

import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath, QPolygonF

# Biblioteca propia de formas. Los nombres se muestran en la UI; los ids se guardan en plantillas.
SHAPES = [
    ("rect", "Rectángulo"), ("rounded_rect", "Rectángulo redondeado"),
    ("ellipse", "Óvalo"), ("triangle", "Triángulo"), ("triangle_down", "Triángulo invertido"),
    ("diamond", "Rombo"), ("pentagon", "Pentágono"), ("hexagon", "Hexágono"),
    ("octagon", "Octágono"), ("trapezoid", "Trapecio"), ("parallelogram", "Paralelogramo"),
    ("star5", "Estrella 5 puntas"), ("star6", "Estrella 6 puntas"), ("star8", "Estrella 8 puntas"),
    ("heart", "Corazón"), ("capsule", "Cápsula"), ("ring", "Anillo"),
    ("plus", "Más"), ("cross", "Cruz"), ("badge", "Insignia"),
    ("arrow_right", "Flecha derecha"), ("arrow_left", "Flecha izquierda"),
    ("arrow_up", "Flecha arriba"), ("arrow_down", "Flecha abajo"),
    ("chevron_right", "Chevron derecha"), ("chevron_left", "Chevron izquierda"),
    ("speech", "Globo de diálogo"), ("cloud", "Nube"), ("lightning", "Rayo"),
    ("moon", "Luna"), ("shield", "Escudo"), ("tag", "Etiqueta"),
]

SHAPE_NAMES = dict(SHAPES)


def _poly(rect: QRectF, pts: list[tuple[float, float]]) -> QPainterPath:
    p = QPainterPath()
    if not pts:
        return p
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    q = [QPointF(x + px*w, y + py*h) for px, py in pts]
    p.addPolygon(QPolygonF(q)); p.closeSubpath(); return p


def _regular(rect: QRectF, sides: int, offset=-math.pi/2) -> QPainterPath:
    pts=[]
    for i in range(sides):
        a=offset+2*math.pi*i/sides
        pts.append((0.5+0.48*math.cos(a), 0.5+0.48*math.sin(a)))
    return _poly(rect, pts)


def _star(rect: QRectF, points: int, inner=0.45, offset=-math.pi/2) -> QPainterPath:
    pts=[]
    for i in range(points*2):
        a=offset+math.pi*i/points
        r=0.48 if i%2==0 else 0.48*inner
        pts.append((0.5+r*math.cos(a), 0.5+r*math.sin(a)))
    return _poly(rect, pts)


def shape_path(shape: str, rect: QRectF) -> QPainterPath:
    r=QRectF(rect)
    if shape == "rect":
        p=QPainterPath(); p.addRect(r); return p
    if shape == "rounded_rect":
        p=QPainterPath(); p.addRoundedRect(r, min(r.width(),r.height())*.18, min(r.width(),r.height())*.18); return p
    if shape == "ellipse":
        p=QPainterPath(); p.addEllipse(r); return p
    if shape == "triangle": return _poly(r, [(0.5,.03),(.98,.96),(.02,.96)])
    if shape == "triangle_down": return _poly(r, [(.02,.04),(.98,.04),(.5,.97)])
    if shape == "diamond": return _poly(r, [(.5,.02),(.98,.5),(.5,.98),(.02,.5)])
    if shape == "pentagon": return _regular(r,5)
    if shape == "hexagon": return _regular(r,6)
    if shape == "octagon": return _regular(r,8)
    if shape == "trapezoid": return _poly(r, [(.22,.03),(.78,.03),(.98,.97),(.02,.97)])
    if shape == "parallelogram": return _poly(r, [(.22,.03),(.98,.03),(.78,.97),(.02,.97)])
    if shape == "star5": return _star(r,5,.43)
    if shape == "star6": return _star(r,6,.50)
    if shape == "star8": return _star(r,8,.55)
    if shape == "heart":
        x,y,w,h=r.x(),r.y(),r.width(),r.height(); p=QPainterPath(QPointF(x+w*.5,y+h*.94))
        p.cubicTo(x+w*.08,y+h*.66, x-w*.02,y+h*.28, x+w*.22,y+h*.16)
        p.cubicTo(x+w*.38,y+h*.08, x+w*.49,y+h*.20, x+w*.5,y+h*.31)
        p.cubicTo(x+w*.51,y+h*.20, x+w*.62,y+h*.08, x+w*.78,y+h*.16)
        p.cubicTo(x+w*1.02,y+h*.28, x+w*.92,y+h*.66, x+w*.5,y+h*.94); p.closeSubpath(); return p
    if shape == "capsule":
        p=QPainterPath(); p.addRoundedRect(r, min(r.width(),r.height())*.5, min(r.width(),r.height())*.5); return p
    if shape == "ring":
        p=QPainterPath(); p.setFillRule(Qt.FillRule.OddEvenFill); p.addEllipse(r)
        m=min(r.width(),r.height())*.22; p.addEllipse(r.adjusted(m,m,-m,-m)); return p
    if shape == "plus": return _poly(r, [(.36,.04),(.64,.04),(.64,.36),(.96,.36),(.96,.64),(.64,.64),(.64,.96),(.36,.96),(.36,.64),(.04,.64),(.04,.36),(.36,.36)])
    if shape == "cross": return _poly(r, [(.18,.04),(.5,.36),(.82,.04),(.96,.18),(.64,.5),(.96,.82),(.82,.96),(.5,.64),(.18,.96),(.04,.82),(.36,.5),(.04,.18)])
    if shape == "badge": return _star(r,12,.82)
    if shape == "arrow_right": return _poly(r, [(.03,.32),(.60,.32),(.60,.08),(.97,.5),(.60,.92),(.60,.68),(.03,.68)])
    if shape == "arrow_left": return _poly(r, [(.97,.32),(.40,.32),(.40,.08),(.03,.5),(.40,.92),(.40,.68),(.97,.68)])
    if shape == "arrow_up": return _poly(r, [(.32,.97),(.32,.40),(.08,.40),(.5,.03),(.92,.40),(.68,.40),(.68,.97)])
    if shape == "arrow_down": return _poly(r, [(.32,.03),(.32,.60),(.08,.60),(.5,.97),(.92,.60),(.68,.60),(.68,.03)])
    if shape == "chevron_right": return _poly(r, [(.18,.05),(.48,.05),(.86,.5),(.48,.95),(.18,.95),(.56,.5)])
    if shape == "chevron_left": return _poly(r, [(.82,.05),(.52,.05),(.14,.5),(.52,.95),(.82,.95),(.44,.5)])
    if shape == "speech": return _poly(r, [(.04,.06),(.96,.06),(.96,.72),(.62,.72),(.46,.96),(.46,.72),(.04,.72)])
    if shape == "cloud":
        x,y,w,h=r.x(),r.y(),r.width(),r.height(); p=QPainterPath();
        p.moveTo(x+w*.18,y+h*.78); p.cubicTo(x-w*.02,y+h*.78,x-w*.02,y+h*.48,x+w*.18,y+h*.46)
        p.cubicTo(x+w*.18,y+h*.25,x+w*.38,y+h*.16,x+w*.52,y+h*.27)
        p.cubicTo(x+w*.66,y+h*.08,x+w*.91,y+h*.22,x+w*.86,y+h*.44)
        p.cubicTo(x+w*1.05,y+h*.48,x+w*1.02,y+h*.78,x+w*.82,y+h*.78); p.closeSubpath(); return p
    if shape == "lightning": return _poly(r, [(.56,.02),(.16,.55),(.45,.55),(.34,.98),(.84,.39),(.55,.39)])
    if shape == "moon":
        x,y,w,h=r.x(),r.y(),r.width(),r.height(); p=QPainterPath(); p.setFillRule(Qt.FillRule.OddEvenFill); p.addEllipse(r); p.addEllipse(QRectF(x+w*.27,y-h*.02,w*.80,h*.88)); return p
    if shape == "shield": return _poly(r, [(.08,.08),(.5,.02),(.92,.08),(.86,.64),(.5,.98),(.14,.64)])
    if shape == "tag": return _poly(r, [(.04,.16),(.66,.16),(.96,.5),(.66,.84),(.04,.84)])
    return shape_path("rect", r)
