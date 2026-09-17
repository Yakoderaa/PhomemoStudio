from __future__ import annotations

import asyncio

from bleak import BleakClient

from phomemo_studio import printer as p


def _format_bt_address(value: int) -> str:
    return ":".join(f"{(value >> shift) & 0xFF:02X}" for shift in (40, 32, 24, 16, 8, 0))


async def _windows_known_ble(self):
    """Fallback to native Windows device enumeration when advertisements are empty."""
    try:
        from winrt.windows.devices.bluetooth import BluetoothLEDevice
        from winrt.windows.devices.enumeration import DeviceInformation
    except Exception as exc:
        self._emit(f"Fallback nativo de Windows no disponible: {exc}")
        return []

    try:
        selector = BluetoothLEDevice.get_device_selector()
        finder = getattr(DeviceInformation, "find_all_async_aqs_filter", None)
        if finder is not None:
            infos = await finder(selector)
        else:
            infos = await DeviceInformation.find_all_async(selector)
    except Exception as exc:
        self._emit(f"Windows no pudo enumerar dispositivos BLE conocidos: {exc}")
        return []

    result = []
    used = set()
    for info in infos:
        ble = None
        try:
            ble = await BluetoothLEDevice.from_id_async(info.id)
            if ble is None:
                continue
            raw = int(getattr(ble, "bluetooth_address", 0) or 0)
            if not raw:
                continue
            address = _format_bt_address(raw)
            if address in used:
                continue
            used.add(address)
            name = str(getattr(info, "name", "") or getattr(ble, "name", "") or "")
            item = p._Seen(None, name, set(), -100)
            item._native_address = address
            result.append(item)
        except Exception:
            continue
        finally:
            if ble is not None:
                try:
                    ble.close()
                except Exception:
                    pass
    return result


def _address(item):
    return str(getattr(item, "_native_address", "") or getattr(item.device, "address", "") or "")


async def _scan402(self, timeout: float):
    devices = await _ORIG_SCAN(self, timeout)
    if devices:
        return devices
    self._emit("El escaneo por anuncios no devolvió nada · consultando el inventario Bluetooth de Windows…")
    return await _windows_known_ble(self)


async def _try_device402(self, item, attempts: int, allow_generic: bool):
    last_error = None
    for attempt in range(attempts):
        client = None
        try:
            address = _address(item)
            target = item.device if item.device is not None else address
            self._emit(f"Conectando a {item.name or address or 'dispositivo BLE'}…")
            client = BleakClient(target, disconnected_callback=self._on_disconnect, timeout=12)
            await client.connect()
            await asyncio.sleep(0.8 + 0.2 * attempt)
            write_uuid, notify_uuid, identity_ok = self._characteristics(client)
            native_candidate = item.device is None and bool(address)
            if not identity_ok and not (allow_generic and item.looks_like_d30):
                raise RuntimeError("el dispositivo no expone el perfil GATT de una D30")
            if not write_uuid:
                raise RuntimeError("no encontré característica BLE de escritura")
            self._client = client
            self._write_uuid = write_uuid
            self._notify_uuid = notify_uuid
            self._last_address = address
            self.snapshot.connected = True
            self.snapshot.name = item.name or "D30"
            self.snapshot.address = address
            self._emit("D30 conectada · enlace estable")
            return True
        except Exception as exc:
            last_error = exc
            if client is not None:
                try:
                    if client.is_connected:
                        await client.disconnect()
                except Exception:
                    pass
            await asyncio.sleep(0.3 * (attempt + 1))
    raise RuntimeError(str(last_error) if last_error else "falló la conexión")


async def _connect402(self, preferred_address: str | None, timeout: float):
    if self._client and self._client.is_connected:
        return True
    self._emit("Buscando D30…")
    devices = await self._scan(timeout)
    if not devices:
        raise RuntimeError(
            "Windows no devolvió anuncios BLE ni dispositivos Bluetooth LE conocidos. "
            "Esto apunta al adaptador o al servicio Bluetooth de Windows, no a que la D30 esté conectada a otro equipo. "
            "Abrí Configuración > Bluetooth y dispositivos; si Windows ve la D30, dejá esa pantalla abierta y reintentá."
        )
    ranked = sorted(devices, key=lambda x: self._candidate_score(x, preferred_address), reverse=True)
    known = [x for x in ranked if x.looks_like_d30 or (preferred_address and _address(x).lower() == preferred_address.lower())]
    last_error = None
    for item in known[:8]:
        try:
            return await self._try_device(item, attempts=3, allow_generic=True)
        except Exception as exc:
            last_error = exc
    fallback = [x for x in ranked if x not in known]
    if fallback:
        self._emit(f"Verificando el perfil GATT de {min(len(fallback), 20)} dispositivos Bluetooth conocidos…")
    for item in fallback[:20]:
        try:
            return await self._try_device(item, attempts=1, allow_generic=False)
        except Exception as exc:
            last_error = exc
    names = [x.name for x in ranked if x.name][:8]
    detail = f" Dispositivos vistos: {', '.join(names)}." if names else f" Windows devolvió {len(ranked)} dispositivos sin nombre."
    raise RuntimeError("No pude identificar el perfil GATT de la D30." + detail + (f" Último detalle: {last_error}" if last_error else ""))


_ORIG_SCAN = p.D30Printer._scan
p.D30Printer._scan = _scan402
p.D30Printer._try_device = _try_device402
p.D30Printer._connect = _connect402
