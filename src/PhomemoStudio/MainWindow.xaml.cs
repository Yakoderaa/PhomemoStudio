using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;
using PhomemoStudio.Services;

namespace PhomemoStudio;

public partial class MainWindow : Window
{
    private const int WmNcLButtonDown = 0x00A1;
    private const int HtCaption = 0x0002;

    [DllImport("user32.dll")]
    private static extern bool ReleaseCapture();

    [DllImport("user32.dll")]
    private static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

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

        StateChanged += (_, _) => RefreshWindowStateButton();
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
            VersionText.Text = $"D30 Desktop · {UpdateService.CurrentVersion}";
            RefreshWindowStateButton();

            var dataDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "PhomemoStudio", "WebView2");
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

            UpdateStatusText.Text = $"Versión {UpdateService.CurrentVersion} · actualizaciones automáticas";
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

    private void TitleBar_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton != MouseButton.Left)
            return;

        // Entrega el arrastre al propio administrador de ventanas de Windows.
        // Así vuelven a funcionar mover, Snap Layouts y arrastrar desde maximizado.
        var hwnd = new WindowInteropHelper(this).Handle;
        if (hwnd == IntPtr.Zero)
            return;

        ReleaseCapture();
        SendMessage(hwnd, WmNcLButtonDown, (IntPtr)HtCaption, IntPtr.Zero);
    }

    private void MinimizeWindow_Click(object sender, RoutedEventArgs e)
    {
        SystemCommands.MinimizeWindow(this);
    }

    private void MaximizeRestoreWindow_Click(object sender, RoutedEventArgs e)
    {
        if (WindowState == WindowState.Maximized)
            SystemCommands.RestoreWindow(this);
        else
            SystemCommands.MaximizeWindow(this);
    }

    private void CloseWindow_Click(object sender, RoutedEventArgs e)
    {
        SystemCommands.CloseWindow(this);
    }

    private void RefreshWindowStateButton()
    {
        if (MaximizeRestoreButton is null)
            return;

        if (WindowState == WindowState.Maximized)
        {
            MaximizeRestoreButton.Content = "❐";
            MaximizeRestoreButton.ToolTip = "Restaurar";
        }
        else
        {
            MaximizeRestoreButton.Content = "□";
            MaximizeRestoreButton.ToolTip = "Maximizar";
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
            UpdateStatusText.Text = "Ya estoy buscando actualizaciones…";
            PostUpdateState("checking", "Ya estoy buscando actualizaciones…", null, true);
            return;
        }

        _isCheckingUpdates = true;
        SearchUpdateButton.IsEnabled = false;
        SearchUpdateButton.Content = "Buscando…";
        UpdateStatusText.Text = "Buscando actualizaciones…";

        UpdateBanner.Visibility = Visibility.Visible;
        UpdateTitle.Text = "Buscando actualización";
        UpdateText.Text = "Consultando la última versión publicada…";
        UpdateProgressBar.Visibility = Visibility.Visible;
        UpdateProgressBar.IsIndeterminate = true;
        UpdateProgressText.Visibility = Visibility.Visible;
        UpdateProgressText.Text = "Conectando con GitHub…";
        PostUpdateState("checking", "Buscando la última versión…", null, true);

        var progress = new Progress<UpdateProgress>(ApplyUpdateProgress);

        try
        {
            var prepared = await _updates.CheckAndPrepareAsync(progress);
            if (prepared is null)
            {
                UpdateTitle.Text = "Phomemo Studio está al día";
                UpdateText.Text = $"Ya tenés instalada la última versión ({UpdateService.CurrentVersion}).";
                UpdateProgressBar.IsIndeterminate = false;
                UpdateProgressBar.Value = 100;
                UpdateProgressText.Text = "100% · sin actualizaciones pendientes";
                UpdateStatusText.Text = $"Versión {UpdateService.CurrentVersion} · al día";
                PostUpdateState("current", $"Ya tenés la última versión ({UpdateService.CurrentVersion}).", 100, false);

                if (!notifyIfCurrent)
                {
                    await Task.Delay(1800);
                    UpdateBanner.Visibility = Visibility.Collapsed;
                }
                return;
            }

            _preparedUpdate = prepared;
            UpdateTitle.Text = $"Phomemo Studio {prepared.Version} listo";
            UpdateText.Text = "Descarga terminada y verificada con SHA-256.";
            UpdateProgressBar.Visibility = Visibility.Visible;
            UpdateProgressBar.IsIndeterminate = false;
            UpdateProgressBar.Value = 100;
            UpdateProgressText.Visibility = Visibility.Visible;
            UpdateProgressText.Text = "100% · descarga verificada";
            UpdateBanner.Visibility = Visibility.Visible;
            UpdateStatusText.Text = $"Actualización {prepared.Version} verificada";
            PostUpdateState("ready", $"Phomemo Studio {prepared.Version} listo para instalar", 100, true);

            if (installAutomatically)
                await BeginInstallAsync();
        }
        catch (Exception ex)
        {
            _updateInstallStarted = false;
            UpdateProgressBar.IsIndeterminate = false;
            UpdateProgressBar.Visibility = Visibility.Collapsed;
            UpdateProgressText.Visibility = Visibility.Visible;
            UpdateProgressText.Text = "Error";
            UpdateStatusText.Text = "No se pudo completar la actualización";
            UpdateTitle.Text = "Error al actualizar";
            UpdateText.Text = ex.GetBaseException().Message;
            UpdateBanner.Visibility = Visibility.Visible;
            PostUpdateState("error", ex.GetBaseException().Message, null, false);

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
            case "current":
                UpdateTitle.Text = "Phomemo Studio está al día";
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

        PostUpdateState(progress.Stage, progress.Message, progress.Percent, true);
    }

    private async Task BeginInstallAsync()
    {
        if (_preparedUpdate is null)
            throw new InvalidOperationException("Todavía no hay una actualización descargada.");

        _updateInstallStarted = true;
        SearchUpdateButton.IsEnabled = false;
        SearchUpdateButton.Content = "Instalando…";
        UpdateTitle.Text = $"Instalando Phomemo Studio {_preparedUpdate.Version}";
        UpdateText.Text = "El instalador va a tomar el control. Vas a ver su progreso; después la app se cerrará y volverá a abrirse sola.";
        UpdateStatusText.Text = $"Instalando {_preparedUpdate.Version}…";
        UpdateProgressBar.Visibility = Visibility.Visible;
        UpdateProgressBar.IsIndeterminate = true;
        UpdateProgressText.Visibility = Visibility.Visible;
        UpdateProgressText.Text = "Iniciando instalador…";
        PostUpdateState("installing", $"Instalando {_preparedUpdate.Version}…", null, true);

        await Task.Delay(500);
        _updates.InstallPreparedUpdate();

        // Le damos tiempo a Inno Setup a crear su ventana de progreso y luego
        // cerramos esta instancia. El instalador relanza la app al finalizar.
        await Task.Delay(900);
        Application.Current.Shutdown();
    }

    private async void SearchUpdates_Click(object sender, RoutedEventArgs e)
    {
        // Flujo completo: buscar -> descargar -> verificar -> instalar -> cerrar -> reabrir.
        await CheckForUpdatesAsync(installAutomatically: true, notifyIfCurrent: true);
    }

    private void PostUpdateState(string stage, string message, double? percent, bool busy)
    {
        try
        {
            if (Web?.CoreWebView2 is null)
                return;

            var json = JsonSerializer.Serialize(new
            {
                type = "updateState",
                stage,
                message,
                percent,
                busy
            });
            Web.CoreWebView2.PostWebMessageAsJson(json);
        }
        catch
        {
            // El estado visual web es auxiliar; nunca debe romper el actualizador nativo.
        }
    }

    private async void WebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
    {
        try
        {
            using var doc = JsonDocument.Parse(e.WebMessageAsJson);
            if (!doc.RootElement.TryGetProperty("type", out var typeElement))
                return;

            var type = typeElement.GetString();
            switch (type)
            {
                case "checkUpdates":
                    await CheckForUpdatesAsync(installAutomatically: true, notifyIfCurrent: true);
                    break;
                case "closeApp":
                    SystemCommands.CloseWindow(this);
                    break;
                case "minimizeApp":
                    SystemCommands.MinimizeWindow(this);
                    break;
                case "maximizeApp":
                    MaximizeRestoreWindow_Click(this, new RoutedEventArgs());
                    break;
            }
        }
        catch
        {
            // Un mensaje web inválido no debe afectar la ventana principal.
        }
    }
}
