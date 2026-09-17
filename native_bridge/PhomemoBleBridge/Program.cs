using System.Globalization;
using System.Text.Json;
using Windows.Devices.Bluetooth;
using Windows.Devices.Bluetooth.Advertisement;
using Windows.Devices.Bluetooth.GenericAttributeProfile;
using Windows.Devices.Enumeration;
using Windows.Foundation;
using Windows.Storage.Streams;

namespace PhomemoBleBridge;

internal static class Program
{
    private static readonly object OutputGate = new();

    public static async Task Main()
    {
        Console.OutputEncoding = System.Text.Encoding.UTF8;

        void Emit(BridgeResponse response)
        {
            lock (OutputGate)
            {
                Console.WriteLine(JsonSerializer.Serialize(response, JsonOptions.Options));
                Console.Out.Flush();
            }
        }

        using var bridge = new D30Bridge(message => Emit(BridgeResponse.Progress(message)));
        string? line;
        while ((line = Console.ReadLine()) is not null)
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            BridgeResponse response;
            try
            {
                var req = JsonSerializer.Deserialize<BridgeRequest>(line, JsonOptions.Options)
                          ?? throw new InvalidOperationException("Solicitud vacía");
                response = req.Command?.ToLowerInvariant() switch
                {
                    "connect" => await bridge.ConnectAsync(req.PreferredAddress),
                    "maintain" => await bridge.MaintainAsync(req.PreferredAddress),
                    "disconnect" => bridge.Disconnect(),
                    "send" => await bridge.SendAsync(req.Packets ?? []),
                    "status" => bridge.Status(),
                    "quit" => bridge.Quit(),
                    _ => BridgeResponse.Fail($"Comando desconocido: {req.Command}")
                };
            }
            catch (Exception ex)
            {
                response = BridgeResponse.Fail(ex.GetBaseException().Message);
            }

            Emit(response);
            if (response.Quit) break;
        }
    }
}

internal static class JsonOptions
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };
}

internal sealed class BridgeRequest
{
    public string? Command { get; set; }
    public string? PreferredAddress { get; set; }
    public string[]? Packets { get; set; }
}

internal sealed class BridgeResponse
{
    public bool Ok { get; set; }
    public bool Connected { get; set; }
    public string Name { get; set; } = "D30";
    public string Address { get; set; } = "";
    public string Message { get; set; } = "";
    public string Event { get; set; } = "result";
    public bool Quit { get; set; }

    public static BridgeResponse Fail(string message) => new() { Ok = false, Message = message };
    public static BridgeResponse Progress(string message) => new() { Ok = true, Message = message, Event = "progress" };
}

internal sealed class D30Bridge : IDisposable
{
    private static readonly Guid[] ServiceUuids =
    {
        new("0000ff00-0000-1000-8000-00805f9b34fb"),
        new("0000ae30-0000-1000-8000-00805f9b34fb"),
        new("0000af30-0000-1000-8000-00805f9b34fb"),
        new("0000ffe0-0000-1000-8000-00805f9b34fb"),
        new("49535343-fe7d-4ae5-8fa9-9fafd205e455")
    };

    private static readonly byte[] KeepAlivePacket = { 0x1F, 0x11, 0x08 };
    private readonly Action<string> _progress;
    private BluetoothLEDevice? _device;
    private GattDeviceService? _service;
    private GattSession? _session;
    private GattCharacteristic? _write;
    private ulong? _address;
    private ulong? _lastAddress;
    private string _name = "D30";
    private DateTimeOffset _lastTrafficUtc = DateTimeOffset.MinValue;

    public D30Bridge(Action<string>? progress = null)
    {
        _progress = progress ?? (_ => { });
    }

    private bool IsConnected => _write is not null &&
        (_device?.ConnectionStatus == BluetoothConnectionStatus.Connected || _session?.SessionStatus == GattSessionStatus.Active);

    public async Task<BridgeResponse> ConnectAsync(string? preferredAddress)
    {
        if (IsConnected) return Status("D30 conectada");

        ulong saved;
        var hasSaved = TryParseAddress(preferredAddress, out saved);
        if (!hasSaved && _lastAddress is ulong remembered)
        {
            saved = remembered;
            hasSaved = true;
        }

        if (hasSaved)
        {
            _progress("Probando la D30 guardada…");
            try
            {
                await ConnectToAddressAsync(saved, "D30");
                return Status("D30 reconectada directamente con Windows");
            }
            catch
            {
                Cleanup();
            }
        }

        _progress("Buscando una D30 que Windows ya conozca…");
        var known = await FindKnownD30Async();
        if (known is not null)
        {
            try
            {
                _progress($"Encontré {known.Value.Name} en Windows · abriendo enlace…");
                await ConnectToIdAsync(known.Value.Id, known.Value.Name);
                return Status("D30 conectada desde el inventario Bluetooth de Windows");
            }
            catch
            {
                Cleanup();
            }
        }

        _progress("Escaneando anuncios Bluetooth LE de la D30…");
        var candidate = await ScanForD30Async(TimeSpan.FromSeconds(8));
        if (candidate is null)
            return BridgeResponse.Fail("Windows no encontró una D30 anunciándose. No hace falta tocar el aviso ‘Agregar un dispositivo’: dejá la D30 encendida y reintentá.");

        _progress($"D30 detectada ({candidate.Value.Name}) · conectando directamente, sin usar el aviso de Windows…");
        await ConnectToAddressAsync(candidate.Value.Address, candidate.Value.Name);
        return Status("D30 conectada con Bluetooth nativo de Windows");
    }

