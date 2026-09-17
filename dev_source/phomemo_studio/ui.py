from __future__ import annotations

import copy
import os
import sys
import time
import uuid
from pathlib import Path
from concurrent.futures import Future

from PySide6.QtCore import Qt, QRectF, QTimer, Signal, QObject, QThread
from PySide6.QtGui import QAction, QColor, QIcon, QImage, QPainter, QPen, QPixmap, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QSlider, QFileDialog, QMessageBox, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsPixmapItem, QDockWidget, QGroupBox,
    QFormLayout, QToolBar, QStatusBar, QProgressBar, QInputDialog, QAbstractItemView,
    QSplitter, QDialog, QDialogButtonBox
)

from . import __version__
from .core import AppState, StateStore, Element, Template, label_pixels, make_print_packet
from .printer import D30Printer, PrinterSnapshot
from .render import render_label, image_to_d30_raster
from . import updater

APP_NAME = "Phomemo Studio"

class Bridge(QObject):
    printer_status = Signal(object)
    print_progress = Signal(int, int)
    future_done = Signal(object, object)
    update_progress = Signal(str, int)

class UpdaterThread(QThread):
    progress = Signal(str, int)
    done = Signal(object, object)
    def __init__(self, current: str):
        super().__init__(); self.current=current
    def run(self):
        try:
            self.progress.emit("Buscando actualización…", 0)
            info=updater.get_latest()
            if updater.parse_version(info.version) <= updater.parse_version(self.current):
                self.done.emit(None, None); return
            self.progress.emit(f"Descargando {info.version}…", 1)
            path=updater.download_verified(info, lambda d,t:self.progress.emit(
                f"Descargando {info.version}…", int(d*100/t) if t else 0))
            self.done.emit(info,path)
        except Exception as e:
            self.done.emit(None,e)

