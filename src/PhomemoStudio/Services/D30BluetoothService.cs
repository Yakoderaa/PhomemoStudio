using System.Globalization;
using System.Text.Json;
using Windows.Devices.Bluetooth;
using Windows.Devices.Bluetooth.Advertisement;
using Windows.Devices.Bluetooth.GenericAttributeProfile;
using Windows.Foundation;
using Windows.Storage.Streams;
using PhomemoStudio.Models;

namespace PhomemoStudio.Services;

public sealed class D30BluetoothService : IDisposable
{
    private static readonly Guid[] ServiceUuids =
    {
        new("0000ff00-0000-1000-8000-00805f9b34fb"),
        new("0000ae30-0000-1000-8000-00805f9b34fb"),
        new("0000af30-0000-1000-8000-00805f9b34fb"),
        new("0000ffe0-0000-1000-8000-00805f9b34fb"),
        new("49535343-fe7d-4ae5-8fa9-9fafd205e455")
    };

    private readonly SemaphoreSlim _connectGate = new(1, 1);
    private readonly SemaphoreSlim _sendGate = new(1, 1);
    private BluetoothLEDevice? _device;
    private GattDeviceService? _service;
    private GattCharacteristic? _write;
    private GattCharacteristic? _notify;
    private bool _notificationsEnabled;
    private NativeSettings _settings = NativeSettings.Load();
    private int? _battery;
    private string? _paper;
    private string? _cover;
    private string? _firmware;
    private string? _lastMessage;

    public bool IsConnected => _device?.ConnectionStatus == BluetoothConnectionStatus.Connected && _write is not null;

    public async Task<PrinterSnapshot> ConnectAsync(bool forceScan = false)
    {
        await _connectGate.WaitAsync().ConfigureAwait(false);
        try
        {
            if (IsConnected) return Snapshot("Ya conectada");

            Exception? savedError = null;
            if (!forceScan && _settings.BluetoothAddress is ulong savedAddress)
            {
                try
                {
                    await ConnectToAddressAsync(savedAddress, _settings.DeviceName).ConfigureAwait(false);
                    return Snapshot("D30 reconectada");
                }
                catch (Exception ex)
                {
                    savedError = ex;
                    CleanupDevice();
                }
            }

            var candidate = await ScanForD30Async(TimeSpan.FromSeconds(10)).ConfigureAwait(false);
            if (candidate is null)
            {
                throw new InvalidOperationException(savedError is null
                    ? "No encontré una D30 encendida. Verificá que esté prendida y cerca de la PC."
                    : $"No pude reconectar la D30 guardada ni encontrar otra. {savedError.Message}");
            }

            await ConnectToAddressAsync(candidate.Value.Address, candidate.Value.Name).ConfigureAwait(false);
            return Snapshot("D30 conectada");
        }
        finally
        {
            _connectGate.Release();
        }
    }

