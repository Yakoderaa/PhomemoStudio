from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import queue
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

    def _stop_bridge(self):
        proc = self._proc
        self._proc = None
        if not proc:
            return
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except Exception:
            pass

    @staticmethod
    def _readline_with_timeout(stream, timeout: float) -> str:
        q: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

        def reader():
            try:
                q.put((True, stream.readline()))
            except Exception as exc:
                q.put((False, exc))

        threading.Thread(target=reader, daemon=True, name="D30BridgeRead").start()
        try:
            ok, value = q.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(f"El backend Bluetooth no respondió después de {int(timeout)} segundos.")
        if not ok:
            raise value  # type: ignore[misc]
        return str(value)

    def _request(self, payload: dict, timeout: float = 22.0) -> dict:
        with self._lock:
            self._start_bridge()
            assert self._proc and self._proc.stdin and self._proc.stdout
            try:
                self._proc.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
                self._proc.stdin.flush()
                line = self._readline_with_timeout(self._proc.stdout, timeout)
            except TimeoutError:
                self._stop_bridge()
                self.snapshot.connected = False
                self._emit("La conexión Bluetooth tardó demasiado y fue reiniciada.")
                raise RuntimeError(
                    "La D30 quedó esperando una operación Bluetooth de Windows durante demasiado tiempo. "
                    "El backend se reinició automáticamente; volvé a pulsar Conectar D30."
                )
            except Exception:
                self._stop_bridge()
                raise

            if not line:
                detail = ""
                if self._proc and self._proc.stderr:
                    try:
                        detail = self._proc.stderr.read(800)
                    except Exception:
                        pass
                self._stop_bridge()
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

    def connect(self, preferred_address: str | None = None, timeout: float = 24) -> concurrent.futures.Future:
        self._emit("Buscando D30 con Bluetooth nativo de Windows…")
        addr = preferred_address or self._last_address
        return self._executor.submit(self._request, {"command": "connect", "preferredAddress": addr}, timeout)

    def disconnect(self):
        return self._executor.submit(self._disconnect_sync)

    def _disconnect_sync(self):
        try:
            return self._request({"command": "disconnect"}, 5)
        except Exception:
            self.snapshot.connected = False
            self._emit("D30 desconectada")
            return True

    def send_packets(self, packets: list[bytes], progress_cb: Callable[[int, int], None] | None = None):
        return self._executor.submit(self._send_packets_sync, packets, progress_cb)

    def _send_packets_sync(self, packets, progress_cb):
        if not self.snapshot.connected:
            self._request({"command": "connect", "preferredAddress": self._last_address}, 24)
        total = sum(len(p) for p in packets)
        encoded = []
        done = 0
        for packet in packets:
            encoded.append(base64.b64encode(packet).decode("ascii"))
            done += len(packet)
            if progress_cb:
                progress_cb(min(done, total), total)
        result = self._request({"command": "send", "packets": encoded}, max(30, min(180, 30 + total / 4000)))
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
                    self._request({"command": "quit"}, 3)
                except Exception:
                    self._stop_bridge()
                else:
                    try:
                        self._proc.wait(timeout=2)
                    except Exception:
                        self._stop_bridge()
        finally:
            self._executor.shutdown(wait=False, cancel_futures=True)