    public async Task<BridgeResponse> MaintainAsync(string? preferredAddress)
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

    private static bool TryParseAddress(string? raw, out ulong address)
    {
        address = 0;
        if (string.IsNullOrWhiteSpace(raw)) return false;
        var cleaned = new string(raw.Where(Uri.IsHexDigit).ToArray());
        return cleaned.Length <= 12 && ulong.TryParse(cleaned, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out address);
    }

    private async Task<(string Id, string Name)?> FindKnownD30Async()
    {
        try
        {
            var selector = BluetoothLEDevice.GetDeviceSelector();
            var devices = await DeviceInformation.FindAllAsync(selector).AsTask()
                .WaitAsync(TimeSpan.FromSeconds(4));
            foreach (var info in devices)
            {
                var name = info.Name?.Trim() ?? string.Empty;
                if (name.Contains("D30", StringComparison.OrdinalIgnoreCase) ||
                    name.Contains("PHOMEMO", StringComparison.OrdinalIgnoreCase))
                    return (info.Id, string.IsNullOrWhiteSpace(name) ? "D30" : name);
            }
        }
        catch
        {
            // Advertisement scanning remains the fallback.
        }
        return null;
    }

    private async Task<(ulong Address, string Name)?> ScanForD30Async(TimeSpan timeout)
    {
        var tcs = new TaskCompletionSource<(ulong, string)?>(TaskCreationOptions.RunContinuationsAsynchronously);
        using var cts = new CancellationTokenSource(timeout);
        var watcher = new BluetoothLEAdvertisementWatcher { ScanningMode = BluetoothLEScanningMode.Active };

        TypedEventHandler<BluetoothLEAdvertisementWatcher, BluetoothLEAdvertisementReceivedEventArgs>? handler = null;
        handler = (_, args) =>
        {
            try
            {
                var name = args.Advertisement.LocalName?.Trim() ?? string.Empty;
                var nameMatch = name.Contains("D30", StringComparison.OrdinalIgnoreCase) ||
                                name.Contains("PHOMEMO", StringComparison.OrdinalIgnoreCase);
                var serviceMatch = args.Advertisement.ServiceUuids.Any(u => ServiceUuids.Contains(u));
                if (!nameMatch && !serviceMatch) return;

                var displayName = string.IsNullOrWhiteSpace(name) ? "D30" : name;
                tcs.TrySetResult((args.BluetoothAddress, displayName));
            }
            catch { }
        };

        watcher.Received += handler;
        watcher.Start();
        try
        {
            using (cts.Token.Register(() => tcs.TrySetResult(null)))
                return await tcs.Task;
        }
        finally
        {
            try { watcher.Stop(); } catch { }
            watcher.Received -= handler;
        }
    }

    private async Task ConnectToIdAsync(string id, string hintedName)
    {
        Cleanup();
        _progress("Windows conoce la D30 · abriendo dispositivo BLE…");
        _device = await BluetoothLEDevice.FromIdAsync(id).AsTask()
                  .WaitAsync(TimeSpan.FromSeconds(5))
                  ?? throw new InvalidOperationException("Windows conoce la D30 pero no pudo abrir el dispositivo BLE.");
        await DiscoverGattAsync(_device.BluetoothAddress, hintedName);
    }

    private async Task ConnectToAddressAsync(ulong address, string hintedName)
    {
        Cleanup();
        _progress("Abriendo la D30 por su dirección Bluetooth…");
        _device = await BluetoothLEDevice.FromBluetoothAddressAsync(address).AsTask()
                  .WaitAsync(TimeSpan.FromSeconds(5))
                  ?? throw new InvalidOperationException("Windows detectó la D30 pero no pudo abrir el dispositivo BLE.");
        await DiscoverGattAsync(address, hintedName);
    }

