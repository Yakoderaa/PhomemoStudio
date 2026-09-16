using System.IO;
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
            _updates.Dispose();
            _bluetooth.Dispose();
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
            Web.Source = new Uri("https://app.phomemostudio.local/index.html");

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
        if (_isCheckingUpdates || _updateInstallStarted)
        {
            if (notifyIfCurrent && _isCheckingUpdates)
                MessageBox.Show(this, "Ya estoy buscando actualizaciones.", "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        _isCheckingUpdates = true;
        SearchUpdateButton.IsEnabled = false;
        SearchUpdateButton.Content = "Buscando…";

        try
        {
            var prepared = await _updates.CheckAndPrepareAsync();
            if (prepared is null)
            {
                if (notifyIfCurrent)
                    MessageBox.Show(this, $"Ya tenés la última versión ({UpdateService.CurrentVersion}).", "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            _preparedUpdate = prepared;
            UpdateTitle.Text = $"Phomemo Studio {prepared.Version} está listo";
            UpdateText.Text = "La actualización se descargó automáticamente y pasó la verificación SHA-256.";
            UpdateBanner.Visibility = Visibility.Visible;

            if (installAutomatically)
            {
                _updateInstallStarted = true;
                UpdateText.Text = "Actualización verificada. Phomemo Studio se reiniciará para instalarla automáticamente.";
                InstallUpdateButton.IsEnabled = false;
                InstallUpdateButton.Content = "Actualizando…";
                SearchUpdateButton.Content = "Actualizando…";
                await Task.Delay(300);
                _updates.InstallPreparedUpdate();
            }
        }
        catch (Exception ex)
        {
            if (notifyIfCurrent)
            {
                MessageBox.Show(this,
                    "No pude buscar o instalar actualizaciones.\n\n" + ex.Message,
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

    private async void SearchUpdates_Click(object sender, RoutedEventArgs e)
    {
        await CheckForUpdatesAsync(installAutomatically: true, notifyIfCurrent: true);
    }

    private void InstallUpdate_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (_preparedUpdate is null)
            {
                MessageBox.Show(this, "Todavía no hay una actualización descargada.", "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            _updateInstallStarted = true;
            InstallUpdateButton.IsEnabled = false;
            InstallUpdateButton.Content = "Actualizando…";
            SearchUpdateButton.IsEnabled = false;
            SearchUpdateButton.Content = "Actualizando…";
            _updates.InstallPreparedUpdate();
        }
        catch (Exception ex)
        {
            _updateInstallStarted = false;
            InstallUpdateButton.IsEnabled = true;
            InstallUpdateButton.Content = "Actualizar y reiniciar";
            SearchUpdateButton.IsEnabled = true;
            SearchUpdateButton.Content = "Buscar actualizaciones";
            MessageBox.Show(this, "No pude iniciar la actualización.\n\n" + ex.Message, "Phomemo Studio", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }
}
