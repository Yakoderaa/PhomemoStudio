using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;
using PhomemoStudio.Services;

namespace PhomemoStudio;

public partial class MainWindow : Window
{
    private readonly D30BluetoothService _bluetooth = new();
    private NativeBridge? _bridge;
    private readonly UpdateService _updates = new();
    private readonly DispatcherTimer _updateTimer;
    private PreparedUpdate? _preparedUpdate;
    private bool _isCheckingUpdates;
    private bool _updateInstallStarted;

    public MainWindow()
    {
        InitializeComponent();

        _updateTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromMinutes(15)
        };
        _updateTimer.Tick += async (_, _) => await CheckForUpdatesAsync();

        Loaded += OnLoaded;
        Closed += (_, _) =>
        {
            _updateTimer.Stop();
            try { _updates.Dispose(); } catch { }
            try { _bluetooth.Dispose(); } catch { }
        };
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            var dataDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PhomemoStudio", "WebView2");
            Directory.CreateDirectory(dataDir);
            var env = await CoreWebView2Environment.CreateAsync(userDataFolder: dataDir);
            await Web.EnsureCoreWebView2Async(env);

            Web.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
            Web.CoreWebView2.Settings.AreDevToolsEnabled = false;
            Web.CoreWebView2.Settings.IsStatusBarEnabled = false;
            Web.CoreWebView2.Settings.AreBrowserAcceleratorKeysEnabled = true;

            var webRoot = Path.Combine(AppContext.BaseDirectory, "web");
            Web.CoreWebView2.SetVirtualHostNameToFolderMapping(
                "app.phomemostudio.local",
                webRoot,
                CoreWebView2HostResourceAccessKind.Allow);

            _bridge = new NativeBridge(_bluetooth);
            Web.CoreWebView2.AddHostObjectToScript("nativeBridge", _bridge);
            Web.CoreWebView2.WebMessageReceived += WebMessageReceived;
            Web.Source = new Uri("https://app.phomemostudio.local/index.html");