    private async Task DiscoverGattAsync(ulong address, string hintedName)
    {
        if (_device is null) throw new InvalidOperationException("No hay dispositivo BLE abierto.");

        _progress("D30 abierta · leyendo servicios GATT…");
        var services = await _device.GetGattServicesAsync(BluetoothCacheMode.Uncached).AsTask()
            .WaitAsync(TimeSpan.FromSeconds(7));
        if (services.Status != GattCommunicationStatus.Success)
        {
            _progress($"Servicios GATT respondieron {services.Status} · probando caché de Windows…");
            services = await _device.GetGattServicesAsync(BluetoothCacheMode.Cached).AsTask()
                .WaitAsync(TimeSpan.FromSeconds(3));
        }
        if (services.Status != GattCommunicationStatus.Success)
            throw new InvalidOperationException($"Windows no pudo leer los servicios GATT de la D30 ({services.Status}).");

        _service = services.Services.FirstOrDefault(s => ServiceUuids.Contains(s.Uuid));
        if (_service is null)
        {
            foreach (var service in services.Services) service.Dispose();
            throw new InvalidOperationException("La D30 respondió, pero no expuso ninguno de sus servicios de impresión conocidos.");
        }
        foreach (var service in services.Services)
            if (!ReferenceEquals(service, _service)) service.Dispose();

        _progress($"Servicio D30 {_service.Uuid} · buscando canal de escritura…");
        _session = _service.Session;
        if (_session.CanMaintainConnection) _session.MaintainConnection = true;

        var charsResult = await _service.GetCharacteristicsAsync(BluetoothCacheMode.Uncached).AsTask()
            .WaitAsync(TimeSpan.FromSeconds(5));
        if (charsResult.Status != GattCommunicationStatus.Success)
            throw new InvalidOperationException($"No pude leer los canales GATT ({charsResult.Status}).");

        _write = charsResult.Characteristics.FirstOrDefault(c => IsWriteUuid(c.Uuid))
              ?? charsResult.Characteristics.FirstOrDefault(c => c.CharacteristicProperties.HasFlag(GattCharacteristicProperties.WriteWithoutResponse))
              ?? charsResult.Characteristics.FirstOrDefault(c => c.CharacteristicProperties.HasFlag(GattCharacteristicProperties.Write));

        if (_write is null) throw new InvalidOperationException("Encontré la D30 pero no su canal de escritura.");

        _address = address;
        _lastAddress = address;
        _name = string.IsNullOrWhiteSpace(_device.Name) ? hintedName : _device.Name;
        _lastTrafficUtc = DateTimeOffset.UtcNow;
        _progress($"Canal de impresión {_write.Uuid} listo · estabilizando enlace…");
        await Task.Delay(550);
    }

    private static bool IsWriteUuid(Guid uuid)
    {
        var s = uuid.ToString("D");
        return s.StartsWith("0000ff02", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000ae01", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000af01", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000ffe1", StringComparison.OrdinalIgnoreCase);
    }

    private async Task WritePayloadAsync(byte[] bytes)
    {
        if (_write is null) throw new InvalidOperationException("La D30 no tiene un canal de escritura activo.");

        for (var i = 0; i < bytes.Length; i += 128)
        {
            var chunk = bytes.AsSpan(i, Math.Min(128, bytes.Length - i)).ToArray();
            using var writer = new DataWriter();
            writer.WriteBytes(chunk);
            var buffer = writer.DetachBuffer();
            var option = _write.CharacteristicProperties.HasFlag(GattCharacteristicProperties.WriteWithoutResponse)
                ? GattWriteOption.WriteWithoutResponse
                : GattWriteOption.WriteWithResponse;
            var result = await _write.WriteValueWithResultAsync(buffer, option).AsTask()
                .WaitAsync(TimeSpan.FromSeconds(5));
            if (result.Status != GattCommunicationStatus.Success)
                throw new InvalidOperationException($"Windows no pudo enviar datos a la D30 ({result.Status}).");
            _lastTrafficUtc = DateTimeOffset.UtcNow;
            if (bytes.Length > 128) await Task.Delay(18);
        }
    }

    public async Task<BridgeResponse> SendAsync(string[] packets)
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

    public BridgeResponse Status(string? message = null) => new()
    {
        Ok = IsConnected,
        Connected = IsConnected,
        Name = _name,
        Address = _address?.ToString("X12", CultureInfo.InvariantCulture) ?? _lastAddress?.ToString("X12", CultureInfo.InvariantCulture) ?? "",
        Message = message ?? (IsConnected ? "D30 conectada" : "D30 desconectada")
    };

    public BridgeResponse Disconnect()
    {
        Cleanup();
        return new BridgeResponse { Ok = true, Connected = false, Name = _name, Address = _lastAddress?.ToString("X12", CultureInfo.InvariantCulture) ?? "", Message = "D30 desconectada" };
    }

    public BridgeResponse Quit()
    {
        Cleanup();
        return new BridgeResponse { Ok = true, Connected = false, Name = _name, Address = _lastAddress?.ToString("X12", CultureInfo.InvariantCulture) ?? "", Message = "Cerrando bridge", Quit = true };
    }

    private void Cleanup()
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

    public void Dispose() => Cleanup();
}
