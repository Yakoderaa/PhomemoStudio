from pathlib import Path

path = Path("python_app/phomemo_studio/ui.py")
s = path.read_text(encoding="utf-8")


def repl(old: str, new: str, label: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"UI patch {label}: expected 1 match, got {count}")
    s = s.replace(old, new, 1)


repl(
    '        self.current_template_id=None; self.queue=[]; self._update_thread=None\n',
    '        self.current_template_id=None; self.queue=[]; self._update_thread=None; self._connect_generation=0; self._want_connected=False; self._maintenance_inflight=False; self._maintenance_timer=QTimer(self); self._maintenance_timer.setInterval(30000); self._maintenance_timer.timeout.connect(self._maintain_connection); self._maintenance_timer.start()\n',
    'connect generation and maintenance timer',
)
repl(
    '        add_btn("Guardar",self.save_template); add_btn("Duplicar",self.duplicate_template); add_btn("PNG",self.export_png); add_btn("Imprimir actual",self.print_current,True)\n',
    '        add_btn("Guardar",self.save_template); add_btn("Duplicar",self.duplicate_template); add_btn("PNG",self.export_png); add_btn("Calibrar",self.calibrate); add_btn("Imprimir actual",self.print_current,True)\n',
    'toolbar calibrate',
)
repl(
    '        rbox=QGroupBox("Rollo y calibración"); rf=QFormLayout(rbox); self.roll_name=QLineEdit(); self.roll_total=QSpinBox(); self.roll_total.setRange(1,9999); self.roll_remaining=QSpinBox(); self.roll_remaining.setRange(0,9999); rf.addRow("Nombre",self.roll_name); rf.addRow("Inicial",self.roll_total); rf.addRow("Restantes",self.roll_remaining); cal=QPushButton("Calibrar rollo"); cal.clicked.connect(self.calibrate); rf.addRow(cal); rv.addWidget(rbox)\n',
    '        rbox=QGroupBox("Rollo y calibración"); rf=QFormLayout(rbox); self.roll_name=QLineEdit(); self.roll_total=QSpinBox(); self.roll_total.setRange(1,9999); self.roll_remaining=QSpinBox(); self.roll_remaining.setRange(0,9999); self.roll_usable=QLabel(); rf.addRow("Nombre",self.roll_name); rf.addRow("Inicial",self.roll_total); rf.addRow("Restantes físicas",self.roll_remaining); rf.addRow("Utilizables",self.roll_usable); self.calibrate_btn=QPushButton("Calibrar D30 / rollo"); self.calibrate_btn.setObjectName("primary"); self.calibrate_btn.clicked.connect(self.calibrate); rf.addRow(self.calibrate_btn); rv.addWidget(rbox)\n',
    'roll controls',
)
repl(
'''    def toggle_connect(self):
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
''',
'''    def toggle_connect(self):
        self._connect_generation += 1
        generation=self._connect_generation
        if self.printer.snapshot.connected:
            self._want_connected=False
            self.conn.setText("Desconectando D30…")
            fut=self.printer.disconnect(); self.wait_future(fut)
        else:
            self._want_connected=True
            self.connect_btn.setEnabled(False)
            self.conn.setText("Buscando D30 con Windows…")
            self.statusBar().clearMessage()
            fut=self.printer.connect(self.state.last_device_address, timeout=20)
            self.wait_future(fut)
            QTimer.singleShot(23000, lambda:self._connect_watchdog(fut,generation))
    def _connect_watchdog(self,fut:Future,generation:int):
        if generation!=self._connect_generation or fut.done(): return
        self._want_connected=False
        try:self.printer.cancel_pending_connection()
        except Exception:pass
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Conectar D30")
        self.conn.setText("La conexión tardó demasiado · podés reintentar")
        QMessageBox.warning(self,APP_NAME,"Windows tardó demasiado en abrir la D30. El intento fue cancelado; podés volver a pulsar Conectar D30.")
    def wait_future(self,fut:Future,msg=""):
        if msg:self.statusBar().showMessage(msg)
        def done(f):
            try:r=f.result(); self.bridge.future_done.emit(r,None)
            except Exception as e:self.bridge.future_done.emit(None,e)
        fut.add_done_callback(done)
    def on_future_done(self,result,error):
        if isinstance(result,tuple) and result and result[0] in ("maintenance","maintenance_error"):
            self._maintenance_inflight=False
            if result[0]=="maintenance":
                data=result[1]
                if isinstance(data,dict) and data.get("connected"):
                    self._want_connected=True
            elif self._want_connected:
                self.conn.setText("D30 desconectada · reintentando automáticamente…")
            return
        self.connect_btn.setEnabled(True); self.progress.hide(); self.statusBar().clearMessage()
        if error:
            if not self.printer.snapshot.connected:self.conn.setText("D30 desconectada")
            QMessageBox.warning(self,APP_NAME,str(error)); self.statusBar().showMessage(str(error),7000); return
        if isinstance(result,tuple) and result and result[0] in ("printed","calibrated"):
            count=int(result[1])
            self.roll_remaining.setValue(max(0,self.roll_remaining.value()-count))
            self.update_roll_ui(); self.save_state()
            if result[0]=="calibrated": self.statusBar().showMessage("Calibración terminada · consumió 1 etiqueta",6000)
''',
    'connect flow',
)
repl(
'''    def on_printer_status(self,s:PrinterSnapshot):
        self.conn.setText(s.message); self.battery.setText(f"Batería {s.battery}%" if s.battery is not None else "Batería —"); self.paper.setText(f"Papel {s.paper}" if s.paper else "Papel —"); self.connect_btn.setText("Desconectar" if s.connected else "Conectar D30")
        if s.address: self.state.last_device_address=s.address
''',
'''    def on_printer_status(self,s:PrinterSnapshot):
        self.statusBar().clearMessage()
        self.conn.setText(s.message); self.battery.setText(f"Batería {s.battery}%" if s.battery is not None else "Batería —"); self.paper.setText(f"Papel {s.paper}" if s.paper else "Papel —"); self.connect_btn.setText("Desconectar" if s.connected else "Conectar D30")
        if s.connected: self._want_connected=True
        if s.address: self.state.last_device_address=s.address
    def _auto_reconnect_checked(self):
        try:
            return any(box.text()=="Reconexión automática" and box.isChecked() for box in self.findChildren(QCheckBox))
        except Exception:
            return True
    def _maintain_connection(self):
        if not self._want_connected or self._maintenance_inflight or not self._auto_reconnect_checked(): return
        self._maintenance_inflight=True
        fut=self.printer.maintain_connection(self.state.last_device_address, timeout=18)
        def done(f):
            try:self.bridge.future_done.emit(("maintenance",f.result()),None)
            except Exception as e:self.bridge.future_done.emit(("maintenance_error",str(e)),None)
        fut.add_done_callback(done)
    def usable_labels(self):
        # La última etiqueta física queda inutilizable por estar demasiado cerca del final del rollo.
        return max(0,self.roll_remaining.value()-1)
''',
    'status keepalive and usable labels helper',
)
repl(
'''    def print_current(self):
        if self.roll_remaining.value()<=0: QMessageBox.warning(self,APP_NAME,"El rollo no tiene etiquetas restantes."); return
        try:packets=self._pack_current()
        except Exception as e: QMessageBox.warning(self,APP_NAME,str(e)); return
        self.progress.setRange(0,100); self.progress.setValue(0); self.progress.show(); fut=self.printer.send_packets(packets,lambda d,t:self.bridge.print_progress.emit(d,t)); fut.add_done_callback(lambda f:self._print_done(f,1))
    def on_print_progress(self,d,t): self.progress.setValue(int(d*100/t) if t else 0)
    def _print_done(self,fut,count):
        try:fut.result(); self.roll_remaining.setValue(max(0,self.roll_remaining.value()-count)); self.update_roll_ui(); self.save_state(); self.bridge.future_done.emit(True,None)
        except Exception as e:self.bridge.future_done.emit(None,e)
''',
'''    def print_current(self):
        if self.usable_labels()<=0:
            QMessageBox.warning(self,APP_NAME,"No quedan etiquetas utilizables. La última etiqueta física del rollo se reserva porque está demasiado cerca del final para imprimir correctamente."); return
        try:packets=self._pack_current()
        except Exception as e: QMessageBox.warning(self,APP_NAME,str(e)); return
        self.progress.setRange(0,100); self.progress.setValue(0); self.progress.show(); fut=self.printer.send_packets(packets,lambda d,t:self.bridge.print_progress.emit(d,t)); fut.add_done_callback(lambda f:self._print_done(f,1))
    def on_print_progress(self,d,t): self.progress.setValue(int(d*100/t) if t else 0)
    def _print_done(self,fut,count):
        try:fut.result(); self.bridge.future_done.emit(("printed",count),None)
        except Exception as e:self.bridge.future_done.emit(None,e)
''',
    'single print reserve',
)
repl(
    '        if self.roll_remaining.value()<len(self.queue): QMessageBox.warning(self,APP_NAME,"No quedan suficientes etiquetas en el rollo."); return\n',
    '        if self.usable_labels()<len(self.queue): QMessageBox.warning(self,APP_NAME,f"No alcanzan las etiquetas utilizables. Quedan {self.roll_remaining.value()} físicas, pero solo {self.usable_labels()} se pueden imprimir porque la última se reserva."); return\n',
    'queue reserve',
)
repl(
'''    def calibrate(self):
        wmm,hmm=self.size_combo.currentData(); w,h=label_pixels(wmm,hmm); from PIL import Image
        blank=Image.new("L",(w,h),255); raster,rw,rh=image_to_d30_raster(blank); fut=self.printer.calibrate(raster,rw,rh); self.wait_future(fut,"Calibrando rollo…")
    def update_roll_ui(self): self.roll_status.setText(f"Rollo {self.roll_remaining.value()}/{self.roll_total.value()}")
''',
'''    def calibrate(self):
        if self.usable_labels()<=0:
            QMessageBox.warning(self,APP_NAME,"No hay una etiqueta utilizable para calibrar. La última etiqueta física se reserva porque está demasiado cerca del final del rollo."); return
        wmm,hmm=self.size_combo.currentData(); w,h=label_pixels(wmm,hmm); from PIL import Image
        blank=Image.new("L",(w,h),255); raster,rw,rh=image_to_d30_raster(blank)
        self.progress.setRange(0,0); self.progress.show(); self.statusBar().showMessage("Calibrando D30 / rollo…")
        fut=self.printer.calibrate(raster,rw,rh); fut.add_done_callback(self._calibration_done)
    def _calibration_done(self,fut):
        try:fut.result(); self.bridge.future_done.emit(("calibrated",1),None)
        except Exception as e:self.bridge.future_done.emit(None,e)
    def update_roll_ui(self):
        usable=self.usable_labels()
        if hasattr(self,"roll_usable"): self.roll_usable.setText(str(usable))
        self.roll_status.setText(f"Rollo {self.roll_remaining.value()}/{self.roll_total.value()} · útiles {usable}")
''',
    'calibration and roll UI',
)

path.write_text(s, encoding="utf-8")
print("Applied UI 4.1.3 patch: connection progress + calibration + last-label reserve + keepalive/reconnect")