    public async Task<PrinterSnapshot> AutoConnectAsync()
    {
        if (IsConnected) return Snapshot("Conectada");
        if (!_settings.AutoConnect) return Snapshot("Autoconexión desactivada");
        try
        {
            return await ConnectAsync(false).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _lastMessage = ex.Message;
            return Snapshot(ex.Message, ok: false);
        }
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
                if (best is null || current.Rssi > best.Value.Rssi)
                    best = current;

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
            {
                return await tcs.Task.ConfigureAwait(false);
            }
        }
        finally
        {
            try { watcher.Stop(); } catch { }
            watcher.Received -= handler;
        }
    }

    private async Task ConnectToAddressAsync(ulong address, string? hintedName)
    {
        CleanupDevice();
        _lastMessage = "Abriendo Bluetooth nativo de Windows…";

        _device = await BluetoothLEDevice.FromBluetoothAddressAsync(address).AsTask().ConfigureAwait(false)
                  ?? throw new InvalidOperationException("Windows detectó la D30 pero no pudo abrir el dispositivo BLE.");
        _device.ConnectionStatusChanged += Device_ConnectionStatusChanged;

        GattDeviceService? foundService = null;
        Exception? last = null;
        foreach (var uuid in ServiceUuids)
        {
            try
            {
                var result = await _device.GetGattServicesForUuidAsync(uuid, BluetoothCacheMode.Uncached).AsTask().ConfigureAwait(false);
                if (result.Status == GattCommunicationStatus.Success && result.Services.Count > 0)
                {
                    foundService = result.Services[0];
                    break;
                }
            }
            catch (Exception ex) { last = ex; }
        }

        _service = foundService ?? throw new InvalidOperationException(last?.Message ?? "La D30 no expuso un servicio Bluetooth compatible.");
        var charsResult = await _service.GetCharacteristicsAsync(BluetoothCacheMode.Uncached).AsTask().ConfigureAwait(false);
        if (charsResult.Status != GattCommunicationStatus.Success)
            throw new InvalidOperationException($"No pude leer los canales GATT ({charsResult.Status}).");

        var chars = charsResult.Characteristics;
        _write = chars.FirstOrDefault(c => IsWriteUuid(c.Uuid))
              ?? chars.FirstOrDefault(c => c.CharacteristicProperties.HasFlag(GattCharacteristicProperties.WriteWithoutResponse))
              ?? chars.FirstOrDefault(c => c.CharacteristicProperties.HasFlag(GattCharacteristicProperties.Write));

        _notify = chars.FirstOrDefault(c => IsNotifyUuid(c.Uuid))
               ?? chars.FirstOrDefault(c => c.CharacteristicProperties.HasFlag(GattCharacteristicProperties.Notify))
               ?? chars.FirstOrDefault(c => c.CharacteristicProperties.HasFlag(GattCharacteristicProperties.Indicate));

        if (_write is null)
            throw new InvalidOperationException("Encontré la D30 pero no su canal de escritura.");

        _settings.BluetoothAddress = address;
        _settings.DeviceName = string.IsNullOrWhiteSpace(_device.Name) ? hintedName ?? "D30" : _device.Name;
        _settings.AutoConnect = true;
        _settings.Save();
        _lastMessage = $"Conectada por Windows · {_service.Uuid} · {_write.Uuid}";
    }

    private static bool IsWriteUuid(Guid uuid)
    {
        var s = uuid.ToString("D");
        return s.StartsWith("0000ff02", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000ae01", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000af01", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000ffe1", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsNotifyUuid(Guid uuid)
    {
        var s = uuid.ToString("D");
        return s.StartsWith("0000ff03", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000ae02", StringComparison.OrdinalIgnoreCase) ||
               s.StartsWith("0000af02", StringComparison.OrdinalIgnoreCase);
    }

    public async Task SendAsync(byte[] bytes)
    {
        if (bytes.Length == 0) return;
        if (!IsConnected || _write is null)
            await ConnectAsync(false).ConfigureAwait(false);
        if (_write is null) throw new InvalidOperationException("La D30 no está conectada.");

        await _sendGate.WaitAsync().ConfigureAwait(false);
        try
        {
            using var writer = new DataWriter();
            writer.WriteBytes(bytes);
            var buffer = writer.DetachBuffer();
            var option = _write.CharacteristicProperties.HasFlag(GattCharacteristicProperties.WriteWithoutResponse)
                ? GattWriteOption.WriteWithoutResponse
                : GattWriteOption.WriteWithResponse;
            var result = await _write.WriteValueWithResultAsync(buffer, option).AsTask().ConfigureAwait(false);
            if (result.Status != GattCommunicationStatus.Success)
                throw new InvalidOperationException($"Windows no pudo enviar datos a la D30 ({result.Status}).");
        }
        catch
        {
            _lastMessage = "Se perdió la conexión con la D30.";
            throw;
        }
        finally
        {
            _sendGate.Release();
        }
    }

    public async Task<PrinterSnapshot> QueryStatusAsync()
    {
        if (!IsConnected) await ConnectAsync(false).ConfigureAwait(false);
        await EnsureNotificationsAsync().ConfigureAwait(false);
        await Task.Delay(120).ConfigureAwait(false);

        await SendAsync(new byte[] { 0x1f, 0x11, 0x08 }).ConfigureAwait(false);
        await Task.Delay(180).ConfigureAwait(false);
        await SendAsync(new byte[] { 0x1f, 0x11, 0x11 }).ConfigureAwait(false);
        await Task.Delay(150).ConfigureAwait(false);
        await SendAsync(new byte[] { 0x1f, 0x11, 0x12 }).ConfigureAwait(false);
        await Task.Delay(100).ConfigureAwait(false);
        return Snapshot("Estado actualizado");
    }

    private async Task EnsureNotificationsAsync()
    {
        if (_notificationsEnabled) return;
        if (_notify is null) throw new InvalidOperationException("Este firmware no expone el canal de estado/batería.");
        _notify.ValueChanged -= Notify_ValueChanged;
        _notify.ValueChanged += Notify_ValueChanged;

        var mode = _notify.CharacteristicProperties.HasFlag(GattCharacteristicProperties.Notify)
            ? GattClientCharacteristicConfigurationDescriptorValue.Notify
            : GattClientCharacteristicConfigurationDescriptorValue.Indicate;
        var status = await _notify.WriteClientCharacteristicConfigurationDescriptorAsync(mode).AsTask().ConfigureAwait(false);
        if (status != GattCommunicationStatus.Success)
            throw new InvalidOperationException($"No pude activar el canal de batería ({status}).");
        _notificationsEnabled = true;
    }

    private void Notify_ValueChanged(GattCharacteristic sender, GattValueChangedEventArgs args)
    {
        try
        {
            using var reader = DataReader.FromBuffer(args.CharacteristicValue);
            var data = new byte[args.CharacteristicValue.Length];
            reader.ReadBytes(data);
            if (data.Length < 3 || data[0] != 0x1a) return;
            var type = data[1];
            var v = data[2];
            switch (type)
            {
                case 0x04:
                    _battery = v switch { 0xa4 => 0, 0xa3 => 3, 0xa2 => 5, 0xa1 => 10, _ => v };
                    break;
                case 0x06:
                    _paper = v == 0x88 ? "out" : "ok";
                    break;
                case 0x05:
                    _cover = v == 0x98 ? "open" : v == 0x99 ? "closed" : "unknown";
                    break;
                case 0x07:
                    _firmware = string.Join('.', data.Skip(2));
                    break;
            }
        }
        catch { }
    }

    public PrinterSnapshot GetSnapshot() => Snapshot(_lastMessage ?? (IsConnected ? "Conectada" : "Desconectada"));

    private PrinterSnapshot Snapshot(string? message, bool ok = true) => new()
    {
        Ok = ok,
        Connected = IsConnected,
        DeviceName = _settings.DeviceName ?? _device?.Name,
        Address = _settings.BluetoothAddress?.ToString("X12", CultureInfo.InvariantCulture),
        Battery = _battery,
        Paper = _paper,
        Cover = _cover,
        Firmware = _firmware,
        Message = message,
        ServiceUuid = _service?.Uuid.ToString(),
        WriteUuid = _write?.Uuid.ToString()
    };

    public void Disconnect(bool forget = false)
    {
        CleanupDevice();
        if (forget)
        {
            _settings.BluetoothAddress = null;
            _settings.DeviceName = null;
            _settings.Save();
        }
        _lastMessage = "Desconectada";
    }

    private void Device_ConnectionStatusChanged(BluetoothLEDevice sender, object args)
    {
        if (sender.ConnectionStatus == BluetoothConnectionStatus.Disconnected)
        {
            _write = null;
            _notify = null;
            _service?.Dispose();
            _service = null;
            _notificationsEnabled = false;
            _lastMessage = "D30 en reposo o desconectada; la app intentará reconectar.";
        }
    }

    private void CleanupDevice()
    {
        try
        {
            if (_notify is not null) _notify.ValueChanged -= Notify_ValueChanged;
            _service?.Dispose();
            if (_device is not null) _device.ConnectionStatusChanged -= Device_ConnectionStatusChanged;
            _device?.Dispose();
        }
        catch { }
        _device = null;
        _service = null;
        _write = null;
        _notify = null;
        _notificationsEnabled = false;
    }

    public void Dispose()
    {
        CleanupDevice();
        _connectGate.Dispose();
        _sendGate.Dispose();
    }
}
