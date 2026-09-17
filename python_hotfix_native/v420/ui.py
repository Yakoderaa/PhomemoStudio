from __future__ import annotations

import copy
import os
import sys
import uuid
from pathlib import Path
from concurrent.futures import Future

from PySide6.QtCore import Qt, QRectF, QTimer, Signal, QObject, QThread, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QFont, QFontDatabase, QBrush
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QSlider, QFileDialog, QMessageBox, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsPixmapItem, QGraphicsPathItem, QGroupBox,
    QFormLayout, QStatusBar, QProgressBar, QInputDialog, QSplitter, QTabWidget, QFrame,
    QScrollArea, QToolButton, QSizePolicy
)

from . import __version__
from .core import AppState, StateStore, Element, Template, label_pixels, make_print_packet
from .printer import D30Printer, PrinterSnapshot
from .render import render_label, image_to_d30_raster
from .shapes import SHAPES, SHAPE_NAMES, shape_path
from . import updater

APP_NAME = "Phomemo Studio"


def load_extra_fonts() -> list[str]:
    """Expose system fonts plus per-user and Adobe Creative Cloud fonts to Qt."""
    roots=[]
    local=os.getenv("LOCALAPPDATA"); roaming=os.getenv("APPDATA")
    if local:
        roots += [Path(local)/"Microsoft"/"Windows"/"Fonts", Path(local)/"Adobe"/"CoreSync"/"plugins"/"livetype"]
    if roaming:
        roots += [Path(roaming)/"Adobe"/"CoreSync"/"plugins"/"livetype"]
    loaded=0
    for root in roots:
        if not root.exists(): continue
        try:
            for p in root.rglob("*"):
                if loaded>=5000: break
                if p.is_file() and p.suffix.lower() in (".ttf",".otf",".ttc"):
                    try:
                        if QFontDatabase.addApplicationFont(str(p)) >= 0: loaded += 1
                    except Exception: pass
        except Exception: pass
    try: families=list(QFontDatabase.families())
    except Exception: families=[]
    return sorted(dict.fromkeys(families), key=str.casefold)


class Bridge(QObject):
    printer_status = Signal(object)
    print_progress = Signal(int, int)
    future_done = Signal(object, object)


class UpdaterThread(QThread):
    progress = Signal(str, int)
    done = Signal(object, object)
    def __init__(self, current: str, download: bool):
        super().__init__(); self.current=current; self.download=download
    def run(self):
        try:
            self.progress.emit("Buscando actualización…",0)
            info=updater.get_latest()
            if updater.parse_version(info.version)<=updater.parse_version(self.current):
                self.done.emit(None,None); return
            if not self.download:
                self.done.emit(info,None); return
            self.progress.emit(f"Descargando {info.version}…",1)
            path=updater.download_verified(info,lambda d,t:self.progress.emit(
                f"Descargando {info.version}…",int(d*100/t) if t else 0))
            self.progress.emit("Descarga verificada · preparando instalación…",100)
            self.done.emit(info,path)
        except Exception as e:
            self.done.emit(None,e)


