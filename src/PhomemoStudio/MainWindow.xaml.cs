using System.IO;
using System.Windows;
using Microsoft.Web.WebView2.Core;
using PhomemoStudio.Services;

namespace PhomemoStudio;

public partial class MainWindow : Window
{
    private readonly D30BluetoothService _bluetooth = new();
    private NativeBridge? _bridge;
    private readonly UpdateService _updates = new();

    public MainWindow()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Closed += (_, _) => _bluetooth.Dispose();
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

            _ = Task.Run(async () =>
            {
                await Task.Delay(3500);
                await Dispatcher.InvokeAsync(async () => await _updates.CheckAndOfferUpdateAsync(this, true));
            });
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
}
