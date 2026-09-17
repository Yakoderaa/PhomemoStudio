using System.Globalization;
using System.Text.Json;
using Windows.Devices.Bluetooth;
using Windows.Devices.Bluetooth.Advertisement;
using Windows.Devices.Bluetooth.GenericAttributeProfile;
using Windows.Foundation;
using Windows.Storage.Streams;

namespace PhomemoBleBridge;

internal static class Program
{
    public static async Task Main()
    {
        Console.OutputEncoding = System.Text.Encoding.UTF8;
        using var bridge = new D30Bridge();
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

            Console.WriteLine(JsonSerializer.Serialize(response, JsonOptions.Options));
            Console.Out.Flush();
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
    public bool Quit { get; set; }

    public static BridgeResponse Fail(string message) => new() { Ok = false, Message = message };
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

    private BluetoothLEDevice? _device;
    private GattDeviceService? _service;
    private GattSession? _session;
    private GattCharacteristic? _write;
    private ulong? _address;
    private string _name = "D30";

    private bool IsConnected => _write is not null &&
        (_device?.ConnectionStatus == BluetoothConnectionStatus.Connected || _session?.SessionStatus == GattSessionStatus.Active);

    public async Task<BridgeResponse> ConnectAsync(string? preferredAddress)
    {
        if (IsConnected) return Status("D30 conectada");

        if (TryParseAddress(preferredAddress, out var saved))
        {
            try
            {
                await ConnectToAddressAsync(saved, "D30");
                return Status("D30 reconectada con Bluetooth nativo de Windows");
            }
            catch
            {
                Cleanup();
            }
        }

        var candidate = await ScanForD30Async(TimeSpan.FromSeconds(14));
        if (candidate is null)
            return BridgeResponse.Fail("El Bluetooth nativo de Windows no encontró una D30 anunciándose. Apagala y prendela, esperá 2 segundos y reintentá.");

        await ConnectToAddressAsync(candidate.Value.Address, candidate.Value.Name);
        return Status("D30 conectada con el mismo backend Bluetooth nativo que usaba la versión anterior");
    }

    private static bool TryParseAddress(string? raw, out ulong address)
    {
        address = 0;
        if (string.IsNullOrWhiteSpace(raw)) return false;
        var cleaned = new string(raw.Where(Uri.IsHexDigit).ToArray());
        return cleaned.Length <= 12 && ulong.TryParse(cleaned, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out address);
    }

    private async Task<(ulong Address, string Name)?> ScanForD30Async(TimeSpan timeout)
    {
        var tcs = new TaskCompletionSource<(ulong, string)?>(TaskCreationOptions.RunContinuationsAsynchronously);
        using var cts = new CancellationTokenSource(timeout);
        var watcher = new BluetoothLEAdvertisementWatcher { ScanningMode = BluetoothLEScanningMode.Active };
        (ulong Address, string Name, short Rssi)? best = null;

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
                var current = (Address: args.BluetoothAddress, Name: displayName, Rssi: args.RawSignalStrengthInDBm);
                if (best is null || current.Rssi > best.Value.Rssi) best = current;

                if (name.Equals("D30", StringComparison.OrdinalIgnoreCase))
                    tcs.TrySetResult((args.BluetoothAddress, displayName));
            }
            catch { }
        };

        watcher.Received += handler;
        watcher.Start();
        try
        {
            using (cts.Token.Register(() => tcs.TrySetResult(best is null ? null : (best.Value.Address, best.Value.Name))))
                return await tcs.Task.ConfigureAwait(false);
        }
        finally
        {
            try { watcher.Stop(); } catch { }
            watcher.Received -= handler;
        }
    }

    private async Task ConnectToAddressAsync(ulong address, string hintedName)
    {
        Cleanup();
        _device = await BluetoothLEDevice.FromBluetoothAddressAsync(address).AsTask().ConfigureAwait(false)
                  ?? throw new InvalidOperationException("Windows detectó la D30 pero no pudo abrir el dispositivo BLE.");

        GattDeviceService? found = null;
        Exception? last = null;
        foreach (var uuid in ServiceUuids)
        {
            try
            {
                var result = await _device.GetGattServicesForUuidAsync(uuid, BluetoothCacheMode.Uncached).AsTask().ConfigureAwait(false);
                if (result.Status == GattCommunicationStatus.Success && result.Services.Count > 0)
                {
                    found = result.Services[0];
                    break;
                }
            }
            catch (Exception ex) { last = ex; }
        }

        _service = found ?? throw new InvalidOperationException(last?.Message ?? "La D30 no expuso un servicio Bluetooth compatible.");
        _session = _service.Session;
        if (_session.CanMaintainConnection) _session.MaintainConnection = true;

        var charsResult = await _service.GetCharacteristicsAsync(BluetoothCacheMode.Uncached).AsTask().ConfigureAwait(false);
        if (charsResult.Status != GattCommunicationStatus.Success)
            throw new InvalidOperationException($"No pude leer los canales GATT ({charsResult.Status}).");

        _write = charsResult.Characteristics.FirstOrDefault(c => IsWriteUuid(c.Uuid))
              ?? charsResult.Characteristics.FirstOrDefault(c => c.CharacteristicProperties.HasFlag(GattCharacteristicProperties.WriteWithoutResponse))
              ?? charsResult.Characteristics.FirstOrDefault(c => c.CharacteristicProperties.HasFlag(GattCharacteristicProperties.Write));

        if (_write is null) throw new InvalidOperationException("Encontré la D30 pero no su canal de escritura.");

        _address = address;
        _name = string.IsNullOrWhiteSpace(_device.Name) ? hintedName : _device.Name;
        await Task.Delay(700).ConfigureAwait(false);
    }

    private static bool IsWriteUuid(Guid uuid)
    {
        var s = uuid.ToString("D");
        return s.StartsWith("0000ff02", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000ae01", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000af01", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000ffe1", StringComparison.OrdinalIgnoreCase);
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
                for (var i = 0; i < bytes.Length; i += 128)
                {
                    var chunk = bytes.AsSpan(i, Math.Min(128, bytes.Length - i)).ToArray();
                    using var writer = new DataWriter();
                    writer.WriteBytes(chunk);
                    var buffer = writer.DetachBuffer();
                    var option = _write.CharacteristicProperties.HasFlag(GattCharacteristicProperties.WriteWithoutResponse)
                        ? GattWriteOption.WriteWithoutResponse
                        : GattWriteOption.WriteWithResponse;
                    var result = await _write.WriteValueWithResultAsync(buffer, option).AsTask().ConfigureAwait(false);
                    if (result.Status != GattCommunicationStatus.Success)
                        throw new InvalidOperationException($"Windows no pudo enviar datos a la D30 ({result.Status}).");
                    await Task.Delay(18).ConfigureAwait(false);
                }
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
        Address = _address?.ToString("X12", CultureInfo.InvariantCulture) ?? "",
        Message = message ?? (IsConnected ? "D30 conectada" : "D30 desconectada")
    };

    public BridgeResponse Disconnect()
    {
        Cleanup();
        return new BridgeResponse { Ok = true, Connected = false, Name = _name, Message = "D30 desconectada" };
    }

    public BridgeResponse Quit()
    {
        Cleanup();
        return new BridgeResponse { Ok = true, Connected = false, Name = _name, Message = "Cerrando bridge", Quit = true };
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
