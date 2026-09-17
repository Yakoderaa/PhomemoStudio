from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from dataclasses import dataclass
from typing import Callable

from bleak import BleakClient, BleakScanner

SERVICE_UUIDS = {
    "0000ff00-0000-1000-8000-00805f9b34fb",
    "0000ae30-0000-1000-8000-00805f9b34fb",
    "0000af30-0000-1000-8000-00805f9b34fb",
    "0000ffe0-0000-1000-8000-00805f9b34fb",
    "49535343-fe7d-4ae5-8fa9-9fafd205e455",
}
WRITE_HINTS = ("ff02", "ae01", "af01", "ffe1")
NOTIFY_HINTS = ("ff03", "ae02", "af02")

@dataclass
class PrinterSnapshot:
    connected: bool = False
    name: str = "D30"
    address: str = ""
    battery: int | None = None
    paper: str | None = None
    message: str = "Bluetooth sin iniciar"

@dataclass
class _Seen:
    device: object
    name: str = ""
    service_uuids: set[str] | None = None
    rssi: int = -127

    def __post_init__(self):
        if self.service_uuids is None:
            self.service_uuids = set()

    @property
    def address(self) -> str:
        return str(getattr(self.device, "address", "") or "")

    @property
    def looks_like_d30(self) -> bool:
        n = self.name.upper()
        return "D30" in n or "PHOMEMO" in n or bool(self.service_uuids & SERVICE_UUIDS)

class AsyncLoopThread:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True, name="D30BLE")
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

