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
        _http.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        _http.DefaultRequestHeaders.CacheControl = new CacheControlHeaderValue { NoCache = true, NoStore = true };
        _http.Timeout = TimeSpan.FromSeconds(25);
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
                throw new InvalidOperationException("La versión nueva no publicó su archivo SHA-256. No voy a instalar una actualización sin verificarla.");

            var updateDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "PhomemoStudio", "Updates", release.Value.Version.ToString());
            Directory.CreateDirectory(updateDir);

            var installerPath = Path.Combine(updateDir, "PhomemoStudioSetup.exe");
            if (!File.Exists(installerPath) || !HashMatches(installerPath, expectedHash))
            {
                var partPath = installerPath + ".part";
                try { if (File.Exists(partPath)) File.Delete(partPath); } catch { }

                using var request = new HttpRequestMessage(HttpMethod.Get, release.Value.InstallerUrl);
                request.Headers.CacheControl = new CacheControlHeaderValue { NoCache = true, NoStore = true };
                using var response = await _http.SendAsync(
                    request,
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
                    throw new InvalidDataException("La descarga terminó, pero el SHA-256 no coincide con el publicado en GitHub.");
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

    // Compatibilidad con instalaciones V3.0/V3.0.1 que todavía llaman este método.
    public async Task CheckAndOfferUpdateAsync(Window owner, bool quietIfCurrent = true)
    {
        try
        {
            var prepared = await CheckAndPrepareAsync().ConfigureAwait(true);
            if (prepared is null)
            {
                if (!quietIfCurrent)
                    MessageBox.Show(owner, $"Ya tenés la última versión ({CurrentVersion}).", "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            var answer = MessageBox.Show(owner,
                $"Phomemo Studio {prepared.Version} ya está descargado y verificado.\n\n¿Querés actualizar y reiniciar ahora?",
                "Actualización lista", MessageBoxButton.YesNo, MessageBoxImage.Information);
            if (answer == MessageBoxResult.Yes)
                InstallPreparedUpdate();
        }
        catch (Exception ex)
        {
            if (!quietIfCurrent)
                MessageBox.Show(owner, "No pude comprobar actualizaciones.\n\n" + ex.GetBaseException().Message,
                    "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
    }

    private async Task<(Version Version, string InstallerUrl, string? HashUrl, string? Notes)?> GetLatestReleaseAsync(CancellationToken cancellationToken)
    {
        var cacheBust = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        using var request = new HttpRequestMessage(HttpMethod.Get, $"{LatestReleaseApi}?t={cacheBust}");
        request.Headers.CacheControl = new CacheControlHeaderValue { NoCache = true, NoStore = true };
        using var response = await _http.SendAsync(request, cancellationToken).ConfigureAwait(false);
        if (!response.IsSuccessStatusCode)
            throw new HttpRequestException($"GitHub respondió {(int)response.StatusCode} ({response.ReasonPhrase}).");

        using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false));
        var root = doc.RootElement;
        var tag = root.GetProperty("tag_name").GetString() ?? string.Empty;
        if (!Version.TryParse(tag.TrimStart('v', 'V'), out var latest))
            throw new InvalidDataException($"GitHub publicó una versión que no pude interpretar: {tag}");

        string? installerUrl = null;
        string? hashUrl = null;
        foreach (var asset in root.GetProperty("assets").EnumerateArray())
        {
            var name = asset.GetProperty("name").GetString() ?? string.Empty;
            var url = asset.GetProperty("browser_download_url").GetString();
            if (name.Equals("PhomemoStudioSetup.exe", StringComparison.OrdinalIgnoreCase)) installerUrl = url;
            else if (name.Equals("PhomemoStudioSetup.exe.sha256", StringComparison.OrdinalIgnoreCase)) hashUrl = url;
        }

        if (string.IsNullOrWhiteSpace(installerUrl))
            throw new InvalidDataException($"La release v{latest} no contiene PhomemoStudioSetup.exe.");

        var notes = root.TryGetProperty("body", out var body) ? body.GetString() : null;
        return (latest, installerUrl, hashUrl, notes);
    }

    private async Task<string?> GetExpectedHashAsync(string? hashUrl, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(hashUrl)) return null;
        using var request = new HttpRequestMessage(HttpMethod.Get, hashUrl);
        request.Headers.CacheControl = new CacheControlHeaderValue { NoCache = true, NoStore = true };
        using var response = await _http.SendAsync(request, cancellationToken).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        var text = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
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
