using System.IO;
using System.Text.Json;

namespace PhomemoStudio.Services;

public sealed class NativeSettings
{
    public ulong? BluetoothAddress { get; set; }
    public string? DeviceName { get; set; }
    public bool AutoConnect { get; set; } = true;

    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    public static string DataDirectory => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PhomemoStudio");
    public static string SettingsPath => Path.Combine(DataDirectory, "native-settings.json");

    public static NativeSettings Load()
    {
        try
        {
            Directory.CreateDirectory(DataDirectory);
            if (!File.Exists(SettingsPath)) return new NativeSettings();
            return JsonSerializer.Deserialize<NativeSettings>(File.ReadAllText(SettingsPath)) ?? new NativeSettings();
        }
        catch { return new NativeSettings(); }
    }

    public void Save()
    {
        Directory.CreateDirectory(DataDirectory);
        var tmp = SettingsPath + ".tmp";
        File.WriteAllText(tmp, JsonSerializer.Serialize(this, JsonOptions));
        File.Move(tmp, SettingsPath, true);
    }
}