class D30Printer:
    def __init__(self, status_cb: Callable[[PrinterSnapshot], None] | None = None):
        self._loop = AsyncLoopThread()
        self._client: BleakClient | None = None
        self._write_uuid: str | None = None
        self._notify_uuid: str | None = None
        self.snapshot = PrinterSnapshot()
        self.status_cb = status_cb
        self._last_address: str | None = None

    def _emit(self, msg: str | None = None):
        if msg:
            self.snapshot.message = msg
        if self.status_cb:
            try:
                self.status_cb(self.snapshot)
            except Exception:
                pass

    def connect(self, preferred_address: str | None = None, timeout: float = 18) -> concurrent.futures.Future:
        return self._loop.submit(self._connect(preferred_address, timeout))

    @staticmethod
    def _candidate_score(item: _Seen, preferred_address: str | None) -> int:
        score = item.rssi
        if preferred_address and item.address.lower() == preferred_address.lower():
            score += 2000
        n = item.name.upper()
        if "D30" in n:
            score += 900
        if "PHOMEMO" in n:
            score += 700
        if item.service_uuids & SERVICE_UUIDS:
            score += 800
        return score

    async def _scan(self, timeout: float) -> list[_Seen]:
        seen: dict[str, _Seen] = {}

        def on_adv(dev, adv):
            address = str(getattr(dev, "address", "") or "")
            if not address:
                return
            current = seen.get(address)
            local_name = str(getattr(adv, "local_name", "") or "")
            dev_name = str(getattr(dev, "name", "") or "")
            name = local_name or dev_name
            uuids = {str(u).lower() for u in (getattr(adv, "service_uuids", None) or [])}
            rssi = int(getattr(adv, "rssi", -127) or -127)
            if current is None:
                seen[address] = _Seen(dev, name, uuids, rssi)
            else:
                current.device = dev
                if name:
                    current.name = name
                current.service_uuids.update(uuids)
                current.rssi = max(current.rssi, rssi)

        scanner = BleakScanner(detection_callback=on_adv, scanning_mode="active")
        await scanner.start()
        try:
            await asyncio.sleep(max(4.0, min(timeout, 15.0)))
        finally:
            await scanner.stop()
        return list(seen.values())

    @staticmethod
    def _characteristics(client) -> tuple[str | None, str | None, bool]:
        write_hint = None
        write_generic = None
        notify_uuid = None
        has_known_service = False
        for service in client.services:
            su = str(getattr(service, "uuid", "")).lower()
            if su in SERVICE_UUIDS:
                has_known_service = True
            for ch in service.characteristics:
                u = ch.uuid.lower()
                props = {p.lower() for p in ch.properties}
                writable = bool({"write", "write-without-response"} & props)
                if writable and write_generic is None:
                    write_generic = ch.uuid
                if writable and write_hint is None and any(h in u for h in WRITE_HINTS):
                    write_hint = ch.uuid
                if notify_uuid is None and any(h in u for h in NOTIFY_HINTS) and ({"notify", "indicate"} & props):
                    notify_uuid = ch.uuid
        return write_hint or write_generic, notify_uuid, has_known_service or write_hint is not None

    async def _try_device(self, item: _Seen, attempts: int, allow_generic: bool):
        last_error = None
        for attempt in range(attempts):
            client = None
            try:
                self._emit(f"Conectando a {item.name or 'dispositivo BLE'}…")
                client = BleakClient(item.device, disconnected_callback=self._on_disconnect, timeout=10)
                await client.connect()
                await asyncio.sleep(0.65 + 0.2 * attempt)
                write_uuid, notify_uuid, identity_ok = self._characteristics(client)
                if not identity_ok and not (allow_generic and item.looks_like_d30):
                    raise RuntimeError("el dispositivo no expone el perfil GATT de una D30")
                if not write_uuid:
                    raise RuntimeError("no encontré característica BLE de escritura")

                self._client = client
                self._write_uuid = write_uuid
                self._notify_uuid = notify_uuid
                self._last_address = item.address
                self.snapshot.connected = True
                self.snapshot.name = item.name or "D30"
                self.snapshot.address = item.address
                self._emit("D30 conectada · enlace estable")
                return True
            except Exception as e:
                last_error = e
                if client is not None:
                    try:
                        if client.is_connected:
                            await client.disconnect()
                    except Exception:
                        pass
                await asyncio.sleep(0.25 * (attempt + 1))
        raise RuntimeError(str(last_error) if last_error else "falló la conexión")

    async def _connect(self, preferred_address: str | None, timeout: float):
        if self._client and self._client.is_connected:
            return True

        self._emit("Buscando D30…")
        devices = await self._scan(timeout)
        if not devices:
            raise RuntimeError(
                "Windows no devolvió ningún dispositivo Bluetooth LE durante el escaneo. "
                "Verificá que Bluetooth esté activado y que la D30 no esté conectada a otro teléfono o PC."
            )

        ranked = sorted(devices, key=lambda x: self._candidate_score(x, preferred_address), reverse=True)
        known = [x for x in ranked if x.looks_like_d30 or (preferred_address and x.address.lower() == preferred_address.lower())]
        last_error = None

        for item in known[:6]:
            try:
                return await self._try_device(item, attempts=3, allow_generic=True)
            except Exception as e:
                last_error = e

        fallback = [x for x in ranked if x not in known]
        if fallback:
            self._emit(f"D30 sin nombre visible · verificando {min(len(fallback), 10)} dispositivos cercanos…")
        for item in fallback[:10]:
            try:
                return await self._try_device(item, attempts=1, allow_generic=False)
            except Exception as e:
                last_error = e

        visible_names = [x.name for x in ranked if x.name][:6]
        extra = f" Dispositivos vistos: {', '.join(visible_names)}." if visible_names else f" Vi {len(ranked)} dispositivos BLE sin nombre útil."
        raise RuntimeError(
            "La D30 está encendida, pero Windows no la expuso como D30/Phomemo ni con su perfil GATT. "
            "Cerrá Print Master y desconectala de cualquier teléfono antes de reintentar." + extra +
            (f" Último detalle: {last_error}" if last_error else "")
        )

    def _on_disconnect(self, _client):
        self.snapshot.connected = False
        self._emit("D30 desconectada")

    def disconnect(self):
        return self._loop.submit(self._disconnect())

    async def _disconnect(self):
        if self._client:
            try:
                await self._client.disconnect()
            finally:
                self._client = None
                self._write_uuid = None
        self.snapshot.connected = False
        self._emit("D30 desconectada")

    async def _ensure(self):
        if self._client and self._client.is_connected and self._write_uuid:
            return
        await self._connect(self._last_address, 18)

    def send_packets(self, packets: list[bytes], progress_cb: Callable[[int, int], None] | None = None):
        return self._loop.submit(self._send_packets(packets, progress_cb))

    async def _send_packets(self, packets, progress_cb):
        await self._ensure()
        assert self._client and self._write_uuid
        total = sum(len(p) for p in packets)
        done = 0
        for packet in packets:
            for i in range(0, len(packet), 128):
                chunk = packet[i:i + 128]
                await self._client.write_gatt_char(self._write_uuid, chunk, response=False)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
                await asyncio.sleep(0.018)
        self._emit("Impresión enviada a la D30")
        return True

    def calibrate(self, blank_raster: bytes, width_px: int, height_px: int):
        from .core import make_print_packet
        return self.send_packets(make_print_packet(blank_raster, width_px, height_px, density=1))

    def close(self):
        try:
            fut = self.disconnect()
            fut.result(timeout=3)
        except Exception:
            pass
        self._loop.stop()
