from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal, QSize
from PySide6.QtGui import QColor, QBrush, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDockWidget, QFontComboBox, QGraphicsItem,
    QGraphicsPathItem, QGraphicsView, QGridLayout, QGroupBox, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QToolBar, QToolButton,
    QVBoxLayout, QWidget
)

REPO = "Yakoderaa/PhomemoStudio"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"


class _Signals(QObject):
    update_checked = Signal(object, object)
    update_downloaded = Signal(object, object)


def _version_tuple(value: str):
    out = []
    for part in value.strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits or 0))
    return tuple((out + [0, 0, 0, 0])[:4])


def _asset(name: str) -> Path | None:
    roots = []
    if getattr(sys, "_MEIPASS", None):
        roots.append(Path(sys._MEIPASS))
    roots += [Path(sys.executable).resolve().parent, Path(__file__).resolve().parents[1]]
    for root in roots:
        for candidate in (root / "assets" / name, root / name):
            if candidate.exists():
                return candidate
    return None


def _taskbar_identity(window):
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Yakoderaa.PhomemoStudio")
    except Exception:
        pass
    icon = _asset("sr-gato.ico") or _asset("sr-gato.png")
    if icon:
        qicon = QIcon(str(icon))
        QApplication.instance().setWindowIcon(qicon)
        window.setWindowIcon(qicon)


