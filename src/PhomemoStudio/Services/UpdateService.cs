using System.Diagnostics;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Windows;

namespace PhomemoStudio.Services;

public sealed class UpdateService
{
    private const string LatestReleaseApi = "https://api.github.com/repos/Yakoderaa/PhomemoStudio/releases/latest";
    private readonly HttpClient _http = new();

    public UpdateService()
    {
        _http.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("PhomemoStudio", CurrentVersion.ToString()));
        _http.Timeout = TimeSpan.FromSeconds(30);
    }

    public static Version CurrentVersion
    {
        get
        {
            var v = Assembly.GetExecutingAssembly().GetName().Version ?? new Version(3, 0, 0);
            return new Version(v.Major, v.Minor, Math.Max(0, v.Build));
        }
    }

    public async Task CheckAndOfferUpdateAsync(Window owner, bool quietIfCurrent = true)
    {
        try
        {
            using var response = await _http.GetAsync(LatestReleaseApi).ConfigureAwait(true);
            if (!response.IsSuccessStatusCode) return;
            using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync().ConfigureAwait(true));
            var root = doc.RootElement;
            var tag = root.GetProperty("tag_name").GetString() ?? string.Empty;
            if (!Version.TryParse(tag.TrimStart('v', 'V'), out var latest)) return;
            if (latest <= CurrentVersion)
            {
                if (!quietIfCurrent) MessageBox.Show(owner, "Ya tenés la última versión.", "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            string? installerUrl = null;
            string? hashUrl = null;
            foreach (var asset in root.GetProperty("assets").EnumerateArray())
            {
                var name = asset.GetProperty("name").GetString() ?? string.Empty;
                var url = asset.GetProperty("browser_download_url").GetString();
                if (name.Equals("PhomemoStudioSetup.exe", StringComparison.OrdinalIgnoreCase)) installerUrl = url;
                else if (name.Equals("PhomemoStudioSetup.exe.sha256", StringComparison.OrdinalIgnoreCase)) hashUrl = url;
            }
            if (installerUrl is null) return;

            var answer = MessageBox.Show(owner,
                $"Hay una nueva versión de Phomemo Studio ({latest}).\n\n¿Querés descargarla e instalarla ahora?",
                "Actualización disponible", MessageBoxButton.YesNo, MessageBoxImage.Information);
            if (answer != MessageBoxResult.Yes) return;

            var tempDir = Path.Combine(Path.GetTempPath(), "PhomemoStudioUpdate");
            Directory.CreateDirectory(tempDir);
            var installerPath = Path.Combine(tempDir, "PhomemoStudioSetup.exe");
            var bytes = await _http.GetByteArrayAsync(installerUrl).ConfigureAwait(true);
            await File.WriteAllBytesAsync(installerPath, bytes).ConfigureAwait(true);

            if (hashUrl is not null)
            {
                var expectedText = await _http.GetStringAsync(hashUrl).ConfigureAwait(true);
                var expected = expectedText.Trim().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)[0];
                var actual = Convert.ToHexString(SHA256.HashData(bytes));
                if (!actual.Equals(expected, StringComparison.OrdinalIgnoreCase))
                {
                    File.Delete(installerPath);
                    MessageBox.Show(owner, "La actualización descargada no pasó la verificación SHA-256.", "Actualización cancelada", MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }
            }

            Process.Start(new ProcessStartInfo
            {
                FileName = installerPath,
                Arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS",
                UseShellExecute = true
            });
            Application.Current.Shutdown();
        }
        catch
        {
            // El actualizador nunca debe impedir usar la impresora.
        }
    }
}