class ShapeGraphicsItem(QGraphicsPathItem):
    def __init__(self, shape_name="rect", w=90, h=55):
        super().__init__(); self.shape_name=shape_name; self.shape_w=w; self.shape_h=h
        self.setPen(QPen(QColor("#111827"),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        self.setBrush(Qt.BrushStyle.NoBrush); self.rebuild()
    def rebuild(self): self.setPath(shape_path(self.shape_name,QRectF(0,0,self.shape_w,self.shape_h)))
    def set_size(self,w,h): self.shape_w=max(4,float(w)); self.shape_h=max(4,float(h)); self.rebuild()


class CanvasView(QGraphicsView):
    selection_changed=Signal(object); scene_modified=Signal()
    def __init__(self,parent=None):
        super().__init__(parent); self.scene_obj=QGraphicsScene(self); self.setScene(self.scene_obj)
        self.setRenderHint(QPainter.RenderHint.Antialiasing); self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag); self.setBackgroundBrush(QColor("#e9edf4")); self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFrameShape(QFrame.Shape.NoFrame); self.width_mm=40; self.height_mm=12; self.zoom_pct=100; self._page=None
        self.scene_obj.selectionChanged.connect(self._sel); self.set_label_size(40,12)
    def _sel(self):
        items=self.scene_obj.selectedItems(); self.selection_changed.emit(items[0] if items else None)
    def _fit(self):
        w,h=label_pixels(self.width_mm,self.height_mm); self.fitInView(QRectF(-28,-28,w+56,h+56),Qt.AspectRatioMode.KeepAspectRatio)
        self.scale(self.zoom_pct/100,self.zoom_pct/100)
    def set_zoom(self,pct): self.zoom_pct=max(50,min(200,int(pct))); self._fit()
    def set_label_size(self,wmm,hmm):
        self.width_mm=wmm; self.height_mm=hmm; w,h=label_pixels(wmm,hmm); self.scene_obj.clear(); self.scene_obj.setSceneRect(-36,-36,w+72,h+72)
        self._page=QGraphicsRectItem(0,0,w,h); self._page.setBrush(QColor("white")); self._page.setPen(QPen(QColor("#cbd3df"),1)); self._page.setZValue(-1000); self.scene_obj.addItem(self._page); self._fit()
    def resizeEvent(self,e): super().resizeEvent(e); self._fit()
    def _flags(self,item):
        item.setFlags(item.flags()|item.GraphicsItemFlag.ItemIsMovable|item.GraphicsItemFlag.ItemIsSelectable|item.GraphicsItemFlag.ItemSendsGeometryChanges)
    def _place(self,item,x=20,y=18): self._flags(item); item.setPos(x,y); self.scene_obj.addItem(item); self.scene_obj.clearSelection(); item.setSelected(True); self.scene_modified.emit(); return item
    def add_text(self,text="Texto"):
        item=QGraphicsTextItem(text); item.setDefaultTextColor(QColor("#111827")); item.setFont(QFont("Arial",16)); return self._place(item)
    def add_shape(self,shape_name="rect"):
        item=ShapeGraphicsItem(shape_name,90,55); return self._place(item)
    def add_rect(self): return self.add_shape("rect")
    def add_line(self):
        item=QGraphicsLineItem(0,0,110,0); item.setPen(QPen(QColor("#111827"),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); return self._place(item,20,45)
    def add_image(self,path):
        pix=QPixmap(path)
        if pix.isNull(): raise ValueError("No pude abrir la imagen")
        item=QGraphicsPixmapItem(pix.scaled(130,90,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); item.setData(0,path); return self._place(item)
    def delete_selected(self):
        for i in list(self.scene_obj.selectedItems()): self.scene_obj.removeItem(i)
        self.scene_modified.emit()
    def duplicate_selected(self):
        items=self.scene_obj.selectedItems()
        if not items:return
        it=items[0]
        if isinstance(it,QGraphicsTextItem): n=self.add_text(it.toPlainText()); n.setFont(it.font())
        elif isinstance(it,ShapeGraphicsItem):
            n=self.add_shape(it.shape_name); n.set_size(it.shape_w,it.shape_h); n.setPen(it.pen()); n.setBrush(it.brush())
        elif isinstance(it,QGraphicsLineItem): n=self.add_line(); n.setLine(it.line()); n.setPen(it.pen())
        elif isinstance(it,QGraphicsPixmapItem) and it.data(0): n=self.add_image(str(it.data(0)))
        else:return
        n.setPos(it.pos().x()+12,it.pos().y()+12); self.scene_modified.emit()
    def keyPressEvent(self,e):
        if e.key() in (Qt.Key.Key_Delete,Qt.Key.Key_Backspace): self.delete_selected(); return
        if e.modifiers()&Qt.KeyboardModifier.ControlModifier and e.key()==Qt.Key.Key_D: self.duplicate_selected(); return
        super().keyPressEvent(e)
    def elements(self):
        out=[]
        for it in self.scene_obj.items():
            if it is self._page: continue
            p=it.pos(); br=it.boundingRect()
            if isinstance(it,QGraphicsTextItem):
                f=it.font(); out.append(Element("text",p.x(),p.y(),max(2,br.width()),max(2,br.height()),text=it.toPlainText(),font=f.family(),font_size=max(1,f.pointSize()),bold=f.bold()))
            elif isinstance(it,ShapeGraphicsItem):
                out.append(Element("shape",p.x(),p.y(),it.shape_w,it.shape_h,stroke=max(1,int(it.pen().width())),shape=it.shape_name,fill=it.brush().style()!=Qt.BrushStyle.NoBrush))
            elif isinstance(it,QGraphicsRectItem): out.append(Element("rect",p.x(),p.y(),br.width(),br.height(),stroke=max(1,int(it.pen().width()))))
            elif isinstance(it,QGraphicsLineItem):
                line=it.line(); out.append(Element("line",p.x()+line.x1(),p.y()+line.y1(),line.x2()-line.x1(),line.y2()-line.y1(),stroke=max(1,int(it.pen().width()))))
            elif isinstance(it,QGraphicsPixmapItem): out.append(Element("image",p.x(),p.y(),br.width(),br.height(),path=str(it.data(0) or "")))
        return out
    def load_elements(self,elements):
        self.set_label_size(self.width_mm,self.height_mm)
        for raw in elements:
            try:e=Element(**{k:v for k,v in raw.items() if k in Element.__dataclass_fields__}) if isinstance(raw,dict) else raw
            except Exception:continue
            if e.kind=="text":
                it=self.add_text(e.text); f=QFont(e.font,e.font_size); f.setBold(e.bold); it.setFont(f); it.setPos(e.x,e.y)
            elif e.kind in ("rect","shape"):
                it=self.add_shape("rect" if e.kind=="rect" else e.shape); it.set_size(e.w,e.h); it.setPos(e.x,e.y); it.setPen(QPen(QColor("#111827"),e.stroke)); it.setBrush(QBrush(QColor("#111827")) if e.fill else Qt.BrushStyle.NoBrush)
            elif e.kind=="line":
                it=self.add_line(); it.setLine(0,0,e.w,e.h); it.setPos(e.x,e.y); it.setPen(QPen(QColor("#111827"),e.stroke,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            elif e.kind=="image" and e.path and Path(e.path).exists():
                try:it=self.add_image(e.path); it.setPos(e.x,e.y)
                except Exception:pass
        self.scene_obj.clearSelection()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(f"{APP_NAME} {__version__}"); self.resize(1540,940); self.setMinimumSize(1120,720)
        icon=self.asset("sr-gato.ico");
        if icon.exists(): self.setWindowIcon(QIcon(str(icon)))
        self.store=StateStore(); self.state=self.store.load(); self.bridge=Bridge(); self.printer=D30Printer(lambda s:self.bridge.printer_status.emit(copy.copy(s)))
        self.bridge.printer_status.connect(self.on_printer_status); self.bridge.print_progress.connect(self.on_print_progress); self.bridge.future_done.connect(self.on_future_done)
        self.current_template_id=None; self.queue=[]; self._update_thread=None; self._connect_generation=0; self._want_connected=False; self._maintenance_inflight=False
        self._autosave=QTimer(self); self._autosave.setInterval(1000); self._autosave.setSingleShot(True); self._autosave.timeout.connect(self.save_state)
        self.font_families=load_extra_fonts(); self._build_ui(); self._apply_state(); self.refresh_templates(); self.refresh_shape_library(); self.update_roll_ui()
        self.canvas.scene_modified.connect(lambda:self._autosave.start())
        self._maintenance_timer=QTimer(self); self._maintenance_timer.setInterval(30000); self._maintenance_timer.timeout.connect(self._maintain_connection); self._maintenance_timer.start()
        QTimer.singleShot(2800,lambda:self.check_updates(auto=True))
    def asset(self,name):
        root=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent.parent)); return root/"assets"/name
    def _button(self,text,slot=None,primary=False,small=False):
        b=QPushButton(text); b.setObjectName("primary" if primary else ("small" if small else ""));
        if slot:b.clicked.connect(slot)
        return b
    def _build_ui(self):
        self.setStyleSheet("""
        *{font-family:'Segoe UI';font-size:12px;color:#172033} QMainWindow{background:#f3f5f8}
        QFrame#topbar{background:#ffffff;border-bottom:1px solid #e6eaf0} QFrame#side,QFrame#inspector{background:#ffffff}
        QLabel#brand{font-size:17px;font-weight:700;color:#111827} QLabel#muted{color:#7b8495} QLabel#section{font-size:13px;font-weight:700;color:#20293a}
        QPushButton,QToolButton{background:#fff;border:1px solid #dce2eb;border-radius:9px;padding:7px 11px;color:#20293a} QPushButton:hover,QToolButton:hover{background:#f7f5ff;border-color:#b9aaff}
        QPushButton#primary{background:#6d4aff;color:#fff;border:1px solid #6d4aff;font-weight:650} QPushButton#primary:hover{background:#5e3fe8} QPushButton#small{padding:5px 8px}
        QLineEdit,QComboBox,QSpinBox{background:#f9fafc;border:1px solid #dfe4ec;border-radius:8px;padding:6px 8px;min-height:20px} QLineEdit:focus,QComboBox:focus,QSpinBox:focus{border-color:#8c72ff;background:white}
        QListWidget{background:#fff;border:1px solid #e4e8ef;border-radius:10px;padding:4px;outline:0} QListWidget::item{padding:8px;border-radius:7px} QListWidget::item:selected{background:#eeeaff;color:#4d35c8}
        QTabWidget::pane{border:0;background:#fff} QTabBar::tab{background:transparent;padding:9px 13px;color:#697386;border-bottom:2px solid transparent} QTabBar::tab:selected{color:#5b42de;border-bottom:2px solid #6d4aff;font-weight:650}
        QGroupBox{border:1px solid #e5e9f0;border-radius:11px;margin-top:14px;padding:12px 10px 10px;background:#fff;font-weight:650} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px;color:#3b4455}
        QScrollArea{border:0;background:#fff} QScrollBar:vertical{background:transparent;width:9px;margin:2px} QScrollBar::handle:vertical{background:#cfd5df;border-radius:4px;min-height:30px}
        QStatusBar{background:#ffffff;border-top:1px solid #e2e7ee} QProgressBar{border:0;border-radius:5px;background:#eceff4;text-align:center;height:10px} QProgressBar::chunk{background:#6d4aff;border-radius:5px}
        QSlider::groove:horizontal{height:5px;background:#e0e4eb;border-radius:2px} QSlider::handle:horizontal{width:15px;margin:-5px 0;border-radius:7px;background:#6d4aff}
        """)
        central=QWidget(); root=QVBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0); self.setCentralWidget(central)
        top=QFrame(); top.setObjectName("topbar"); th=QHBoxLayout(top); th.setContentsMargins(14,9,14,9); th.setSpacing(7)
        logo=QLabel(); pix=QPixmap(str(self.asset("sr-gato-transparent.png"))); logo.setPixmap(pix.scaled(29,29,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)) if not pix.isNull() else None; th.addWidget(logo)
        brand=QLabel("Phomemo Studio"); brand.setObjectName("brand"); th.addWidget(brand); ver=QLabel(f"v{__version__}"); ver.setObjectName("muted"); th.addWidget(ver); th.addSpacing(8)
        th.addWidget(self._button("Nuevo",self.new_blank)); th.addWidget(self._button("＋ Texto",lambda:self.canvas.add_text())); th.addWidget(self._button("＋ Línea",lambda:self.canvas.add_line())); th.addWidget(self._button("Subir imagen",self.pick_image)); th.addStretch(1)
        self.size_combo=QComboBox();
        for w,h in [(40,12),(30,12),(22,12),(12,12),(30,14),(40,15),(30,15)]:self.size_combo.addItem(f"{w} × {h} mm",(w,h))
        self.size_combo.currentIndexChanged.connect(self.change_size); th.addWidget(self.size_combo)
        th.addWidget(self._button("Guardar",self.save_template)); th.addWidget(self._button("Duplicar diseño",self.duplicate_template)); th.addWidget(self._button("PNG",self.export_png)); th.addWidget(self._button("Calibrar",self.calibrate)); th.addWidget(self._button("Imprimir",self.print_current,True)); root.addWidget(top)
        splitter=QSplitter(); splitter.setChildrenCollapsible(False); root.addWidget(splitter,1)
        left=QFrame(); left.setObjectName("side"); left.setMinimumWidth(260); left.setMaximumWidth(340); ll=QVBoxLayout(left); ll.setContentsMargins(12,12,12,12)
        tabs=QTabWidget(); ll.addWidget(tabs)
        designs=QWidget(); dv=QVBoxLayout(designs); dv.setContentsMargins(0,8,0,0); head=QHBoxLayout(); lab=QLabel("Mis diseños"); lab.setObjectName("section"); head.addWidget(lab); head.addStretch(); head.addWidget(self._button("＋ Grupo",self.new_group,small=True)); dv.addLayout(head)
        self.search=QLineEdit(); self.search.setPlaceholderText("Buscar diseños…"); self.search.textChanged.connect(self.refresh_templates); dv.addWidget(self.search)
        self.group_filter=QComboBox(); self.group_filter.currentIndexChanged.connect(self.refresh_templates); dv.addWidget(self.group_filter); self.template_list=QListWidget(); self.template_list.itemDoubleClicked.connect(self.load_template_item); dv.addWidget(self.template_list,1); tabs.addTab(designs,"Diseños")
        elements=QWidget(); ev=QVBoxLayout(elements); ev.setContentsMargins(0,8,0,0); el=QLabel("Biblioteca de formas"); el.setObjectName("section"); ev.addWidget(el); self.shape_filter=QLineEdit(); self.shape_filter.setPlaceholderText("Buscar formas…"); self.shape_filter.textChanged.connect(self.refresh_shape_library); ev.addWidget(self.shape_filter)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); self.shape_host=QWidget(); self.shape_grid=QGridLayout(self.shape_host); self.shape_grid.setContentsMargins(0,4,2,4); self.shape_grid.setSpacing(7); scroll.setWidget(self.shape_host); ev.addWidget(scroll,1); tabs.addTab(elements,"Elementos"); splitter.addWidget(left)
        work=QFrame(); wv=QVBoxLayout(work); wv.setContentsMargins(10,10,10,10); bar=QHBoxLayout(); label=QLabel("Lienzo de etiqueta"); label.setObjectName("section"); bar.addWidget(label); bar.addStretch(); bar.addWidget(QLabel("Zoom")); self.zoom=QSlider(Qt.Orientation.Horizontal); self.zoom.setRange(50,160); self.zoom.setValue(100); self.zoom.setFixedWidth(130); self.zoom.valueChanged.connect(lambda v:self.canvas.set_zoom(v)); bar.addWidget(self.zoom); self.zoom_label=QLabel("100%"); self.zoom.valueChanged.connect(lambda v:self.zoom_label.setText(f"{v}%")); bar.addWidget(self.zoom_label); wv.addLayout(bar); self.canvas=CanvasView(); wv.addWidget(self.canvas,1); splitter.addWidget(work)
        right=QFrame(); right.setObjectName("inspector"); right.setMinimumWidth(300); right.setMaximumWidth(390); rv=QVBoxLayout(right); rv.setContentsMargins(10,10,10,10); self.inspector_tabs=QTabWidget(); rv.addWidget(self.inspector_tabs)
        prop=QWidget(); pv=QVBoxLayout(prop); pv.setContentsMargins(2,8,2,2); pbox=QGroupBox("Elemento seleccionado"); pf=QFormLayout(pbox); self.prop_text=QLineEdit(); self.prop_font=QComboBox(); self.prop_font.setEditable(True); self.prop_font.addItems(self.font_families); self.prop_size=QSpinBox(); self.prop_size.setRange(4,180); self.prop_bold=QCheckBox("Negrita"); self.prop_stroke=QSpinBox(); self.prop_stroke.setRange(1,16); self.prop_fill=QCheckBox("Relleno negro"); pf.addRow("Texto",self.prop_text); pf.addRow("Fuente",self.prop_font); pf.addRow("Tamaño",self.prop_size); pf.addRow("",self.prop_bold); pf.addRow("Grosor",self.prop_stroke); pf.addRow("",self.prop_fill); row=QHBoxLayout(); dup=self._button("Duplicar",self.canvas.duplicate_selected); dele=self._button("Eliminar",self.canvas.delete_selected); row.addWidget(dup); row.addWidget(dele); pf.addRow(row); pv.addWidget(pbox); font_hint=QLabel(f"{len(self.font_families)} familias de fuentes detectadas. Incluye fuentes de Adobe si Creative Cloud las expone en Windows."); font_hint.setWordWrap(True); font_hint.setObjectName("muted"); pv.addWidget(font_hint); pv.addStretch(); self.inspector_tabs.addTab(prop,"Propiedades")
        self.canvas.selection_changed.connect(self.selection_changed)
        for w in [self.prop_text,self.prop_font,self.prop_size,self.prop_bold,self.prop_stroke,self.prop_fill]:
            sig=getattr(w,"textChanged",None) or getattr(w,"currentTextChanged",None) or getattr(w,"valueChanged",None) or getattr(w,"toggled",None); sig.connect(self.apply_properties)
        printing=QWidget(); iv=QVBoxLayout(printing); iv.setContentsMargins(2,8,2,2); qbox=QGroupBox("Cola de impresión"); qv=QVBoxLayout(qbox); self.queue_list=QListWidget(); self.queue_list.setMaximumHeight(180); qv.addWidget(self.queue_list); qr=QHBoxLayout(); qr.addWidget(self._button("＋ Actual",self.queue_current)); qr.addWidget(self._button("Vaciar",self.clear_queue)); qv.addLayout(qr); qv.addWidget(self._button("Imprimir todo",self.print_queue,True)); iv.addWidget(qbox)
        sbox=QGroupBox("Ajustes de impresión"); sf=QFormLayout(sbox); self.density=QSlider(Qt.Orientation.Horizontal); self.density.setRange(1,8); self.density_label=QLabel("6"); self.density.valueChanged.connect(lambda v:self.density_label.setText(str(v))); dr=QWidget(); dh=QHBoxLayout(dr); dh.setContentsMargins(0,0,0,0); dh.addWidget(self.density); dh.addWidget(self.density_label); self.continuous=QCheckBox("Rollo continuo"); self.feed=QSpinBox(); self.feed.setRange(0,255); self.auto_reconnect=QCheckBox("Reconexión automática"); sf.addRow("Densidad",dr); sf.addRow(self.continuous); sf.addRow("Avance extra",self.feed); sf.addRow(self.auto_reconnect); iv.addWidget(sbox); iv.addStretch(); self.inspector_tabs.addTab(printing,"Impresión")
        roll=QWidget(); rov=QVBoxLayout(roll); rov.setContentsMargins(2,8,2,2); rbox=QGroupBox("Rollo y calibración"); rf=QFormLayout(rbox); self.roll_name=QLineEdit(); self.roll_total=QSpinBox(); self.roll_total.setRange(1,9999); self.roll_remaining=QSpinBox(); self.roll_remaining.setRange(0,9999); self.roll_usable=QLabel(); rf.addRow("Nombre",self.roll_name); rf.addRow("Inicial",self.roll_total); rf.addRow("Restantes físicas",self.roll_remaining); rf.addRow("Utilizables",self.roll_usable); self.calibrate_btn=self._button("Calibrar D30 / rollo",self.calibrate,True); rf.addRow(self.calibrate_btn); rov.addWidget(rbox); note=QLabel("Calibrar no descuenta etiquetas. La última etiqueta física se reserva para evitar impresiones defectuosas al final del rollo."); note.setWordWrap(True); note.setObjectName("muted"); rov.addWidget(note); rov.addStretch(); self.inspector_tabs.addTab(roll,"Rollo")
        app=QWidget(); av=QVBoxLayout(app); av.setContentsMargins(2,8,2,2); ab=QGroupBox("Actualizaciones"); ah=QVBoxLayout(ab); self.update_state=QLabel(f"Versión instalada: {__version__}"); self.update_state.setWordWrap(True); ah.addWidget(self.update_state); self.update_btn=self._button("Buscar actualizaciones",lambda:self.check_updates(auto=False),True); ah.addWidget(self.update_btn); av.addWidget(ab); al=QLabel("Al encontrar una versión nueva, el botón la descarga, verifica el SHA-256, inicia el instalador y cierra Phomemo Studio automáticamente."); al.setWordWrap(True); al.setObjectName("muted"); av.addWidget(al); av.addStretch(); self.inspector_tabs.addTab(app,"Aplicación")
        splitter.addWidget(right); splitter.setSizes([285,930,330])
        sb=QStatusBar(); self.setStatusBar(sb); self.conn=QLabel("D30 desconectada"); self.battery=QLabel("Batería —"); self.paper=QLabel("Papel —"); self.roll_status=QLabel(); self.progress=QProgressBar(); self.progress.setFixedWidth(180); self.progress.hide(); self.connect_btn=self._button("Conectar D30",self.toggle_connect,True); sb.addWidget(self.conn,1); sb.addPermanentWidget(self.battery); sb.addPermanentWidget(self.paper); sb.addPermanentWidget(self.roll_status); sb.addPermanentWidget(self.progress); sb.addPermanentWidget(self.connect_btn)
    def _apply_state(self):
        self.roll_name.setText(self.state.roll_name); self.roll_total.setValue(self.state.roll_total); self.roll_remaining.setValue(self.state.roll_remaining); self.density.setValue(self.state.density); self.continuous.setChecked(self.state.continuous); self.feed.setValue(self.state.feed_dots); self.auto_reconnect.setChecked(self.state.auto_reconnect); self.refresh_groups()
        for w in [self.roll_name,self.roll_total,self.roll_remaining,self.density,self.continuous,self.feed,self.auto_reconnect]:
            sig=getattr(w,"textChanged",None) or getattr(w,"valueChanged",None) or getattr(w,"toggled",None); sig.connect(lambda *_:self._autosave.start())
    def refresh_shape_library(self):
        if not hasattr(self,"shape_grid"):return
        while self.shape_grid.count():
            it=self.shape_grid.takeAt(0); w=it.widget();
            if w:w.deleteLater()
        q=self.shape_filter.text().strip().lower() if hasattr(self,"shape_filter") else ""; row=col=0
        for sid,name in SHAPES:
            if q and q not in name.lower():continue
            b=QToolButton(); b.setText(name); b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly); b.setMinimumHeight(45); b.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed); b.clicked.connect(lambda checked=False,s=sid:self.canvas.add_shape(s)); self.shape_grid.addWidget(b,row,col); col+=1
            if col>=2:col=0; row+=1
        self.shape_grid.setRowStretch(row+1,1)
    def refresh_groups(self):
        current=self.group_filter.currentText(); self.group_filter.blockSignals(True); self.group_filter.clear(); self.group_filter.addItem("Todos los grupos"); self.group_filter.addItems(self.state.groups); idx=self.group_filter.findText(current); self.group_filter.setCurrentIndex(max(0,idx)); self.group_filter.blockSignals(False)
    def refresh_templates(self):
        if not hasattr(self,"template_list"):return
        q=self.search.text().lower().strip(); g=self.group_filter.currentText(); self.template_list.clear()
        for t in self.state.templates:
            if q and q not in t.name.lower():continue
            if g and g!="Todos los grupos" and t.group!=g:continue
            item=QListWidgetItem(f"{t.name}\n{t.group} · {t.width_mm}×{t.height_mm} mm"); item.setData(Qt.ItemDataRole.UserRole,t.id); self.template_list.addItem(item)
    def new_group(self):
        name,ok=QInputDialog.getText(self,"Nuevo grupo","Nombre del grupo:")
        if ok and name.strip() and name.strip() not in self.state.groups:self.state.groups.append(name.strip()); self.refresh_groups(); self.save_state()
    def new_blank(self): self.current_template_id=None; self.canvas.set_label_size(*self.size_combo.currentData())
    def change_size(self):
        data=self.size_combo.currentData();
        if data:self.canvas.set_label_size(*data)
    def pick_image(self):
        path,_=QFileDialog.getOpenFileName(self,"Subir imagen","","Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            try:self.canvas.add_image(path)
            except Exception as e:QMessageBox.warning(self,APP_NAME,str(e))
    def selection_changed(self,it):
        widgets=[self.prop_text,self.prop_font,self.prop_size,self.prop_bold,self.prop_stroke,self.prop_fill]
        for w in widgets:w.blockSignals(True)
        try:
            self.prop_text.setEnabled(isinstance(it,QGraphicsTextItem)); self.prop_font.setEnabled(isinstance(it,QGraphicsTextItem)); self.prop_size.setEnabled(isinstance(it,QGraphicsTextItem)); self.prop_bold.setEnabled(isinstance(it,QGraphicsTextItem)); self.prop_fill.setEnabled(isinstance(it,ShapeGraphicsItem)); self.prop_stroke.setEnabled(isinstance(it,(ShapeGraphicsItem,QGraphicsLineItem,QGraphicsRectItem)))
            if isinstance(it,QGraphicsTextItem):
                f=it.font(); self.prop_text.setText(it.toPlainText()); self.prop_font.setCurrentText(f.family()); self.prop_size.setValue(max(4,f.pointSize())); self.prop_bold.setChecked(f.bold())
            elif hasattr(it,"pen"):self.prop_stroke.setValue(max(1,int(it.pen().width())))
            if isinstance(it,ShapeGraphicsItem):self.prop_fill.setChecked(it.brush().style()!=Qt.BrushStyle.NoBrush)
        finally:
            for w in widgets:w.blockSignals(False)
    def apply_properties(self,*_):
        items=self.canvas.scene_obj.selectedItems();
        if not items:return
        it=items[0]
        if isinstance(it,QGraphicsTextItem):
            it.setPlainText(self.prop_text.text()); f=QFont(self.prop_font.currentText(),self.prop_size.value()); f.setBold(self.prop_bold.isChecked()); it.setFont(f)
        elif isinstance(it,ShapeGraphicsItem):
            it.setPen(QPen(QColor("#111827"),self.prop_stroke.value(),Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin)); it.setBrush(QBrush(QColor("#111827")) if self.prop_fill.isChecked() else Qt.BrushStyle.NoBrush)
        elif hasattr(it,"setPen"):it.setPen(QPen(QColor("#111827"),self.prop_stroke.value()))
        self.canvas.scene_modified.emit()
    def _template_elements(self):return [e.__dict__ for e in self.canvas.elements()]
    def save_template(self):
        name,ok=QInputDialog.getText(self,"Guardar diseño","Nombre:");
        if not ok or not name.strip():return
        groups=self.state.groups or ["General"]; group,ok=QInputDialog.getItem(self,"Grupo","Grupo:",groups,0,False)
        if not ok:return
        w,h=self.size_combo.currentData(); tid=self.current_template_id or uuid.uuid4().hex; existing=next((t for t in self.state.templates if t.id==tid),None)
        if existing:existing.name=name.strip(); existing.group=group; existing.width_mm=w; existing.height_mm=h; existing.elements=self._template_elements()
        else:self.state.templates.append(Template(tid,name.strip(),group,w,h,self._template_elements()))
        self.current_template_id=tid; self.state.last_template_id=tid; self.save_state(); self.refresh_templates()
    def duplicate_template(self):self.current_template_id=None; self.save_template()
    def load_template_item(self,item):
        tid=item.data(Qt.ItemDataRole.UserRole); t=next((x for x in self.state.templates if x.id==tid),None)
        if not t:return
        idx=self.size_combo.findData((t.width_mm,t.height_mm)); self.size_combo.blockSignals(True); self.size_combo.setCurrentIndex(max(0,idx)); self.size_combo.blockSignals(False); self.canvas.width_mm=t.width_mm; self.canvas.height_mm=t.height_mm; self.canvas.load_elements(t.elements); self.current_template_id=t.id; self.state.last_template_id=t.id
    def export_png(self):
        path,_=QFileDialog.getSaveFileName(self,"Exportar PNG","etiqueta.png","PNG (*.png)")
        if path:
            img=render_label(self.canvas.elements(),*self.size_combo.currentData()); img.resize((img.width*8,img.height*8)).save(path)
    def toggle_connect(self):
        self._connect_generation+=1; generation=self._connect_generation
        if self.printer.snapshot.connected:
            self._want_connected=False; self.conn.setText("Desconectando D30…"); self.wait_future(self.printer.disconnect())
        else:
            self._want_connected=True; self.connect_btn.setEnabled(False); self.conn.setText("Buscando D30 con Windows…"); fut=self.printer.connect(self.state.last_device_address,timeout=20); self.wait_future(fut); QTimer.singleShot(23000,lambda:self._connect_watchdog(fut,generation))
    def _connect_watchdog(self,fut:Future,generation:int):
        if generation!=self._connect_generation or fut.done():return
        self._want_connected=False
        try:self.printer.cancel_pending_connection()
        except Exception:pass
        self.connect_btn.setEnabled(True); self.connect_btn.setText("Conectar D30"); self.conn.setText("La conexión tardó demasiado · podés reintentar")
    def wait_future(self,fut:Future,msg=""):
        if msg:self.statusBar().showMessage(msg)
        def done(f):
            try:self.bridge.future_done.emit(f.result(),None)
            except Exception as e:self.bridge.future_done.emit(None,e)
        fut.add_done_callback(done)
    def on_future_done(self,result,error):
        if isinstance(result,tuple) and result and result[0] in ("maintenance","maintenance_error"):
            self._maintenance_inflight=False
            if result[0]=="maintenance" and isinstance(result[1],dict) and result[1].get("connected"):self._want_connected=True
            elif self._want_connected:self.conn.setText("D30 desconectada · reintentando automáticamente…")
            return
        self.connect_btn.setEnabled(True); self.progress.hide()
        if error:
            if not self.printer.snapshot.connected:self.conn.setText("D30 desconectada")
            QMessageBox.warning(self,APP_NAME,str(error)); self.statusBar().showMessage(str(error),7000); return
        if isinstance(result,tuple) and result and result[0]=="printed":
            self.roll_remaining.setValue(max(0,self.roll_remaining.value()-int(result[1]))); self.update_roll_ui(); self.save_state()
        elif isinstance(result,tuple) and result and result[0]=="calibrated":
            self.update_roll_ui(); self.save_state(); self.statusBar().showMessage("Calibración terminada · contador del rollo sin cambios",6000)
    def on_printer_status(self,s:PrinterSnapshot):
        self.conn.setText(s.message); self.battery.setText(f"Batería {s.battery}%" if s.battery is not None else "Batería —"); self.paper.setText(f"Papel {s.paper}" if s.paper else "Papel —"); self.connect_btn.setText("Desconectar" if s.connected else "Conectar D30")
        if s.connected:self._want_connected=True
        if s.address:self.state.last_device_address=s.address
    def _maintain_connection(self):
        if not self._want_connected or self._maintenance_inflight or not self.auto_reconnect.isChecked():return
        self._maintenance_inflight=True; fut=self.printer.maintain_connection(self.state.last_device_address,timeout=18)
        def done(f):
            try:self.bridge.future_done.emit(("maintenance",f.result()),None)
            except Exception as e:self.bridge.future_done.emit(("maintenance_error",str(e)),None)
        fut.add_done_callback(done)
    def usable_labels(self):return max(0,self.roll_remaining.value()-1)
    def _pack_current(self):
        img=render_label(self.canvas.elements(),*self.size_combo.currentData()); raster,w,h=image_to_d30_raster(img); return make_print_packet(raster,w,h,self.density.value(),self.continuous.isChecked(),self.feed.value())
    def print_current(self):
        if self.usable_labels()<=0:QMessageBox.warning(self,APP_NAME,"No quedan etiquetas utilizables. La última etiqueta física se reserva para el final del rollo."); return
        try:packets=self._pack_current()
        except Exception as e:QMessageBox.warning(self,APP_NAME,str(e)); return
        self.progress.setRange(0,100); self.progress.setValue(0); self.progress.show(); fut=self.printer.send_packets(packets,lambda d,t:self.bridge.print_progress.emit(d,t)); fut.add_done_callback(lambda f:self._print_done(f,1))
    def on_print_progress(self,d,t):self.progress.setValue(int(d*100/t) if t else 0)
    def _print_done(self,fut,count):
        try:fut.result(); self.bridge.future_done.emit(("printed",count),None)
        except Exception as e:self.bridge.future_done.emit(None,e)
    def queue_current(self):self.queue.append(self._template_elements()); self.queue_list.addItem(f"Etiqueta {len(self.queue)} · 1 copia")
    def clear_queue(self):self.queue.clear(); self.queue_list.clear()
    def print_queue(self):
        if not self.queue:return
        if self.usable_labels()<len(self.queue):QMessageBox.warning(self,APP_NAME,f"No alcanzan las etiquetas utilizables. Quedan {self.roll_remaining.value()} físicas y {self.usable_labels()} utilizables."); return
        packs=[]
        try:
            wmm,hmm=self.size_combo.currentData()
            for els in self.queue:
                img=render_label([Element(**{k:v for k,v in x.items() if k in Element.__dataclass_fields__}) for x in els],wmm,hmm); raster,w,h=image_to_d30_raster(img); packs.extend(make_print_packet(raster,w,h,self.density.value(),self.continuous.isChecked(),self.feed.value()))
            self.progress.show(); fut=self.printer.send_packets(packs,lambda d,t:self.bridge.print_progress.emit(d,t)); fut.add_done_callback(lambda f:self._print_done(f,len(self.queue)))
        except Exception as e:QMessageBox.warning(self,APP_NAME,str(e))
    def calibrate(self):
        wmm,hmm=self.size_combo.currentData(); w,h=label_pixels(wmm,hmm); from PIL import Image
        blank=Image.new("L",(w,h),255); raster,rw,rh=image_to_d30_raster(blank); self.progress.setRange(0,0); self.progress.show(); self.statusBar().showMessage("Calibrando D30 / rollo…"); fut=self.printer.calibrate(raster,rw,rh); fut.add_done_callback(self._calibration_done)
    def _calibration_done(self,fut):
        try:fut.result(); self.bridge.future_done.emit(("calibrated",0),None)
        except Exception as e:self.bridge.future_done.emit(None,e)
    def update_roll_ui(self):
        usable=self.usable_labels(); self.roll_usable.setText(str(usable)); self.roll_status.setText(f"Rollo {self.roll_remaining.value()}/{self.roll_total.value()} · útiles {usable}")
    def check_updates(self,auto=False):
        if self._update_thread and self._update_thread.isRunning():return
        self.update_btn.setEnabled(False); self.update_btn.setText("Buscando…"); self.progress.setRange(0,100); self.progress.setValue(0); self.progress.show(); self._update_thread=UpdaterThread(__version__,download=not auto); self._update_thread.progress.connect(self.on_update_progress); self._update_thread.done.connect(lambda info,result:self.on_update_done(info,result,auto)); self._update_thread.start()
    def on_update_progress(self,msg,pct):self.statusBar().showMessage(msg); self.update_state.setText(msg); self.progress.setValue(pct)
    def on_update_done(self,info,result,auto):
        self.update_btn.setEnabled(True); self.progress.hide()
        if isinstance(result,Exception):
            self.update_btn.setText("Buscar actualizaciones"); self.update_state.setText(f"No se pudo actualizar: {result}")
            if not auto:QMessageBox.warning(self,APP_NAME,f"No pude actualizar:\n\n{result}")
            return
        if info is None:
            self.update_btn.setText("Buscar actualizaciones"); self.update_state.setText(f"Phomemo Studio {__version__} está actualizado")
            if not auto:QMessageBox.information(self,APP_NAME,f"Ya tenés la última versión ({__version__}).")
            return
        if auto:
            self.update_btn.setText(f"Actualizar a {info.version}"); self.update_state.setText(f"Nueva versión disponible: {info.version}"); return
        path=result
        if not path:
            self.update_btn.setText(f"Actualizar a {info.version}"); return
        self.update_btn.setText("Instalando…"); self.update_state.setText(f"Instalando {info.version}. Phomemo Studio se cerrará automáticamente…"); self.save_state()
        try:self.printer.close()
        except Exception:pass
        try:updater.launch_installer(path)
        except Exception as e:
            self.update_btn.setEnabled(True); self.update_btn.setText("Reintentar actualización"); QMessageBox.warning(self,APP_NAME,f"La descarga está lista, pero no pude iniciar el instalador:\n\n{e}"); return
        QTimer.singleShot(250,lambda:QApplication.instance().quit())
    def save_state(self):
        self.state.roll_name=self.roll_name.text(); self.state.roll_total=self.roll_total.value(); self.state.roll_remaining=min(self.roll_remaining.value(),self.roll_total.value()); self.state.density=self.density.value(); self.state.continuous=self.continuous.isChecked(); self.state.feed_dots=self.feed.value(); self.state.auto_reconnect=self.auto_reconnect.isChecked(); self.store.save(self.state); self.update_roll_ui()
    def closeEvent(self,e):
        self.save_state();
        try:self.printer.close()
        except Exception:pass
        super().closeEvent(e)