def _font_dirs():
    env = os.environ
    candidates = [
        Path(env.get("WINDIR", r"C:\Windows")) / "Fonts",
        Path(env.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
        Path(env.get("APPDATA", "")) / "Adobe" / "CoreSync" / "plugins" / "livetype" / "r",
        Path(env.get("LOCALAPPDATA", "")) / "Adobe" / "CoreSync" / "plugins" / "livetype" / "r",
        Path(env.get("APPDATA", "")) / "Adobe" / "CoreSync" / "plugins" / "livetype",
    ]
    seen = set()
    for p in candidates:
        try:
            p = p.resolve()
        except Exception:
            continue
        if p not in seen and p.exists():
            seen.add(p)
            yield p


def load_all_fonts():
    loaded = 0
    for root in _font_dirs():
        try:
            files = list(root.rglob("*.ttf")) + list(root.rglob("*.otf")) + list(root.rglob("*.ttc"))
        except Exception:
            continue
        for f in files[:6000]:
            try:
                if QFontDatabase.addApplicationFont(str(f)) >= 0:
                    loaded += 1
            except Exception:
                pass
    return loaded


def _star(points=5, inner=.42, rotation=-90):
    pts = []
    for i in range(points * 2):
        a = math.radians(rotation + i * 180 / points)
        r = 50 if i % 2 == 0 else 50 * inner
        pts.append((50 + math.cos(a) * r, 50 + math.sin(a) * r))
    return pts


def _polygon(n, rotation=-90):
    return [(50 + math.cos(math.radians(rotation + i * 360 / n)) * 48,
             50 + math.sin(math.radians(rotation + i * 360 / n)) * 48) for i in range(n)]


def _poly_path(points, close=True):
    p = QPainterPath()
    if not points:
        return p
    p.moveTo(*points[0])
    for point in points[1:]:
        p.lineTo(*point)
    if close:
        p.closeSubpath()
    return p


def shape_path(name: str) -> QPainterPath:
    n = name.lower()
    p = QPainterPath()
    if n == "rectángulo": p.addRect(3, 15, 94, 70)
    elif n == "rectángulo redondeado": p.addRoundedRect(3, 15, 94, 70, 18, 18)
    elif n == "círculo": p.addEllipse(4, 4, 92, 92)
    elif n == "elipse": p.addEllipse(3, 21, 94, 58)
    elif n == "triángulo": p = _poly_path([(50,2),(98,94),(2,94)])
    elif n == "triángulo invertido": p = _poly_path([(2,6),(98,6),(50,98)])
    elif n == "rombo": p = _poly_path([(50,2),(98,50),(50,98),(2,50)])
    elif n == "pentágono": p = _poly_path(_polygon(5))
    elif n == "hexágono": p = _poly_path(_polygon(6))
    elif n == "octágono": p = _poly_path(_polygon(8, -67.5))
    elif n == "decágono": p = _poly_path(_polygon(10))
    elif n.startswith("estrella"):
        count = int("".join(c for c in n if c.isdigit()) or 5); p = _poly_path(_star(count))
    elif n == "corazón":
        p.moveTo(50,92); p.cubicTo(10,62,4,38,20,22); p.cubicTo(34,8,48,18,50,31); p.cubicTo(52,18,66,8,80,22); p.cubicTo(96,38,90,62,50,92); p.closeSubpath()
    elif n == "nube":
        p.moveTo(18,70); p.cubicTo(2,68,2,46,20,43); p.cubicTo(22,24,43,18,55,32); p.cubicTo(70,18,91,31,88,48); p.cubicTo(105,51,99,73,84,73); p.lineTo(18,73); p.closeSubpath()
    elif n == "gota":
        p.moveTo(50,3); p.cubicTo(32,30,18,47,18,65); p.cubicTo(18,87,34,98,50,98); p.cubicTo(66,98,82,87,82,65); p.cubicTo(82,47,68,30,50,3); p.closeSubpath()
    elif n == "luna":
        p.moveTo(72,5); p.cubicTo(34,10,18,42,30,70); p.cubicTo(42,96,72,98,91,80); p.cubicTo(57,82,40,50,72,5); p.closeSubpath()
    elif n == "rayo": p = _poly_path([(58,2),(20,57),(47,57),(38,98),(82,42),(55,42)])
    elif n == "cruz": p = _poly_path([(38,5),(62,5),(62,37),(95,37),(95,63),(62,63),(62,95),(38,95),(38,63),(5,63),(5,37),(38,37)])
    elif n == "cápsula": p.addRoundedRect(3, 28, 94, 44, 22, 22)
    elif n == "anillo":
        p.addEllipse(4,4,92,92); inner=QPainterPath(); inner.addEllipse(27,27,46,46); p = p.subtracted(inner)
    elif n == "marco":
        p.addRoundedRect(3,3,94,94,10,10); inner=QPainterPath(); inner.addRoundedRect(13,13,74,74,7,7); p=p.subtracted(inner)
    elif n == "etiqueta": p = _poly_path([(4,18),(68,18),(96,50),(68,82),(4,82)]); hole=QPainterPath(); hole.addEllipse(70,43,14,14); p=p.subtracted(hole)
    elif n == "ticket":
        p.addRoundedRect(3,18,94,64,9,9); c=QPainterPath(); c.addEllipse(-7,43,20,20); c.addEllipse(87,43,20,20); p=p.subtracted(c)
    elif n == "banderín": p = _poly_path([(8,6),(92,6),(92,94),(50,72),(8,94)])
    elif n == "escudo": p = _poly_path([(50,4),(91,18),(86,62),(50,96),(14,62),(9,18)])
    elif n == "casa": p = _poly_path([(8,48),(50,8),(92,48),(83,48),(83,94),(60,94),(60,67),(40,67),(40,94),(17,94),(17,48)])
    elif n == "flor":
        for i in range(8):
            a=math.radians(i*45); cx=50+math.cos(a)*27; cy=50+math.sin(a)*27; p.addEllipse(cx-19,cy-19,38,38)
        p.addEllipse(35,35,30,30)
    elif n == "explosión": p = _poly_path(_star(12,.68))
    elif n == "flecha derecha": p = _poly_path([(4,35),(60,35),(60,13),(97,50),(60,87),(60,65),(4,65)])
    elif n == "flecha izquierda": p = _poly_path([(96,35),(40,35),(40,13),(3,50),(40,87),(40,65),(96,65)])
    elif n == "flecha arriba": p = _poly_path([(35,96),(35,40),(13,40),(50,3),(87,40),(65,40),(65,96)])
    elif n == "flecha abajo": p = _poly_path([(35,4),(35,60),(13,60),(50,97),(87,60),(65,60),(65,4)])
    elif n == "chevrón": p = _poly_path([(8,20),(34,20),(66,50),(34,80),(8,80),(40,50)])
    elif n == "burbuja":
        p.addRoundedRect(4,8,92,67,16,16); tail=QPainterPath(); tail.moveTo(28,73); tail.lineTo(20,96); tail.lineTo(50,74); tail.closeSubpath(); p=p.united(tail)
    elif n == "cinta": p = _poly_path([(6,22),(94,22),(84,50),(94,78),(6,78),(16,50)])
    elif n == "marcador": p = _poly_path([(24,3),(76,3),(76,97),(50,73),(24,97)])
    elif n == "reloj de arena": p = _poly_path([(15,5),(85,5),(70,50),(85,95),(15,95),(30,50)])
    elif n == "onda":
        p.moveTo(2,58); p.cubicTo(20,10,36,95,54,45); p.cubicTo(70,2,82,88,98,38); p.lineTo(98,63); p.cubicTo(82,98,70,20,54,70); p.cubicTo(36,100,20,35,2,80); p.closeSubpath()
    else: p.addRoundedRect(5,5,90,90,10,10)
    return p


SHAPES = [
    "Rectángulo","Rectángulo redondeado","Círculo","Elipse","Triángulo","Triángulo invertido","Rombo",
    "Pentágono","Hexágono","Octágono","Decágono","Estrella 4","Estrella 5","Estrella 6","Estrella 8","Estrella 12",
    "Corazón","Nube","Gota","Luna","Rayo","Cruz","Cápsula","Anillo","Marco","Etiqueta","Ticket","Banderín",
    "Escudo","Casa","Flor","Explosión","Flecha derecha","Flecha izquierda","Flecha arriba","Flecha abajo","Chevrón",
    "Burbuja","Cinta","Marcador","Reloj de arena","Onda"
]


def _shape_icon(name):
    pm = QPixmap(72,56); pm.fill(Qt.transparent)
    qp = QPainter(pm); qp.setRenderHint(QPainter.Antialiasing)
    qp.setPen(QPen(QColor("#475569"),2)); qp.setBrush(QBrush(QColor("#eef2ff")))
    path = shape_path(name); tr = path.boundingRect(); scale=min(56/max(1,tr.width()),42/max(1,tr.height()))
    qp.translate(36,28); qp.scale(scale,scale); qp.translate(-tr.center().x(),-tr.center().y()); qp.drawPath(path); qp.end()
    return QIcon(pm)


def _find_canvas(window):
    views = window.findChildren(QGraphicsView)
    if not views: return None
    return max(views, key=lambda v: max(1,v.width())*max(1,v.height()))


def insert_shape(window, name):
    view = _find_canvas(window)
    if not view or not view.scene():
        QMessageBox.warning(window,"Phomemo Studio","No encontré el lienzo activo.")
        return
    path=shape_path(name)
    item=QGraphicsPathItem(path)
    item.setPen(QPen(QColor("#111827"),2.0)); item.setBrush(QBrush(QColor("#111827")))
    item.setFlags(QGraphicsItem.ItemIsMovable|QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemIsFocusable)
    item.setData(1001,"studio-shape"); item.setData(1002,name)
    center=view.mapToScene(view.viewport().rect().center()); br=path.boundingRect()
    item.setPos(center.x()-br.width()/2, center.y()-br.height()/2)
    view.scene().addItem(item); item.setSelected(True)


def _build_shape_dock(window):
    dock=QDockWidget("Elementos",window); dock.setObjectName("studioElementsDock"); dock.setMinimumWidth(286)
    host=QWidget(); lay=QVBoxLayout(host); lay.setContentsMargins(12,12,12,12); lay.setSpacing(10)
    title=QLabel("Biblioteca de formas"); title.setObjectName("sectionTitle"); lay.addWidget(title)
    search=QLineEdit(); search.setPlaceholderText("Buscar formas…"); lay.addWidget(search)
    scroll=QScrollArea(); scroll.setWidgetResizable(True); inner=QWidget(); grid=QGridLayout(inner); grid.setSpacing(8); grid.setContentsMargins(2,2,2,2)
    buttons=[]
    for i,name in enumerate(SHAPES):
        b=QToolButton(); b.setText(name); b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); b.setIcon(_shape_icon(name)); b.setIconSize(QSize(54,42)); b.setFixedSize(80,76); b.clicked.connect(lambda _=False,n=name:insert_shape(window,n)); grid.addWidget(b,i//3,i%3); buttons.append((b,name))
    scroll.setWidget(inner); lay.addWidget(scroll,1)
    search.textChanged.connect(lambda text:[b.setVisible(text.lower() in n.lower()) for b,n in buttons])
    dock.setWidget(host); window.addDockWidget(Qt.LeftDockWidgetArea,dock)
    return dock


def _apply_fonts(window):
    load_all_fonts(); families=QFontDatabase.families()
    for combo in window.findChildren(QFontComboBox): combo.setWritingSystem(QFontDatabase.Any)
    for combo in window.findChildren(QComboBox):
        try:
            hint=(combo.objectName()+" "+combo.currentText()).lower()
            if "font" not in hint and "fuente" not in hint and not any(combo.currentText()==f for f in families): continue
            current=combo.currentText(); combo.blockSignals(True); combo.clear(); combo.addItems(families); combo.setCurrentText(current); combo.blockSignals(False)
        except Exception: pass


def _modern_style(window):
    window.setMinimumSize(1180,760)
    window.setStyleSheet('''
    QMainWindow { background:#f4f6fb; color:#111827; }
    QWidget { font-family:"Segoe UI Variable","Segoe UI"; font-size:12px; }
    QToolBar { background:#ffffff; border:0; border-bottom:1px solid #e5e7eb; spacing:6px; padding:8px; }
    QStatusBar { background:#ffffff; border-top:1px solid #e5e7eb; color:#64748b; }
    QGroupBox { background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; margin-top:14px; padding:12px; font-weight:600; }
    QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; color:#334155; }
    QPushButton, QToolButton { background:#ffffff; color:#1f2937; border:1px solid #dbe2ea; border-radius:9px; padding:7px 11px; min-height:22px; }
    QPushButton:hover, QToolButton:hover { background:#f8fafc; border-color:#a5b4fc; }
    QPushButton:pressed, QToolButton:pressed { background:#eef2ff; }
    QPushButton#primary { background:#6d4aff; color:white; border:0; font-weight:600; }
    QPushButton#primary:hover { background:#5b3df5; }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background:#ffffff; border:1px solid #dbe2ea; border-radius:8px; padding:6px 9px; min-height:22px; selection-background-color:#6d4aff; }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border:1px solid #7c5cff; }
    QListWidget, QTreeWidget { background:#ffffff; border:1px solid #e5e7eb; border-radius:10px; padding:4px; }
    QListWidget::item { padding:7px; border-radius:7px; }
    QListWidget::item:selected { background:#ede9fe; color:#4c1d95; }
    QDockWidget { color:#334155; font-weight:600; }
    QDockWidget::title { background:#ffffff; padding:10px; border-bottom:1px solid #e5e7eb; }
    QScrollArea { border:0; background:transparent; }
    QLabel#sectionTitle { font-size:17px; font-weight:700; color:#111827; padding:2px 0 4px 0; }
    QProgressBar { border:0; border-radius:5px; background:#e9edf5; text-align:center; }
    QProgressBar::chunk { border-radius:5px; background:#6d4aff; }
    QSlider::groove:horizontal { height:5px; background:#dbe2ea; border-radius:2px; }
    QSlider::handle:horizontal { width:16px; margin:-6px 0; border-radius:8px; background:#6d4aff; }
    ''')
    for gb in window.findChildren(QGroupBox): gb.setFlat(False)
    for tb in window.findChildren(QToolBar): tb.setMovable(False); tb.setIconSize(QSize(20,20))


def _find_update_controls(window):
    out=[]
    for cls in (QPushButton,QToolButton):
        for w in window.findChildren(cls):
            if "actualiz" in w.text().lower(): out.append(w)
    return out


def _current_version():
    try:
        from . import __version__
        return __version__
    except Exception: return "0.0.0"


def _check_worker(signals):
    try:
        req=urllib.request.Request(API_LATEST,headers={"User-Agent":"PhomemoStudio"})
        with urllib.request.urlopen(req,timeout=15) as r: data=json.load(r)
        signals.update_checked.emit(data,None)
    except Exception as exc: signals.update_checked.emit(None,exc)


def _download_worker(signals, release):
    try:
        assets={a.get("name"):a.get("browser_download_url") for a in release.get("assets",[])}
        exe_url=assets.get("PhomemoStudioSetup.exe"); sha_url=assets.get("PhomemoStudioSetup.exe.sha256")
        if not exe_url: raise RuntimeError("La release no contiene PhomemoStudioSetup.exe")
        tag=release.get("tag_name","update").lstrip("vV"); out=Path(tempfile.gettempdir())/f"PhomemoStudioSetup-{tag}.exe"
        req=urllib.request.Request(exe_url,headers={"User-Agent":"PhomemoStudio"})
        with urllib.request.urlopen(req,timeout=60) as src, out.open("wb") as dst:
            while True:
                chunk=src.read(1024*1024)
                if not chunk: break
                dst.write(chunk)
        if sha_url:
            req=urllib.request.Request(sha_url,headers={"User-Agent":"PhomemoStudio"})
            with urllib.request.urlopen(req,timeout=15) as r: expected=r.read().decode("utf-8","replace").split()[0].lower()
            actual=hashlib.sha256(out.read_bytes()).hexdigest().lower()
            if expected and expected!=actual: raise RuntimeError("La verificación SHA-256 de la actualización falló.")
        signals.update_downloaded.emit(str(out),None)
    except Exception as exc: signals.update_downloaded.emit(None,exc)


def _start_update_check(window):
    if getattr(window,"_studio_update_busy",False): return
    window._studio_update_busy=True; window.statusBar().showMessage("Buscando actualización…")
    threading.Thread(target=_check_worker,args=(window._studio_signals,),daemon=True).start()


def _on_update_checked(window, release, error):
    window._studio_update_busy=False
    if error:
        window.statusBar().showMessage("No se pudo buscar actualizaciones",5000); QMessageBox.warning(window,"Actualizaciones",str(error)); return
    latest=release.get("tag_name","").lstrip("vV"); current=_current_version()
    if _version_tuple(latest)<=_version_tuple(current):
        window.statusBar().showMessage(f"Phomemo Studio {current} está actualizado",5000); QMessageBox.information(window,"Actualizaciones",f"Ya tenés la última versión ({current})."); return
    answer=QMessageBox.question(window,"Actualización disponible",f"Está disponible Phomemo Studio {latest}.\n\n¿Querés descargarla e instalarla ahora?",QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)
    if answer!=QMessageBox.Yes: return
    window._studio_update_busy=True; window.statusBar().showMessage(f"Descargando Phomemo Studio {latest}…")
    threading.Thread(target=_download_worker,args=(window._studio_signals,release),daemon=True).start()


def _on_update_downloaded(window, path, error):
    window._studio_update_busy=False
    if error:
        window.statusBar().showMessage("Falló la descarga de la actualización",6000); QMessageBox.warning(window,"Actualizaciones",str(error)); return
    window.statusBar().showMessage("Actualización descargada. Cerrando para instalar…")
    try:
        flags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)|getattr(subprocess,"DETACHED_PROCESS",0)|getattr(subprocess,"CREATE_NO_WINDOW",0)
        cmd=f'timeout /t 2 /nobreak >nul & "{path}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /NORESTARTAPPLICATIONS'
        subprocess.Popen(["cmd.exe","/c",cmd],creationflags=flags,close_fds=True)
        QApplication.instance().quit()
    except Exception as exc: QMessageBox.warning(window,"Actualizaciones",f"Se descargó la actualización, pero no pude iniciar el instalador:\n{exc}")