            UpdateStatusText.Text = $"Phomemo Studio {UpdateService.CurrentVersion} · actualizaciones automáticas activas";
            _updateTimer.Start();
            _ = CheckAfterStartupAsync();
        }
        catch (Exception ex)
        {
            MessageBox.Show(this,
                "No pude iniciar la interfaz de Phomemo Studio.\n\n" + ex.Message +
                "\n\nWindows 11 normalmente incluye Microsoft Edge WebView2. Si fue removido, reinstalalo y volvé a abrir la app.",
                "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Error);
            Close();
        }
    }

    private async Task CheckAfterStartupAsync()
    {
        await Task.Delay(3500);
        await CheckForUpdatesAsync(installAutomatically: true, notifyIfCurrent: false);
    }

    private async Task CheckForUpdatesAsync(bool installAutomatically = false, bool notifyIfCurrent = false)
    {
        if (_updateInstallStarted)
            return;

        if (_isCheckingUpdates)
        {
            if (notifyIfCurrent)
                MessageBox.Show(this, "Ya estoy buscando actualizaciones.", "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        _isCheckingUpdates = true;
        SearchUpdateButton.IsEnabled = false;
        SearchUpdateButton.Content = "Buscando…";
        UpdateStatusText.Text = "Buscando actualizaciones…";
        InstallUpdateButton.Visibility = Visibility.Collapsed;

        var progress = new Progress<UpdateProgress>(ApplyUpdateProgress);

        try
        {
            var prepared = await _updates.CheckAndPrepareAsync(progress);
            if (prepared is null)
            {
                UpdateBanner.Visibility = Visibility.Collapsed;
                UpdateStatusText.Text = $"Versión {UpdateService.CurrentVersion} · al día";
                if (notifyIfCurrent)
                    MessageBox.Show(this, $"Ya tenés la última versión ({UpdateService.CurrentVersion}).", "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            _preparedUpdate = prepared;
            UpdateTitle.Text = $"Phomemo Studio {prepared.Version} listo";
            UpdateText.Text = "La descarga terminó y el SHA-256 fue verificado.";
            UpdateProgressBar.Visibility = Visibility.Visible;
            UpdateProgressBar.IsIndeterminate = false;
            UpdateProgressBar.Value = 100;
            UpdateProgressText.Visibility = Visibility.Visible;
            UpdateProgressText.Text = "100% · descarga verificada";
            UpdateBanner.Visibility = Visibility.Visible;
            UpdateStatusText.Text = $"Actualización {prepared.Version} verificada";

            if (installAutomatically)
            {
                await BeginInstallAsync();
                return;
            }

            InstallUpdateButton.Visibility = Visibility.Visible;
            if (notifyIfCurrent)
            {
                MessageBox.Show(this,
                    $"Encontré Phomemo Studio {prepared.Version}. Ya está descargado y verificado.\n\nTocá “Actualizar y reiniciar” para instalarlo.",
                    "Actualización encontrada", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }
        catch (Exception ex)
        {
            _updateInstallStarted = false;
            UpdateProgressBar.IsIndeterminate = false;
            UpdateProgressBar.Visibility = Visibility.Collapsed;
            UpdateProgressText.Visibility = Visibility.Collapsed;
            UpdateStatusText.Text = "No se pudo completar la actualización";
            UpdateTitle.Text = "Error al actualizar";
            UpdateText.Text = ex.GetBaseException().Message;
            UpdateBanner.Visibility = Visibility.Visible;

            if (notifyIfCurrent)
            {
                MessageBox.Show(this,
                    "No pude completar la actualización.\n\n" + ex.GetBaseException().Message,
                    "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }
        finally
        {
            _isCheckingUpdates = false;
            if (!_updateInstallStarted)
            {
                SearchUpdateButton.IsEnabled = true;
                SearchUpdateButton.Content = "Buscar actualizaciones";
            }
        }
    }

    private void ApplyUpdateProgress(UpdateProgress progress)
    {
        UpdateBanner.Visibility = Visibility.Visible;
        UpdateText.Text = progress.Message;
        UpdateProgressBar.Visibility = Visibility.Visible;
        UpdateProgressText.Visibility = Visibility.Visible;

        switch (progress.Stage)
        {
            case "checking":
                UpdateTitle.Text = "Buscando actualización";
                UpdateStatusText.Text = "Consultando GitHub…";
                break;
            case "found":
                UpdateTitle.Text = "Actualización encontrada";
                UpdateStatusText.Text = progress.Message;
                break;
            case "downloading":
                UpdateTitle.Text = "Descargando actualización";
                UpdateStatusText.Text = progress.Message;
                break;
            case "verifying":
                UpdateTitle.Text = "Verificando actualización";
                UpdateStatusText.Text = progress.Message;
                break;
            case "ready":
                UpdateTitle.Text = "Actualización lista";
                UpdateStatusText.Text = progress.Message;
                break;
        }

        if (progress.Percent.HasValue)
        {
            UpdateProgressBar.IsIndeterminate = false;
            UpdateProgressBar.Value = Math.Clamp(progress.Percent.Value, 0, 100);
            UpdateProgressText.Text = $"{UpdateProgressBar.Value:0}%";
        }
        else
        {
            UpdateProgressBar.IsIndeterminate = true;
            UpdateProgressText.Text = progress.Message;
        }
    }

    private async Task BeginInstallAsync()
    {
        if (_preparedUpdate is null)
            throw new InvalidOperationException("Todavía no hay una actualización descargada.");

        _updateInstallStarted = true;
        SearchUpdateButton.IsEnabled = false;
        SearchUpdateButton.Content = "Instalando…";
        InstallUpdateButton.IsEnabled = false;
        InstallUpdateButton.Visibility = Visibility.Collapsed;
        UpdateTitle.Text = $"Instalando Phomemo Studio {_preparedUpdate.Version}";
        UpdateText.Text = "Abriendo el instalador. Vas a ver el progreso de instalación; al terminar, Phomemo Studio se abrirá otra vez automáticamente.";
        UpdateStatusText.Text = $"Instalando {_preparedUpdate.Version}…";
        UpdateProgressBar.Visibility = Visibility.Visible;
        UpdateProgressBar.IsIndeterminate = true;
        UpdateProgressText.Visibility = Visibility.Visible;
        UpdateProgressText.Text = "Iniciando instalador…";

        // Da tiempo a WPF a pintar el estado antes de entregar el control al instalador.
        await Task.Delay(700);
        _updates.InstallPreparedUpdate();
    }

    private async void SearchUpdates_Click(object sender, RoutedEventArgs e)
    {
        // El botón ejecuta el flujo completo: buscar -> descargar -> verificar -> instalar -> reiniciar.
        await CheckForUpdatesAsync(installAutomatically: true, notifyIfCurrent: true);
    }

    private async void InstallUpdate_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            await BeginInstallAsync();
        }
        catch (Exception ex)
        {
            _updateInstallStarted = false;
            InstallUpdateButton.IsEnabled = true;
            InstallUpdateButton.Visibility = Visibility.Visible;
            InstallUpdateButton.Content = "Actualizar y reiniciar";
            SearchUpdateButton.IsEnabled = true;
            SearchUpdateButton.Content = "Buscar actualizaciones";
            UpdateProgressBar.IsIndeterminate = false;
            UpdateStatusText.Text = "No se pudo iniciar la actualización";
            MessageBox.Show(this, "No pude iniciar la actualización.\n\n" + ex.Message, "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void CloseApp_Click(object sender, RoutedEventArgs e)
    {
        Close();
    }

    private async void WebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
    {
        try
        {
            using var doc = JsonDocument.Parse(e.WebMessageAsJson);
            if (!doc.RootElement.TryGetProperty("type", out var typeElement)) return;
            var type = typeElement.GetString();

            if (type == "checkUpdates")
            {
                await CheckForUpdatesAsync(installAutomatically: true, notifyIfCurrent: true);
            }
            else if (type == "closeApp")
            {
                Close();
            }
        }
        catch
        {
            // Un mensaje web inválido no debe afectar la ventana principal.
        }
    }
}
