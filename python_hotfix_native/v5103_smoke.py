import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v5103-")

from PySide6.QtWidgets import QApplication, QFrame, QPushButton

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.printer import D30Printer, PrinterSnapshot

w = MainWindow()
status = w.findChild(QFrame, "v5103PrinterStatus")
assert status is not None
assert getattr(w, "connect_btn").parentWidget() is status
assert getattr(w, "battery").parentWidget() is status
assert getattr(w, "paper").parentWidget() is status
assert getattr(w, "roll_status").parentWidget() is status

# Hiding Properties must never hide printer connection / consumable status.
inspector = getattr(w, "_v51_inspector")
inspector.hide()
assert inspector.isHidden()
assert not status.isHidden()

# The moved original widgets still receive live backend status updates.
w.on_printer_status(PrinterSnapshot(
    connected=True,
    name="D30",
    battery=87,
    paper="OK",
    message="D30 conectada",
))
assert "Desconectar" in w.connect_btn.text()
assert "87" in w.battery.text()
assert "OK" in w.paper.text()
w.roll_total.setValue(100)
w.roll_remaining.setValue(42)
w.update_roll_ui()
assert "42" in w.roll_status.text()

# Progress must only reach 100% after the native send request returns.
p = D30Printer()
p.snapshot.connected = True
events = []

def fake_request(payload, timeout=20.0):
    events.append(("request", payload.get("command")))
    return {"ok": True, "connected": True, "message": "enviado"}

p._request = fake_request
packets = [b"abc", b"defgh"]
total = sum(len(x) for x in packets)
p._send_packets_sync(
    packets,
    lambda done, amount: events.append(("progress", done, amount)),
)
assert events[0] == ("progress", 0, total), events
assert events[1] == ("request", "send"), events
assert events[2] == ("progress", total, total), events
p.close()

w.close()
print("V5.10.3 persistent printer header + truthful print progress smoke OK")
