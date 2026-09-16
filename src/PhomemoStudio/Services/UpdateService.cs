using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Windows;

namespace PhomemoStudio.Services;

public sealed record PreparedUpdate(Version Version, string InstallerPath, string? Notes);

public sealed class UpdateService : IDisposable
{
    private const string LatestReleaseApi = "https://api.github.com/repos/Yakoderaa/PhomemoStudio/releases/latest";
    private readonly HttpClient _http = new();
    private readonly SemaphoreSlim _checkGate = new(1, 1);

    public PreparedUpdate? Prepared { get; private set; }

    public UpdateService()
    {
        _http.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("PhomemoStudio", CurrentVersion.ToString()));
        _http.Timeout = TimeSpan.FromMinutes(3);
    }

    public static Version CurrentVersion
    {
        get
        {
            var v = Assembly.GetExecutingAssembly().GetName().Version ?? new Version(3, 0, 0);
            return new Version(v.Major, v.Minor, Math.Max(0, v.Build));
        }
    }

    public async Task<PreparedUpdate?> CheckAndPrepareAsync(CancellationToken cancellationToken = default)
    {
        await _checkGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            var release = await GetLatestReleaseAsync(cancellationToken).ConfigureAwait(false);
            if (release is null || release.Value.Version <= CurrentVersion)
                return null;

            if (Prepared is not null && Prepared.Version == release.Value.Version && File.Exists(Prepared.InstallerPath))
                return Prepared;

            var expectedHash = await GetExpectedHashAsync(release.Value.HashUrl, cancellationToken).ConfigureAwait(false);
            if (string.IsNullOrWhiteSpace(expectedHash))
                return null;

            var updateDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "PhomemoStudio", "Updates", release.Value.Version.ToString());
            Directory.CreateDirectory(updateDir);

            var installerPath = Path.Combine(updateDir, "PhomemoStudioSetup.exe");
            if (!File.Exists(installerPath) || !HashMatches(installerPath, expectedHash))
            {
                var partPath = installerPath + ".part";
                try { if (File.Exists(partPath)) File.Delete(partPath); } catch { }

                using var response = await _http.GetAsync(
                    release.Value.InstallerUrl,
                    HttpCompletionOption.ResponseHeadersRead,
                    cancellationToken).ConfigureAwait(false);
                response.EnsureSuccessStatusCode();

                await using (var input = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false))
                await using (var output = new FileStream(partPath, FileMode.Create, FileAccess.Write, FileShare.None, 81920, true))
                {
                    await input.CopyToAsync(output, cancellationToken).ConfigureAwait(false);
                }

                if (!HashMatches(partPath, expectedHash))
                {
                    try { File.Delete(partPath); } catch { }
                    return null;
                }

                File.Move(partPath, installerPath, true);
            }

            Prepared = new PreparedUpdate(release.Value.Version, installerPath, release.Value.Notes);
            return Prepared;
        }
        finally
        {
            _checkGate.Release();
        }
    }

    public void InstallPreparedUpdate()
    {
        var prepared = Prepared;
        if (prepared is null || !File.Exists(prepared.InstallerPath))
            throw new InvalidOperationException("No hay una actualización descargada lista para instalar.");

        Process.Start(new ProcessStartInfo
        {
            FileName = prepared.InstallerPath,
            Arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS",
            UseShellExecute = true
        });
        Application.Current.Shutdown();
    }

    // Se mantiene para actualizar correctamente instalaciones V3.0/V3.0.1.
    public async Task CheckAndOfferUpdateAsync(Window owner, bool quietIfCurrent = true)
    {
        try
        {
            var prepared = await CheckAndPrepareAsync().ConfigureAwait(true);
            if (prepared is null)
            {
                if (!quietIfCurrent)
                    MessageBox.Show(owner, "Ya tenés la última versión.", "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            var answer = MessageBox.Show(owner,
                $"Phomemo Studio {prepared.Version} ya está descargado y verificado.\n\n¿Querés actualizar y reiniciar ahora?",
                "Actualización lista", MessageBoxButton.YesNo, MessageBoxImage.Information);
            if (answer == MessageBoxResult.Yes)
                InstallPreparedUpdate();
        }
        catch
        {
            // Una falla del actualizador nunca debe impedir usar la impresora.
        }
    }

    private async Task<(Version Version, string InstallerUrl, string? HashUrl, string? Notes)?> GetLatestReleaseAsync(CancellationToken cancellationToken)
    {
        using var response = await _http.GetAsync(LatestReleaseApi, cancellationToken).ConfigureAwait(false);
        if (!response.IsSuccessStatusCode) return null;

        using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false));
        var root = doc.RootElement;
        var tag = root.GetProperty("tag_name").GetString() ?? string.Empty;
        if (!Version.TryParse(tag.TrimStart('v', 'V'), out var latest)) return null;

        string? installerUrl = null;
        string? hashUrl = null;
        foreach (var asset in root.GetProperty("assets").EnumerateArray())
        {
            var name = asset.GetProperty("name").GetString() ?? string.Empty;
            var url = asset.GetProperty("browser_download_url").GetString();
            if (name.Equals("PhomemoStudioSetup.exe", StringComparison.OrdinalIgnoreCase)) installerUrl = url;
            else if (name.Equals("PhomemoStudioSetup.exe.sha256", StringComparison.OrdinalIgnoreCase)) hashUrl = url;
        }

        if (string.IsNullOrWhiteSpace(installerUrl)) return null;
        var notes = root.TryGetProperty("body", out var body) ? body.GetString() : null;
        return (latest, installerUrl, hashUrl, notes);
    }

    private async Task<string?> GetExpectedHashAsync(string? hashUrl, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(hashUrl)) return null;
        var text = await _http.GetStringAsync(hashUrl, cancellationToken).ConfigureAwait(false);
        return text.Trim().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries).FirstOrDefault();
    }

    private static bool HashMatches(string path, string expected)
    {
        try
        {
            using var stream = File.OpenRead(path);
            var actual = Convert.ToHexString(SHA256.HashData(stream));
            return actual.Equals(expected, StringComparison.OrdinalIgnoreCase);
        }
        catch
        {
            return false;
        }
    }

    public void Dispose()
    {
        _http.Dispose();
        _checkGate.Dispose();
    }
}
