from __future__ import annotations

import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath, QPolygonF

# Biblioteca propia de formas para etiquetas. No replica catálogos de terceros.
SHAPES = [
    ("rect", "Rectángulo"), ("rounded_rect", "Rectángulo redondeado"), ("ellipse", "Óvalo / círculo"),
    ("capsule", "Cápsula"), ("ring", "Anillo"), ("frame", "Marco"), ("frame_round", "Marco redondeado"),
    ("triangle", "Triángulo"), ("triangle_down", "Triángulo invertido"), ("diamond", "Rombo"),
    ("pentagon", "Pentágono"), ("hexagon", "Hexágono"), ("heptagon", "Heptágono"),
    ("octagon", "Octágono"), ("nonagon", "Nonágono"), ("decagon", "Decágono"), ("dodecagon", "Dodecágono"),
    ("trapezoid", "Trapecio"), ("parallelogram", "Paralelogramo"), ("semicircle_up", "Semicírculo"),
    ("semicircle_down", "Semicírculo invertido"), ("teardrop", "Gota"), ("leaf", "Hoja"),
    ("star4", "Estrella 4 puntas"), ("star5", "Estrella 5 puntas"), ("star6", "Estrella 6 puntas"),
    ("star7", "Estrella 7 puntas"), ("star8", "Estrella 8 puntas"), ("star10", "Estrella 10 puntas"),
    ("star12", "Estrella 12 puntas"), ("burst16", "Destello 16 puntas"), ("burst24", "Destello 24 puntas"),
    ("heart", "Corazón"), ("cloud", "Nube"), ("moon", "Luna"), ("sun", "Sol"),
    ("plus", "Más"), ("cross", "Cruz"), ("badge", "Insignia"), ("lightning", "Rayo"),
    ("shield", "Escudo"), ("house", "Casa"), ("bookmark", "Marcador"), ("hourglass", "Reloj de arena"),
    ("tag", "Etiqueta"), ("ticket", "Ticket"), ("flag", "Bandera"), ("ribbon", "Cinta"),
    ("arrow_right", "Flecha derecha"), ("arrow_left", "Flecha izquierda"), ("arrow_up", "Flecha arriba"),
    ("arrow_down", "Flecha abajo"), ("arrow_up_right", "Flecha diagonal ↗"), ("arrow_down_right", "Flecha diagonal ↘"),
    ("double_arrow_h", "Flecha doble horizontal"), ("double_arrow_v", "Flecha doble vertical"),
    ("chevron_right", "Chevron derecha"), ("chevron_left", "Chevron izquierda"),
    ("speech", "Globo de diálogo"), ("speech_round", "Globo redondeado"),
]

SHAPE_NAMES = dict(SHAPES)


def _poly(rect: QRectF, pts: list[tuple[float, float]]) -> QPainterPath:
    p=QPainterPath()
    if not pts:return p
    x,y,w,h=rect.x(),rect.y(),rect.width(),rect.height(); q=[QPointF(x+px*w,y+py*h) for px,py in pts]
    p.addPolygon(QPolygonF(q)); p.closeSubpath(); return p


def _regular(rect: QRectF, sides: int, offset=-math.pi/2) -> QPainterPath:
    return _poly(rect,[(0.5+0.48*math.cos(offset+2*math.pi*i/sides),0.5+0.48*math.sin(offset+2*math.pi*i/sides)) for i in range(sides)])


def _star(rect: QRectF, points: int, inner=0.45, offset=-math.pi/2) -> QPainterPath:
    pts=[]
    for i in range(points*2):
        a=offset+math.pi*i/points; rr=0.48 if i%2==0 else 0.48*inner; pts.append((0.5+rr*math.cos(a),0.5+rr*math.sin(a)))
    return _poly(rect,pts)


