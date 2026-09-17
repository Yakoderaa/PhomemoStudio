from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class PrinterSnapshot:
    connected: bool = False
    name: str = "D30"
    address: str = ""
    battery: int | None = None
    paper: str | None = None
    message: str = "Bluetooth nativo sin iniciar"


def bridge_path() -> Path:
    env = os.environ.get("PHOMEMO_BLE_BRIDGE")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().with_name("PhomemoBleBridge.exe")
    return Path(__file__).resolve().parents[2] / "native_bridge" / "PhomemoBleBridge.exe"


class D30Printer:
    def __init__(self, status_cb: Callable[[PrinterSnapshot], None] | None = None):
        self.snapshot = PrinterSnapshot()
        self.status_cb = status_cb
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="D30Native")
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._last_address: str | None = None

    def _emit(self, msg: str | None = None):
        if msg:
            self.snapshot.message = msg
        if self.status_cb:
            try:
                self.status_cb(self.snapshot)
            except Exception:
                pass

    def _start_bridge(self):
        if self._proc and self._proc.poll() is None:
            return
        path = bridge_path()
        if not path.exists():
            raise RuntimeError(f"Falta el backend Bluetooth nativo: {path}")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._proc = subprocess.Popen(
            [str(path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=flags,
        )

    def _request(self, payload: dict) -> dict:
        with self._lock:
            self._start_bridge()
            assert self._proc and self._proc.stdin and self._proc.stdout
            self._proc.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
            if not line:
                detail = ""
                if self._proc.stderr:
                    try:
                        detail = self._proc.stderr.read(800)
                    except Exception:
                        pass
                raise RuntimeError("El backend Bluetooth nativo se cerró inesperadamente." + (f" {detail}" if detail else ""))
            data = json.loads(line)
            self.snapshot.connected = bool(data.get("connected", False))
            self.snapshot.name = data.get("name") or "D30"
            self.snapshot.address = data.get("address") or ""
            self.snapshot.message = data.get("message") or self.snapshot.message
            if self.snapshot.address:
                self._last_address = self.snapshot.address
            self._emit()
            if not data.get("ok", False):
                raise RuntimeError(self.snapshot.message)
            return data

    def connect(self, preferred_address: str | None = None, timeout: float = 18) -> concurrent.futures.Future:
        self._emit("Buscando D30 con Bluetooth nativo de Windows…")
        addr = preferred_address or self._last_address
        return self._executor.submit(self._request, {"command": "connect", "preferredAddress": addr})

    def disconnect(self):
        return self._executor.submit(self._disconnect_sync)

    def _disconnect_sync(self):
        try:
            return self._request({"command": "disconnect"})
        except Exception:
            self.snapshot.connected = False
            self._emit("D30 desconectada")
            return True

    def send_packets(self, packets: list[bytes], progress_cb: Callable[[int, int], None] | None = None):
        return self._executor.submit(self._send_packets_sync, packets, progress_cb)

    def _send_packets_sync(self, packets, progress_cb):
        if not self.snapshot.connected:
            self._request({"command": "connect", "preferredAddress": self._last_address})
        total = sum(len(p) for p in packets)
        encoded = []
        done = 0
        for packet in packets:
            encoded.append(base64.b64encode(packet).decode("ascii"))
            done += len(packet)
            if progress_cb:
                progress_cb(min(done, total), total)
        result = self._request({"command": "send", "packets": encoded})
        if progress_cb:
            progress_cb(total, total)
        self._emit(result.get("message") or "Impresión enviada a la D30")
        return True

    def calibrate(self, blank_raster: bytes, width_px: int, height_px: int):
        from .core import make_print_packet
        return self.send_packets(make_print_packet(blank_raster, width_px, height_px, density=1))

    def close(self):
        try:
            if self._proc and self._proc.poll() is None:
                try:
                    self._request({"command": "quit"})
                except Exception:
                    pass
                try:
                    self._proc.wait(timeout=2)
                except Exception:
                    self._proc.kill()
        finally:
            self._executor.shutdown(wait=False, cancel_futures=True)