def enhance(window):
    _taskbar_identity(window); _modern_style(window); _apply_fonts(window)
    try: _build_shape_dock(window)
    except Exception as exc: print("Shape dock:",exc)
    window._studio_signals=_Signals(window)
    window._studio_signals.update_checked.connect(lambda r,e:_on_update_checked(window,r,e))
    window._studio_signals.update_downloaded.connect(lambda p,e:_on_update_downloaded(window,p,e))
    controls=_find_update_controls(window)
    for b in controls:
        try: b.clicked.disconnect()
        except Exception: pass
        b.clicked.connect(lambda _=False:_start_update_check(window))
    if not controls:
        toolbar=QToolBar("Studio",window); toolbar.setMovable(False); window.addToolBar(Qt.TopToolBarArea,toolbar)
        title=QLabel("  Phomemo Studio  "); title.setObjectName("sectionTitle"); toolbar.addWidget(title)
        spacer=QWidget(); spacer.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred); toolbar.addWidget(spacer)
        upd=QPushButton("Buscar actualizaciones"); upd.clicked.connect(lambda:_start_update_check(window)); toolbar.addWidget(upd)


def install(MainWindow):
    if getattr(MainWindow,"_studio_pro_installed",False): return
    MainWindow._studio_pro_installed=True
    original=MainWindow.__init__
    def wrapped(self,*a,**kw):
        original(self,*a,**kw)
        enhance(self)
    MainWindow.__init__=wrapped