def shape_path(shape: str, rect: QRectF) -> QPainterPath:
    r=QRectF(rect); x,y,w,h=r.x(),r.y(),r.width(),r.height()
    if shape=="rect": p=QPainterPath(); p.addRect(r); return p
    if shape=="rounded_rect": p=QPainterPath(); p.addRoundedRect(r,min(w,h)*.18,min(w,h)*.18); return p
    if shape=="ellipse": p=QPainterPath(); p.addEllipse(r); return p
    if shape=="capsule": p=QPainterPath(); p.addRoundedRect(r,min(w,h)*.5,min(w,h)*.5); return p
    if shape in ("ring","frame","frame_round"):
        p=QPainterPath(); p.setFillRule(Qt.FillRule.OddEvenFill)
        if shape=="ring": p.addEllipse(r)
        elif shape=="frame_round": p.addRoundedRect(r,min(w,h)*.14,min(w,h)*.14)
        else:p.addRect(r)
        m=min(w,h)*.20; inner=r.adjusted(m,m,-m,-m)
        if shape=="ring": p.addEllipse(inner)
        elif shape=="frame_round": p.addRoundedRect(inner,min(inner.width(),inner.height())*.12,min(inner.width(),inner.height())*.12)
        else:p.addRect(inner)
        return p
    if shape=="triangle":return _poly(r,[(.5,.03),(.98,.96),(.02,.96)])
    if shape=="triangle_down":return _poly(r,[(.02,.04),(.98,.04),(.5,.97)])
    if shape=="diamond":return _poly(r,[(.5,.02),(.98,.5),(.5,.98),(.02,.5)])
    regular={"pentagon":5,"hexagon":6,"heptagon":7,"octagon":8,"nonagon":9,"decagon":10,"dodecagon":12}
    if shape in regular:return _regular(r,regular[shape])
    if shape=="trapezoid":return _poly(r,[(.22,.03),(.78,.03),(.98,.97),(.02,.97)])
    if shape=="parallelogram":return _poly(r,[(.22,.03),(.98,.03),(.78,.97),(.02,.97)])
    if shape=="semicircle_up":
        p=QPainterPath(QPointF(x,y+h)); p.arcTo(QRectF(x,y,w,h*2),180,-180); p.closeSubpath(); return p
    if shape=="semicircle_down":
        p=QPainterPath(QPointF(x,y)); p.arcTo(QRectF(x,y-h,w,h*2),180,180); p.closeSubpath(); return p
    if shape=="teardrop":
        p=QPainterPath(QPointF(x+w*.5,y+h*.02)); p.cubicTo(x+w*.95,y+h*.42,x+w*.92,y+h*.78,x+w*.5,y+h*.98); p.cubicTo(x+w*.08,y+h*.78,x+w*.05,y+h*.42,x+w*.5,y+h*.02); p.closeSubpath(); return p
    if shape=="leaf":
        p=QPainterPath(QPointF(x+w*.05,y+h*.88)); p.cubicTo(x+w*.12,y+h*.20,x+w*.68,y-h*.02,x+w*.96,y+h*.12); p.cubicTo(x+w*.90,y+h*.74,x+w*.42,y+h*1.02,x+w*.05,y+h*.88); p.closeSubpath(); return p
    stars={"star4":(4,.36),"star5":(5,.43),"star6":(6,.50),"star7":(7,.50),"star8":(8,.55),"star10":(10,.58),"star12":(12,.60),"burst16":(16,.72),"burst24":(24,.78),"sun":(16,.76),"badge":(12,.82)}
    if shape in stars:return _star(r,*stars[shape])
    if shape=="heart":
        p=QPainterPath(QPointF(x+w*.5,y+h*.94)); p.cubicTo(x+w*.08,y+h*.66,x-w*.02,y+h*.28,x+w*.22,y+h*.16); p.cubicTo(x+w*.38,y+h*.08,x+w*.49,y+h*.20,x+w*.5,y+h*.31); p.cubicTo(x+w*.51,y+h*.20,x+w*.62,y+h*.08,x+w*.78,y+h*.16); p.cubicTo(x+w*1.02,y+h*.28,x+w*.92,y+h*.66,x+w*.5,y+h*.94); p.closeSubpath(); return p
    if shape=="cloud":
        p=QPainterPath(); p.moveTo(x+w*.18,y+h*.78); p.cubicTo(x-w*.02,y+h*.78,x-w*.02,y+h*.48,x+w*.18,y+h*.46); p.cubicTo(x+w*.18,y+h*.25,x+w*.38,y+h*.16,x+w*.52,y+h*.27); p.cubicTo(x+w*.66,y+h*.08,x+w*.91,y+h*.22,x+w*.86,y+h*.44); p.cubicTo(x+w*1.05,y+h*.48,x+w*1.02,y+h*.78,x+w*.82,y+h*.78); p.closeSubpath(); return p
    if shape=="moon": p=QPainterPath(); p.setFillRule(Qt.FillRule.OddEvenFill); p.addEllipse(r); p.addEllipse(QRectF(x+w*.27,y-h*.02,w*.80,h*.88)); return p
    if shape=="plus":return _poly(r,[(.36,.04),(.64,.04),(.64,.36),(.96,.36),(.96,.64),(.64,.64),(.64,.96),(.36,.96),(.36,.64),(.04,.64),(.04,.36),(.36,.36)])
    if shape=="cross":return _poly(r,[(.18,.04),(.5,.36),(.82,.04),(.96,.18),(.64,.5),(.96,.82),(.82,.96),(.5,.64),(.18,.96),(.04,.82),(.36,.5),(.04,.18)])
    if shape=="lightning":return _poly(r,[(.56,.02),(.16,.55),(.45,.55),(.34,.98),(.84,.39),(.55,.39)])
    if shape=="shield":return _poly(r,[(.08,.08),(.5,.02),(.92,.08),(.86,.64),(.5,.98),(.14,.64)])
    if shape=="house":return _poly(r,[(.05,.44),(.5,.04),(.95,.44),(.82,.44),(.82,.95),(.18,.95),(.18,.44)])
    if shape=="bookmark":return _poly(r,[(.18,.04),(.82,.04),(.82,.96),(.5,.73),(.18,.96)])
    if shape=="hourglass":return _poly(r,[(.12,.04),(.88,.04),(.62,.5),(.88,.96),(.12,.96),(.38,.5)])
    if shape=="tag":return _poly(r,[(.04,.16),(.66,.16),(.96,.5),(.66,.84),(.04,.84)])
    if shape=="ticket":return _poly(r,[(.04,.12),(.35,.12),(.42,.24),(.58,.24),(.65,.12),(.96,.12),(.96,.88),(.65,.88),(.58,.76),(.42,.76),(.35,.88),(.04,.88)])
    if shape=="flag":return _poly(r,[(.08,.04),(.08,.96),(.20,.96),(.20,.62),(.88,.62),(.70,.36),(.88,.10),(.20,.10),(.20,.04)])
    if shape=="ribbon":return _poly(r,[(.04,.18),(.22,.18),(.22,.08),(.78,.08),(.78,.18),(.96,.18),(.84,.50),(.96,.82),(.72,.82),(.72,.92),(.28,.92),(.28,.82),(.04,.82),(.16,.50)])
    if shape=="arrow_right":return _poly(r,[(.03,.32),(.60,.32),(.60,.08),(.97,.5),(.60,.92),(.60,.68),(.03,.68)])
    if shape=="arrow_left":return _poly(r,[(.97,.32),(.40,.32),(.40,.08),(.03,.5),(.40,.92),(.40,.68),(.97,.68)])
    if shape=="arrow_up":return _poly(r,[(.32,.97),(.32,.40),(.08,.40),(.5,.03),(.92,.40),(.68,.40),(.68,.97)])
    if shape=="arrow_down":return _poly(r,[(.32,.03),(.32,.60),(.08,.60),(.5,.97),(.92,.60),(.68,.60),(.68,.03)])
    if shape=="arrow_up_right":return _poly(r,[(.08,.70),(.30,.92),(.66,.56),(.84,.74),(.94,.06),(.26,.16),(.44,.34)])
    if shape=="arrow_down_right":return _poly(r,[(.08,.30),(.30,.08),(.66,.44),(.84,.26),(.94,.94),(.26,.84),(.44,.66)])
    if shape=="double_arrow_h":return _poly(r,[(.02,.5),(.28,.12),(.28,.34),(.72,.34),(.72,.12),(.98,.5),(.72,.88),(.72,.66),(.28,.66),(.28,.88)])
    if shape=="double_arrow_v":return _poly(r,[(.5,.02),(.88,.28),(.66,.28),(.66,.72),(.88,.72),(.5,.98),(.12,.72),(.34,.72),(.34,.28),(.12,.28)])
    if shape=="chevron_right":return _poly(r,[(.18,.05),(.48,.05),(.86,.5),(.48,.95),(.18,.95),(.56,.5)])
    if shape=="chevron_left":return _poly(r,[(.82,.05),(.52,.05),(.14,.5),(.52,.95),(.82,.95),(.44,.5)])
    if shape=="speech":return _poly(r,[(.04,.06),(.96,.06),(.96,.72),(.62,.72),(.46,.96),(.46,.72),(.04,.72)])
    if shape=="speech_round":
        p=QPainterPath(); body=QRectF(x,y,w,h*.78); p.addRoundedRect(body,min(w,h)*.15,min(w,h)*.15); p.addPolygon(QPolygonF([QPointF(x+w*.43,y+h*.72),QPointF(x+w*.43,y+h*.97),QPointF(x+w*.63,y+h*.74)])); return p
    return shape_path("rect",r)
