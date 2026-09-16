using System.Runtime.InteropServices;
using System.Text.Json;
using PhomemoStudio.Models;

namespace PhomemoStudio.Services;

[ComVisible(true)]
[ClassInterface(ClassInterfaceType.AutoDual)]
public sealed class NativeBridge
{
    private readonly D30BluetoothService _bluetooth;
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };

    public NativeBridge(D30BluetoothService bluetooth) => _bluetooth = bluetooth;

    public string Connect(bool forceScan)
        => Run(() => _bluetooth.ConnectAsync(forceScan));

    public string AutoConnect()
        => Run(() => _bluetooth.AutoConnectAsync());

    public string GetStatus()
        => JsonSerializer.Serialize(_bluetooth.GetSnapshot(), JsonOptions);

    public string QueryStatus()
        => Run(() => _bluetooth.QueryStatusAsync());

    public string SendBase64(string base64)
    {
        try
        {
            var bytes = Convert.FromBase64String(base64);
            Task.Run(() => _bluetooth.SendAsync(bytes)).GetAwaiter().GetResult();
            return JsonSerializer.Serialize(new { ok = true, connected = _bluetooth.IsConnected }, JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(new { ok = false, connected = false, message = ex.Message }, JsonOptions);
        }
    }

    public string Disconnect(bool forget)
    {
        try
        {
            _bluetooth.Disconnect(forget);
            return JsonSerializer.Serialize(new { ok = true, connected = false }, JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(new { ok = false, connected = false, message = ex.Message }, JsonOptions);
        }
    }

    public string AppVersion() => ThisAssemblyVersion.Value;

    private static string Run(Func<Task<PrinterSnapshot>> action)
    {
        try
        {
            var snapshot = Task.Run(action).GetAwaiter().GetResult();
            return JsonSerializer.Serialize(snapshot, JsonOptions);
        }
        catch (Exception ex)
        {
            var snapshot = new PrinterSnapshot { Ok = false, Connected = false, Message = ex.GetBaseException().Message };
            return JsonSerializer.Serialize(snapshot, JsonOptions);
        }
    }
}

internal static class ThisAssemblyVersion
{
    public static string Value => typeof(NativeBridge).Assembly.GetName().Version?.ToString(3) ?? "3.0.0";
}
