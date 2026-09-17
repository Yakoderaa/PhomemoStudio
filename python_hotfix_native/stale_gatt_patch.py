from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"4.1.5 patch {label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


# Native bridge: WinRT can report a session as active even though one of its GATT wrappers
# has already been disposed by Windows. Never trust cached ConnectionStatus/SessionStatus
# alone: every maintenance pass probes the actual write characteristic with a harmless packet.
bridge_path = Path("native_bridge/PhomemoBleBridge/Program.cs")
bridge = bridge_path.read_text(encoding="utf-8")

bridge = replace_once(
    bridge,
    '''    private bool IsConnected => _write is not null &&
        (_device?.ConnectionStatus == BluetoothConnectionStatus.Connected || _session?.SessionStatus == GattSessionStatus.Active);
''',
    '''    private bool IsConnected
    {
        get
        {
            if (_write is null) return false;
            try
            {
                if (_device is not null && _device.ConnectionStatus == BluetoothConnectionStatus.Connected)
                    return true;
            }
            catch (ObjectDisposedException) { return false; }
            catch { }

            try
            {
                if (_session is not null && _session.SessionStatus == GattSessionStatus.Active)
                    return true;
            }
            catch (ObjectDisposedException) { return false; }
            catch { }

            return false;
        }
    }
''',
    "safe IsConnected",
)

bridge = replace_once(
    bridge,
    '''    public async Task<BridgeResponse> MaintainAsync(string? preferredAddress)
    {
        if (!IsConnected)
        {
            var reconnect = await ConnectAsync(preferredAddress);
            if (!reconnect.Ok || !reconnect.Connected)
                return reconnect;
            return Status("D30 reconectada automáticamente");
        }

        // La D30 suele entrar en reposo tras varios minutos sin tráfico. Cada dos minutos,
        // una consulta de batería muy corta mantiene viva la sesión sin imprimir ni avanzar papel.
        if (DateTimeOffset.UtcNow - _lastTrafficUtc >= TimeSpan.FromMinutes(2))
        {
            try
            {
                await WritePayloadAsync(KeepAlivePacket);
                return Status("D30 conectada · enlace activo");
            }
            catch
            {
                var remembered = _lastAddress;
                Cleanup();
                if (remembered is ulong address)
                {
                    try
                    {
                        await ConnectToAddressAsync(address, "D30");
                        return Status("D30 reconectada automáticamente");
                    }
                    catch
                    {
                        Cleanup();
                    }
                }
                return BridgeResponse.Fail("La D30 perdió el enlace y Windows todavía no permitió reconectarla.");
            }
        }

        return Status("D30 conectada");
    }
''',
    '''    public async Task<BridgeResponse> MaintainAsync(string? preferredAddress)
    {
        // Windows/WinRT puede conservar ConnectionStatus/SessionStatus aunque la característica
        // GATT ya haya sido descartada. Por eso cada comprobación valida el canal real de escritura.
        if (!IsConnected || _write is null)
        {
            Cleanup();
            var reconnect = await ConnectAsync(preferredAddress);
            if (!reconnect.Ok || !reconnect.Connected)
                return reconnect;
        }

        try
        {
            // Paquete inocuo: no imprime ni avanza papel. Sirve como preflight real del canal GATT.
            await WritePayloadAsync(KeepAlivePacket);
            return Status("D30 conectada · canal verificado");
        }
        catch
        {
            var remembered = _lastAddress;
            Cleanup();
            if (remembered is ulong address)
            {
                try
                {
                    await ConnectToAddressAsync(address, "D30");
                    await WritePayloadAsync(KeepAlivePacket);
                    return Status("D30 reconectada automáticamente · canal renovado");
                }
                catch
                {
                    Cleanup();
                }
            }
            return BridgeResponse.Fail("La D30 perdió el canal Bluetooth de escritura y Windows todavía no permitió renovarlo.");
        }
    }
''',
    "active GATT maintenance probe",
)

