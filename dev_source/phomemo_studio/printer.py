from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import time
from dataclasses import dataclass
from typing import Callable

from bleak import BleakClient, BleakScanner

SERVICE_UUIDS = [
    "0000ff00-0000-1000-8000-00805f9b34fb",
    "0000ae30-0000-1000-8000-00805f9b34fb",
    "0000af30-0000-1000-8000-00805f9b34fb",
    "0000ffe0-0000-1000-8000-00805f9b34fb",
    "49535343-fe7d-4ae5-8fa9-9fafd205e455",
]
WRITE_HINTS = ["ff02","ae01","af01","ffe1"]
NOTIFY_HINTS = ["ff03","ae02","af02"]

@dataclass
class PrinterSnapshot:
    connected: bool = False
    name: str = "D30"
    address: str = ""
    battery: int | None = None
    paper: str | None = None
    message: str = "Bluetooth sin iniciar"

class AsyncLoopThread:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True, name="D30BLE")
        self.thread.start()
    def _run(self):
        asyncio.set_event_loop(self.loop); self.loop.run_forever()
    def submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)
    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

class D30Printer:
    def __init__(self, status_cb: Callable[[PrinterSnapshot],None] | None = None):
        self._loop = AsyncLoopThread(); self._client: BleakClient | None = None
        self._write_uuid: str | None = None; self._notify_uuid: str | None = None
        self.snapshot = PrinterSnapshot(); self.status_cb = status_cb
        self._lock = threading.Lock(); self._last_address: str | None = None

    def _emit(self, msg: str | None = None):
        if msg: self.snapshot.message = msg
        if self.status_cb:
            try: self.status_cb(self.snapshot)
            except Exception: pass

    def connect(self, preferred_address: str | None = None, timeout: float = 15) -> concurrent.futures.Future:
        return self._loop.submit(self._connect(preferred_address, timeout))

    async def _connect(self, preferred_address: str | None, timeout: float):
        if self._client and self._client.is_connected:
            return True
        self._emit("Buscando D30…")
        devices = await BleakScanner.discover(timeout=min(timeout, 12.0), return_adv=True)
        candidates = []
        for addr,(dev,adv) in devices.items():
            name = (dev.name or adv.local_name or "").upper()
            uuids = {u.lower() for u in (adv.service_uuids or [])}
            if "D30" in name or "PHOMEMO" in name or uuids.intersection(SERVICE_UUIDS):
                score = 100 if preferred_address and addr.lower()==preferred_address.lower() else 0
                score += int(getattr(adv,"rssi",-100) or -100)
                candidates.append((score,dev))
        if not candidates:
            raise RuntimeError("No encontré una Phomemo D30 encendida cerca.")
        candidates.sort(key=lambda x:x[0], reverse=True)
        last_error = None
        for _, dev in candidates[:4]:
            for attempt in range(3):
                try:
                    self._emit(f"Conectando a {dev.name or 'D30'}…")
                    client = BleakClient(dev, disconnected_callback=self._on_disconnect, timeout=12)
                    await client.connect()
                    await asyncio.sleep(0.75)
                    services = client.services
                    write_uuid = None; notify_uuid = None
                    for service in services:
                        for ch in service.characteristics:
                            u = ch.uuid.lower()
                            props = {p.lower() for p in ch.properties}
                            if write_uuid is None and any(h in u for h in WRITE_HINTS) and ({"write","write-without-response"}&props):
                                write_uuid = ch.uuid
                            if notify_uuid is None and any(h in u for h in NOTIFY_HINTS) and ({"notify","indicate"}&props):
                                notify_uuid = ch.uuid
                    if write_uuid is None:
                        for service in services:
                            for ch in service.characteristics:
                                props={p.lower() for p in ch.properties}
                                if {"write","write-without-response"}&props:
                                    write_uuid=ch.uuid; break
                            if write_uuid: break
                    if not write_uuid:
                        await client.disconnect(); raise RuntimeError("No encontré característica BLE de escritura.")
                    self._client=client; self._write_uuid=write_uuid; self._notify_uuid=notify_uuid
                    self._last_address=str(dev.address)
                    self.snapshot.connected=True; self.snapshot.name=dev.name or "D30"; self.snapshot.address=str(dev.address)
                    self._emit("D30 conectada · enlace estable")
                    return True
                except Exception as e:
                    last_error=e; await asyncio.sleep(0.35*(attempt+1))
        raise RuntimeError(f"No pude conectar la D30: {last_error}")

    def _on_disconnect(self, _client):
        self.snapshot.connected=False; self._emit("D30 desconectada")

    def disconnect(self):
        return self._loop.submit(self._disconnect())
    async def _disconnect(self):
        if self._client:
            try: await self._client.disconnect()
            finally: self._client=None; self._write_uuid=None
        self.snapshot.connected=False; self._emit("D30 desconectada")

    async def _ensure(self):
        if self._client and self._client.is_connected and self._write_uuid: return
        await self._connect(self._last_address, 15)

    def send_packets(self, packets: list[bytes], progress_cb: Callable[[int,int],None] | None=None):
        return self._loop.submit(self._send_packets(packets, progress_cb))
    async def _send_packets(self, packets, progress_cb):
        await self._ensure(); assert self._client and self._write_uuid
        total=sum(len(p) for p in packets); done=0
        for packet in packets:
            for i in range(0,len(packet),128):
                chunk=packet[i:i+128]
                await self._client.write_gatt_char(self._write_uuid, chunk, response=False)
                done += len(chunk)
                if progress_cb: progress_cb(done,total)
                await asyncio.sleep(0.018)
        self._emit("Impresión enviada a la D30")
        return True

    def calibrate(self, blank_raster: bytes, width_px: int, height_px: int):
        from .core import make_print_packet
        return self.send_packets(make_print_packet(blank_raster,width_px,height_px,density=1))

    def close(self):
        try:
            fut=self.disconnect(); fut.result(timeout=3)
        except Exception: pass
        self._loop.stop()