class CanvasView(QGraphicsView):
    selection_changed = Signal(object)
    scene_modified = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_obj=QGraphicsScene(self); self.setScene(self.scene_obj)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setBackgroundBrush(QColor("#dfe2e7"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.width_mm=40; self.height_mm=12
        self._page=None
        self.scene_obj.selectionChanged.connect(self._sel)
        self.set_label_size(40,12)
    def _sel(self):
        items=self.scene_obj.selectedItems(); self.selection_changed.emit(items[0] if items else None)
    def set_label_size(self,wmm,hmm):
        self.width_mm=wmm; self.height_mm=hmm; w,h=label_pixels(wmm,hmm)
        self.scene_obj.clear(); self.scene_obj.setSceneRect(-30,-30,w+60,h+60)
        self._page=QGraphicsRectItem(0,0,w,h); self._page.setBrush(Qt.GlobalColor.white)
        self._page.setPen(QPen(QColor("#b9bec8"),1)); self._page.setZValue(-100); self.scene_obj.addItem(self._page)
        self.fitInView(QRectF(-15,-15,w+30,h+30),Qt.AspectRatioMode.KeepAspectRatio)
    def resizeEvent(self,e):
        super().resizeEvent(e)
        w,h=label_pixels(self.width_mm,self.height_mm)
        self.fitInView(QRectF(-15,-15,w+30,h+30),Qt.AspectRatioMode.KeepAspectRatio)
    def add_text(self,text="Texto"):
        item=QGraphicsTextItem(text); item.setDefaultTextColor(Qt.GlobalColor.black); item.setFont(QFont("Arial",16))
        self._flags(item); item.setPos(20,20); self.scene_obj.addItem(item); item.setSelected(True); self.scene_modified.emit(); return item
    def add_rect(self):
        item=QGraphicsRectItem(0,0,80,40); item.setPen(QPen(Qt.GlobalColor.black,2)); self._flags(item); item.setPos(20,20); self.scene_obj.addItem(item); item.setSelected(True); self.scene_modified.emit(); return item
    def add_line(self):
        item=QGraphicsLineItem(0,0,100,0); item.setPen(QPen(Qt.GlobalColor.black,2)); self._flags(item); item.setPos(20,40); self.scene_obj.addItem(item); item.setSelected(True); self.scene_modified.emit(); return item
    def add_image(self,path):
        pix=QPixmap(path)
        if pix.isNull(): raise ValueError("No pude abrir la imagen")
        item=QGraphicsPixmapItem(pix.scaled(120,80,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self._flags(item); item.setPos(20,10); item.setData(0,path); self.scene_obj.addItem(item); item.setSelected(True); self.scene_modified.emit(); return item
    def _flags(self,item):
        item.setFlags(item.flags() | item.GraphicsItemFlag.ItemIsMovable | item.GraphicsItemFlag.ItemIsSelectable | item.GraphicsItemFlag.ItemSendsGeometryChanges)
    def delete_selected(self):
        for i in list(self.scene_obj.selectedItems()): self.scene_obj.removeItem(i)
        self.scene_modified.emit()
    def keyPressEvent(self,e):
        if e.key() in (Qt.Key.Key_Delete,Qt.Key.Key_Backspace): self.delete_selected(); return
        super().keyPressEvent(e)
    def elements(self):
        out=[]
        for it in self.scene_obj.items():
            if it is self._page: continue
            p=it.pos(); br=it.boundingRect()
            if isinstance(it,QGraphicsTextItem):
                f=it.font(); out.append(Element("text",p.x(),p.y(),br.width(),br.height(),text=it.toPlainText(),font=f.family(),font_size=f.pointSize(),bold=f.bold()))
            elif isinstance(it,QGraphicsRectItem):
                out.append(Element("rect",p.x(),p.y(),br.width(),br.height(),stroke=max(1,int(it.pen().width()))))
            elif isinstance(it,QGraphicsLineItem):
                line=it.line(); out.append(Element("line",p.x()+line.x1(),p.y()+line.y1(),line.x2()-line.x1(),line.y2()-line.y1(),stroke=max(1,int(it.pen().width()))))
            elif isinstance(it,QGraphicsPixmapItem):
                out.append(Element("image",p.x(),p.y(),br.width(),br.height(),path=it.data(0) or ""))
        return out
    def load_elements(self,elements):
        self.set_label_size(self.width_mm,self.height_mm)
        for raw in elements:
            e=Element(**raw) if isinstance(raw,dict) else raw
            if e.kind=="text":
                it=self.add_text(e.text); f=QFont(e.font,e.font_size); f.setBold(e.bold); it.setFont(f); it.setPos(e.x,e.y)
            elif e.kind=="rect":
                it=self.add_rect(); it.setRect(0,0,e.w,e.h); it.setPos(e.x,e.y); it.setPen(QPen(Qt.GlobalColor.black,e.stroke))
            elif e.kind=="line":
                it=self.add_line(); it.setLine(0,0,e.w,e.h); it.setPos(e.x,e.y); it.setPen(QPen(Qt.GlobalColor.black,e.stroke))
            elif e.kind=="image" and e.path and Path(e.path).exists():
                try:
                    it=self.add_image(e.path); it.setPos(e.x,e.y)
                except Exception: pass
        self.scene_obj.clearSelection()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1460,900); self.setMinimumSize(1080,720)
        icon=self.asset("sr-gato.png"); self.setWindowIcon(QIcon(str(icon)))
        self.store=StateStore(); self.state=self.store.load(); self.bridge=Bridge()
        self.printer=D30Printer(lambda s:self.bridge.printer_status.emit(copy.copy(s)))
        self.bridge.printer_status.connect(self.on_printer_status)
        self.bridge.print_progress.connect(self.on_print_progress)
        self.bridge.future_done.connect(self.on_future_done)
        self.current_template_id=None; self.queue=[]; self._update_thread=None
        self._build_ui(); self._apply_state(); self.refresh_templates(); self.update_roll_ui()
        self._autosave=QTimer(self); self._autosave.setInterval(1200); self._autosave.setSingleShot(True); self._autosave.timeout.connect(self.save_state)
        self.canvas.scene_modified.connect(lambda:self._autosave.start())
        QTimer.singleShot(2500, lambda:self.check_updates(auto=True))
    def asset(self,name):
        root=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent.parent)); p=root/"assets"/name
        return p
    def _build_ui(self):
        self.setStyleSheet("""
        QMainWindow{background:#eef1f6} QToolBar{background:#ffffff;border-bottom:1px solid #e3e7ef;spacing:6px;padding:6px}
        QPushButton{padding:7px 11px;border:1px solid #d8ddea;border-radius:8px;background:white;color:#283044} QPushButton:hover{background:#f3f0ff;border-color:#cbbfff}
        QPushButton#primary{background:#6c4cf1;color:white;border:0;font-weight:600} QListWidget,QLineEdit,QComboBox,QSpinBox{border:1px solid #dfe3eb;border-radius:8px;padding:6px;background:white}
        QGroupBox{font-weight:600;border:1px solid #e3e7ef;border-radius:10px;margin-top:10px;padding-top:10px;background:white} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px}
        QDockWidget{background:white} QStatusBar{background:#fbfbfd;border-top:1px solid #e3e7ef}
        """)
        tb=QToolBar("Edición",self); tb.setMovable(False); self.addToolBar(tb)
        def add_btn(text,slot,primary=False):
            b=QPushButton(text); b.setObjectName("primary" if primary else ""); b.clicked.connect(slot); tb.addWidget(b); return b
        add_btn("Vacía",self.new_blank); add_btn("Texto",lambda:self.canvas.add_text()); add_btn("Forma",lambda:self.canvas.add_rect()); add_btn("Línea",lambda:self.canvas.add_line()); add_btn("Subir imagen",self.pick_image)
        tb.addSeparator(); self.size_combo=QComboBox();
        for w,h in [(40,12),(30,12),(22,12),(12,12),(30,14),(40,15),(30,15)]: self.size_combo.addItem(f"{w} × {h} mm",(w,h))
        self.size_combo.currentIndexChanged.connect(self.change_size); tb.addWidget(self.size_combo)
        add_btn("Guardar",self.save_template); add_btn("Duplicar",self.duplicate_template); add_btn("PNG",self.export_png); add_btn("Imprimir actual",self.print_current,True)
        splitter=QSplitter(); self.setCentralWidget(splitter)
        left=QWidget(); lv=QVBoxLayout(left); lv.setContentsMargins(10,10,10,10)
        head=QHBoxLayout(); title=QLabel("Diseños"); title.setStyleSheet("font-size:18px;font-weight:700"); head.addWidget(title); ng=QPushButton("+ Grupo"); ng.clicked.connect(self.new_group); head.addWidget(ng); lv.addLayout(head)
        self.search=QLineEdit(); self.search.setPlaceholderText("Buscar diseños…"); self.search.textChanged.connect(self.refresh_templates); lv.addWidget(self.search)
        self.group_filter=QComboBox(); self.group_filter.currentIndexChanged.connect(self.refresh_templates); lv.addWidget(self.group_filter)
        self.template_list=QListWidget(); self.template_list.itemDoubleClicked.connect(self.load_template_item); lv.addWidget(self.template_list,1)
        splitter.addWidget(left)
        self.canvas=CanvasView(); splitter.addWidget(self.canvas)
        right=QWidget(); rv=QVBoxLayout(right); rv.setContentsMargins(10,10,10,10)
        pbox=QGroupBox("Propiedades"); pf=QFormLayout(pbox)
        self.prop_text=QLineEdit(); self.prop_font=QComboBox(); self.prop_font.addItems(["Arial","Segoe UI","Verdana","Trebuchet MS","Georgia","Courier New"]); self.prop_size=QSpinBox(); self.prop_size.setRange(6,72); self.prop_bold=QCheckBox("Negrita"); self.prop_stroke=QSpinBox(); self.prop_stroke.setRange(1,8)
        pf.addRow("Texto",self.prop_text); pf.addRow("Fuente",self.prop_font); pf.addRow("Tamaño",self.prop_size); pf.addRow("",self.prop_bold); pf.addRow("Grosor",self.prop_stroke); dele=QPushButton("Eliminar elemento"); dele.clicked.connect(self.canvas.delete_selected); pf.addRow(dele); rv.addWidget(pbox)
        self.canvas.selection_changed.connect(self.selection_changed)
        for w in [self.prop_text,self.prop_font,self.prop_size,self.prop_bold,self.prop_stroke]:
            sig = getattr(w,"textChanged",None) or getattr(w,"currentIndexChanged",None) or getattr(w,"valueChanged",None) or getattr(w,"toggled",None)
            sig.connect(self.apply_properties)
        qbox=QGroupBox("Cola de impresión"); qv=QVBoxLayout(qbox); self.queue_list=QListWidget(); qv.addWidget(self.queue_list); qr=QHBoxLayout(); qa=QPushButton("+ Actual"); qa.clicked.connect(self.queue_current); qc=QPushButton("Vaciar"); qc.clicked.connect(self.clear_queue); qr.addWidget(qa); qr.addWidget(qc); qv.addLayout(qr); qp=QPushButton("Imprimir todo"); qp.setObjectName("primary"); qp.clicked.connect(self.print_queue); qv.addWidget(qp); rv.addWidget(qbox,1)
        rbox=QGroupBox("Rollo y calibración"); rf=QFormLayout(rbox); self.roll_name=QLineEdit(); self.roll_total=QSpinBox(); self.roll_total.setRange(1,9999); self.roll_remaining=QSpinBox(); self.roll_remaining.setRange(0,9999); rf.addRow("Nombre",self.roll_name); rf.addRow("Inicial",self.roll_total); rf.addRow("Restantes",self.roll_remaining); cal=QPushButton("Calibrar rollo"); cal.clicked.connect(self.calibrate); rf.addRow(cal); rv.addWidget(rbox)
        sbox=QGroupBox("Ajustes de impresión"); sf=QFormLayout(sbox); self.density=QSlider(Qt.Orientation.Horizontal); self.density.setRange(1,8); self.density_label=QLabel(); self.density.valueChanged.connect(lambda v:self.density_label.setText(str(v))); row=QWidget(); rh=QHBoxLayout(row); rh.setContentsMargins(0,0,0,0); rh.addWidget(self.density); rh.addWidget(self.density_label); self.continuous=QCheckBox("Rollo continuo"); self.feed=QSpinBox(); self.feed.setRange(0,255); self.auto_reconnect=QCheckBox("Reconexión automática"); sf.addRow("Densidad",row); sf.addRow(self.continuous); sf.addRow("Avance extra",self.feed); sf.addRow(self.auto_reconnect); rv.addWidget(sbox)
        ub=QGroupBox("Aplicación"); uh=QHBoxLayout(ub); self.update_btn=QPushButton("Buscar actualizaciones"); self.update_btn.clicked.connect(lambda:self.check_updates(auto=False)); uh.addWidget(self.update_btn); rv.addWidget(ub)
        splitter.addWidget(right); splitter.setSizes([260,880,320])
        sb=QStatusBar(); self.setStatusBar(sb); self.conn=QLabel("D30 desconectada"); self.battery=QLabel("Batería —"); self.paper=QLabel("Papel —"); self.roll_status=QLabel(); self.progress=QProgressBar(); self.progress.setFixedWidth(170); self.progress.hide(); self.connect_btn=QPushButton("Conectar D30"); self.connect_btn.setObjectName("primary"); self.connect_btn.clicked.connect(self.toggle_connect)
        sb.addWidget(self.conn,1); sb.addPermanentWidget(self.battery); sb.addPermanentWidget(self.paper); sb.addPermanentWidget(self.roll_status); sb.addPermanentWidget(self.progress); sb.addPermanentWidget(self.connect_btn)
    def _apply_state(self):
        self.roll_name.setText(self.state.roll_name); self.roll_total.setValue(self.state.roll_total); self.roll_remaining.setValue(self.state.roll_remaining); self.density.setValue(self.state.density); self.continuous.setChecked(self.state.continuous); self.feed.setValue(self.state.feed_dots); self.auto_reconnect.setChecked(self.state.auto_reconnect)
        self.refresh_groups()
        for w in [self.roll_name,self.roll_total,self.roll_remaining,self.density,self.continuous,self.feed,self.auto_reconnect]:
            sig=getattr(w,"textChanged",None) or getattr(w,"valueChanged",None) or getattr(w,"toggled",None); sig.connect(lambda *_:self._autosave.start() if hasattr(self,"_autosave") else None)
    def refresh_groups(self):
        current=self.group_filter.currentText(); self.group_filter.blockSignals(True); self.group_filter.clear(); self.group_filter.addItem("Todos los grupos"); self.group_filter.addItems(self.state.groups); idx=self.group_filter.findText(current); self.group_filter.setCurrentIndex(max(0,idx)); self.group_filter.blockSignals(False)
    def refresh_templates(self):
        if not hasattr(self,"template_list"): return
        q=self.search.text().lower().strip() if hasattr(self,"search") else ""; g=self.group_filter.currentText() if hasattr(self,"group_filter") else "Todos los grupos"; self.template_list.clear()
        for t in self.state.templates:
            if q and q not in t.name.lower(): continue
            if g and g!="Todos los grupos" and t.group!=g: continue
            item=QListWidgetItem(f"{t.name}\n{t.group} · {t.width_mm}×{t.height_mm} mm"); item.setData(Qt.ItemDataRole.UserRole,t.id); self.template_list.addItem(item)
    def new_group(self):
        name,ok=QInputDialog.getText(self,"Nuevo grupo","Nombre del grupo / cafetería:")
        if ok and name.strip() and name.strip() not in self.state.groups:
            self.state.groups.append(name.strip()); self.refresh_groups(); self.save_state()
    def new_blank(self): self.current_template_id=None; self.canvas.set_label_size(*self.size_combo.currentData())
    def change_size(self):
        data=self.size_combo.currentData();
        if data: self.canvas.set_label_size(*data)
    def pick_image(self):
        path,_=QFileDialog.getOpenFileName(self,"Subir imagen","","Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            try:self.canvas.add_image(path)
            except Exception as e: QMessageBox.warning(self,APP_NAME,str(e))
    def selection_changed(self,it):
        for w in [self.prop_text,self.prop_font,self.prop_size,self.prop_bold,self.prop_stroke]: w.blockSignals(True)
        try:
            if isinstance(it,QGraphicsTextItem): f=it.font(); self.prop_text.setText(it.toPlainText()); self.prop_font.setCurrentText(f.family()); self.prop_size.setValue(max(6,f.pointSize())); self.prop_bold.setChecked(f.bold())
            elif hasattr(it,"pen"): self.prop_stroke.setValue(max(1,int(it.pen().width())))
        finally:
            for w in [self.prop_text,self.prop_font,self.prop_size,self.prop_bold,self.prop_stroke]: w.blockSignals(False)
    def apply_properties(self,*_):
        items=self.canvas.scene_obj.selectedItems();
        if not items:return
        it=items[0]
        if isinstance(it,QGraphicsTextItem):
            it.setPlainText(self.prop_text.text()); f=QFont(self.prop_font.currentText(),self.prop_size.value()); f.setBold(self.prop_bold.isChecked()); it.setFont(f)
        elif hasattr(it,"setPen"): it.setPen(QPen(Qt.GlobalColor.black,self.prop_stroke.value()))
        self.canvas.scene_modified.emit()
    def _template_elements(self): return [e.__dict__ for e in self.canvas.elements()]
    def save_template(self):
        name,ok=QInputDialog.getText(self,"Guardar plantilla","Nombre:")
        if not ok or not name.strip(): return
        group,ok=QInputDialog.getItem(self,"Grupo","Grupo:",self.state.groups,0,False)
        if not ok:return
        w,h=self.size_combo.currentData(); tid=self.current_template_id or uuid.uuid4().hex
        existing=next((t for t in self.state.templates if t.id==tid),None)
        if existing: existing.name=name.strip(); existing.group=group; existing.width_mm=w; existing.height_mm=h; existing.elements=self._template_elements()
        else:self.state.templates.append(Template(tid,name.strip(),group,w,h,self._template_elements()))
        self.current_template_id=tid; self.state.last_template_id=tid; self.save_state(); self.refresh_templates()
    def duplicate_template(self): self.current_template_id=None; self.save_template()
    def load_template_item(self,item):
        tid=item.data(Qt.ItemDataRole.UserRole); t=next((x for x in self.state.templates if x.id==tid),None)
        if not t:return
        idx=self.size_combo.findData((t.width_mm,t.height_mm)); self.size_combo.blockSignals(True); self.size_combo.setCurrentIndex(max(0,idx)); self.size_combo.blockSignals(False); self.canvas.width_mm=t.width_mm; self.canvas.height_mm=t.height_mm; self.canvas.load_elements(t.elements); self.current_template_id=t.id; self.state.last_template_id=t.id
    def export_png(self):
        path,_=QFileDialog.getSaveFileName(self,"Exportar PNG","etiqueta.png","PNG (*.png)")
        if path: render_label(self.canvas.elements(),*self.size_combo.currentData()).resize((label_pixels(*self.size_combo.currentData())[0]*8,label_pixels(*self.size_combo.currentData())[1]*8)).save(path)
    def toggle_connect(self):
        if self.printer.snapshot.connected:
            fut=self.printer.disconnect(); self.wait_future(fut,"Desconectando…")
        else:
            self.connect_btn.setEnabled(False); self.conn.setText("Buscando D30…"); fut=self.printer.connect(self.state.last_device_address); self.wait_future(fut,"Conectando…")
    def wait_future(self,fut:Future,msg=""):
        if msg:self.statusBar().showMessage(msg)
        def done(f):
            try:r=f.result(); self.bridge.future_done.emit(r,None)
            except Exception as e:self.bridge.future_done.emit(None,e)
        fut.add_done_callback(done)
    def on_future_done(self,result,error):
        self.connect_btn.setEnabled(True); self.progress.hide()
        if error: QMessageBox.warning(self,APP_NAME,str(error)); self.statusBar().showMessage(str(error),5000)
    def on_printer_status(self,s:PrinterSnapshot):
        self.conn.setText(s.message); self.battery.setText(f"Batería {s.battery}%" if s.battery is not None else "Batería —"); self.paper.setText(f"Papel {s.paper}" if s.paper else "Papel —"); self.connect_btn.setText("Desconectar" if s.connected else "Conectar D30")
        if s.address: self.state.last_device_address=s.address
    def _pack_current(self):
        img=render_label(self.canvas.elements(),*self.size_combo.currentData()); raster,w,h=image_to_d30_raster(img); return make_print_packet(raster,w,h,self.density.value(),self.continuous.isChecked(),self.feed.value())
    def print_current(self):
        if self.roll_remaining.value()<=0: QMessageBox.warning(self,APP_NAME,"El rollo no tiene etiquetas restantes."); return
        try:packets=self._pack_current()
        except Exception as e: QMessageBox.warning(self,APP_NAME,str(e)); return
        self.progress.setRange(0,100); self.progress.setValue(0); self.progress.show(); fut=self.printer.send_packets(packets,lambda d,t:self.bridge.print_progress.emit(d,t)); fut.add_done_callback(lambda f:self._print_done(f,1))
    def on_print_progress(self,d,t): self.progress.setValue(int(d*100/t) if t else 0)
    def _print_done(self,fut,count):
        try:fut.result(); self.roll_remaining.setValue(max(0,self.roll_remaining.value()-count)); self.update_roll_ui(); self.save_state(); self.bridge.future_done.emit(True,None)
        except Exception as e:self.bridge.future_done.emit(None,e)
    def queue_current(self): self.queue.append(self._template_elements()); self.queue_list.addItem(f"Etiqueta {len(self.queue)} · 1 copia")
    def clear_queue(self): self.queue.clear(); self.queue_list.clear()
    def print_queue(self):
        if not self.queue:return
        if self.roll_remaining.value()<len(self.queue): QMessageBox.warning(self,APP_NAME,"No quedan suficientes etiquetas en el rollo."); return
        original=self.canvas.elements(); packs=[]
        try:
            wmm,hmm=self.size_combo.currentData()
            for els in self.queue:
                img=render_label([Element(**x) for x in els],wmm,hmm); raster,w,h=image_to_d30_raster(img); packs.extend(make_print_packet(raster,w,h,self.density.value(),self.continuous.isChecked(),self.feed.value()))
            self.progress.show(); fut=self.printer.send_packets(packs,lambda d,t:self.bridge.print_progress.emit(d,t)); fut.add_done_callback(lambda f:self._print_done(f,len(self.queue)))
        except Exception as e: QMessageBox.warning(self,APP_NAME,str(e))
    def calibrate(self):
        wmm,hmm=self.size_combo.currentData(); w,h=label_pixels(wmm,hmm); from PIL import Image
        blank=Image.new("L",(w,h),255); raster,rw,rh=image_to_d30_raster(blank); fut=self.printer.calibrate(raster,rw,rh); self.wait_future(fut,"Calibrando rollo…")
    def update_roll_ui(self): self.roll_status.setText(f"Rollo {self.roll_remaining.value()}/{self.roll_total.value()}")
    def check_updates(self,auto=False):
        if self._update_thread and self._update_thread.isRunning(): return
        self.update_btn.setEnabled(False); self.update_btn.setText("Buscando…"); self.progress.setRange(0,100); self.progress.setValue(0); self.progress.show()
        self._update_thread=UpdaterThread(__version__); self._update_thread.progress.connect(self.on_update_progress); self._update_thread.done.connect(lambda info,result:self.on_update_done(info,result,auto)); self._update_thread.start()
    def on_update_progress(self,msg,pct): self.statusBar().showMessage(msg); self.progress.setValue(pct)
    def on_update_done(self,info,result,auto):
        self.update_btn.setEnabled(True); self.update_btn.setText("Buscar actualizaciones"); self.progress.hide()
        if isinstance(result,Exception):
            if not auto: QMessageBox.warning(self,APP_NAME,f"No pude actualizar:\n\n{result}"); return
        if info is None:
            if not auto: QMessageBox.information(self,APP_NAME,f"Ya tenés la última versión ({__version__})."); return
        path=result
        answer=QMessageBox.question(self,APP_NAME,f"Phomemo Studio {info.version} se descargó y verificó correctamente.\n\n¿Instalar ahora?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.Yes)
        if answer==QMessageBox.StandardButton.Yes:
            updater.launch_installer(path); QApplication.instance().quit()
    def save_state(self):
        self.state.roll_name=self.roll_name.text(); self.state.roll_total=self.roll_total.value(); self.state.roll_remaining=min(self.roll_remaining.value(),self.roll_total.value()); self.state.density=self.density.value(); self.state.continuous=self.continuous.isChecked(); self.state.feed_dots=self.feed.value(); self.state.auto_reconnect=self.auto_reconnect.isChecked(); self.store.save(self.state); self.update_roll_ui()
    def closeEvent(self,e): self.save_state(); self.printer.close(); super().closeEvent(e)