bridge = replace_once(
    bridge,
    '''    public async Task<BridgeResponse> SendAsync(string[] packets)
    {
        if (!IsConnected || _write is null)
            return BridgeResponse.Fail("La D30 no está conectada al backend Bluetooth nativo.");

        try
        {
            foreach (var encoded in packets)
            {
                var bytes = Convert.FromBase64String(encoded);
                await WritePayloadAsync(bytes);
            }
            return Status("Impresión enviada a la D30");
        }
        catch (Exception ex)
        {
            return BridgeResponse.Fail(ex.GetBaseException().Message);
        }
    }
''',
    '''    public async Task<BridgeResponse> SendAsync(string[] packets)
    {
        // Validar el canal justo antes de imprimir evita usar una característica GATT que Windows
        // haya descartado entre la reconexión automática y el siguiente trabajo.
        var preflight = await MaintainAsync(_lastAddress?.ToString("X12", CultureInfo.InvariantCulture));
        if (!preflight.Ok || !preflight.Connected || _write is null)
            return BridgeResponse.Fail(preflight.Message);

        try
        {
            foreach (var encoded in packets)
            {
                var bytes = Convert.FromBase64String(encoded);
                await WritePayloadAsync(bytes);
            }
            return Status("Impresión enviada a la D30");
        }
        catch (Exception ex)
        {
            // Si el enlace cae durante el envío, limpiar todo para que el próximo intento nazca
            // con BluetoothLEDevice/Session/Characteristic nuevos. No se reenvía automáticamente
            // el trabajo para evitar una impresión duplicada si Windows alcanzó a transmitir bytes.
            var detail = ex.GetBaseException().Message;
            Cleanup();
            return BridgeResponse.Fail($"El enlace Bluetooth cambió durante la impresión y fue reiniciado. Volvé a imprimir. Detalle: {detail}");
        }
    }
''',
    "send preflight",
)

bridge = replace_once(
    bridge,
    '''    private void Cleanup()
    {
        try
        {
            if (_session is not null)
            {
                try { _session.MaintainConnection = false; } catch { }
                _session.Dispose();
            }
            _service?.Dispose();
            _device?.Dispose();
        }
        catch { }
        _device = null;
        _service = null;
        _session = null;
        _write = null;
        _address = null;
    }
''',
    '''    private void Cleanup()
    {
        if (_session is not null)
        {
            try { _session.MaintainConnection = false; } catch { }
            try { _session.Dispose(); } catch { }
        }
        try { _service?.Dispose(); } catch { }
        try { _device?.Dispose(); } catch { }
        _device = null;
        _service = null;
        _session = null;
        _write = null;
        _address = null;
    }
''',
    "independent cleanup",
)

bridge_path.write_text(bridge, encoding="utf-8")


# Python wrapper: validate/rebuild the native helper before every real print/calibration job,
# not only on the 30-second background timer. This closes the race where the D30 reconnects
# and the user prints before the next maintenance tick.
printer_path = Path("python_hotfix_native/printer.py")
printer = printer_path.read_text(encoding="utf-8")
printer = replace_once(
    printer,
    '''    def _send_packets_sync(self, packets, progress_cb, post_delay: float = 0.0):
        if not self.snapshot.connected:
            self._request({"command": "connect", "preferredAddress": self._last_address}, 20)
        total = sum(len(p) for p in packets)
''',
    '''    def _send_packets_sync(self, packets, progress_cb, post_delay: float = 0.0):
        addr = self._last_address or self.snapshot.address or None
        try:
            self._maintain_connection_sync(addr, 18)
        except Exception:
            # Last-resort rebuild before a real job. No print bytes have been sent yet.
            self._stop_bridge()
            self.snapshot.connected = False
            self._emit("Renovando enlace Bluetooth antes de imprimir…")
            self._request({"command": "connect", "preferredAddress": addr}, 20)
        total = sum(len(p) for p in packets)
''',
    "python preflight before send",
)

printer = replace_once(
    printer,
    '''        result = self._request({"command": "send", "packets": encoded}, max(30, min(180, 30 + total / 4000)))
        if post_delay:
''',
    '''        try:
            result = self._request({"command": "send", "packets": encoded}, max(30, min(180, 30 + total / 4000)))
        except Exception as exc:
            text = str(exc).lower()
            if "disposed" in text or "descart" in text or "canal bluetooth cambió" in text:
                self._stop_bridge()
                self.snapshot.connected = False
                self._emit("El enlace Bluetooth se renovará en el próximo intento")
                raise RuntimeError("Windows cambió el enlace Bluetooth justo al imprimir. Ya lo limpié; volvé a pulsar Imprimir.") from exc
            raise
        if post_delay:
''',
    "friendly stale-link recovery",
)
printer_path.write_text(printer, encoding="utf-8")

print("Applied Phomemo Studio 4.1.5 stale-GATT fix")
