from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"4.1.6 patch {label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


bridge_path = Path("native_bridge/PhomemoBleBridge/Program.cs")
bridge = bridge_path.read_text(encoding="utf-8")

# Add a request flag that distinguishes a user-initiated connection (discovery allowed)
# from automatic/background reconnects (must stay silent and never launch discovery).
bridge = replace_once(
    bridge,
    '''internal sealed class BridgeRequest
{
    public string? Command { get; set; }
    public string? PreferredAddress { get; set; }
    public string[]? Packets { get; set; }
}
''',
    '''internal sealed class BridgeRequest
{
    public string? Command { get; set; }
    public string? PreferredAddress { get; set; }
    public string[]? Packets { get; set; }
    public bool AllowDiscovery { get; set; } = true;
}
''',
    "request allowDiscovery",
)

bridge = replace_once(
    bridge,
    '''                    "connect" => await bridge.ConnectAsync(req.PreferredAddress),
                    "maintain" => await bridge.MaintainAsync(req.PreferredAddress),
''',
    '''                    "connect" => await bridge.ConnectAsync(req.PreferredAddress, req.AllowDiscovery),
                    "maintain" => await bridge.MaintainAsync(req.PreferredAddress),
''',
    "connect command flag",
)

bridge = replace_once(
    bridge,
    '''    public async Task<BridgeResponse> ConnectAsync(string? preferredAddress)
    {
''',
    '''    public async Task<BridgeResponse> ConnectAsync(string? preferredAddress, bool allowDiscovery = true)
    {
''',
    "ConnectAsync signature",
)

# After trying the saved Bluetooth address, background reconnect must stop there.
# This prevents DeviceInformation enumeration and active BLE advertisement scanning,
# the two discovery paths that can provoke Windows' "Agregar un dispositivo" banner.
bridge = replace_once(
    bridge,
    '''        if (hasSaved)
        {
            _progress("Probando la D30 guardada…");
            try
            {
                await ConnectToAddressAsync(saved, "D30");
                return Status("D30 reconectada directamente con Windows");
            }
            catch
            {
                Cleanup();
            }
        }

        _progress("Buscando una D30 que Windows ya conozca…");
''',
    '''        if (hasSaved)
        {
            _progress("Probando la D30 guardada…");
            try
            {
                await ConnectToAddressAsync(saved, "D30");
                return Status("D30 reconectada directamente con Windows");
            }
            catch
            {
                Cleanup();
            }
        }

        if (!allowDiscovery)
            return BridgeResponse.Fail("La D30 no respondió por su dirección guardada. La reconexión automática seguirá intentando en segundo plano sin abrir el asistente de Windows.");

        _progress("Buscando una D30 que Windows ya conozca…");
''',
    "silent saved-address reconnect",
)

bridge = replace_once(
    bridge,
    '''            var reconnect = await ConnectAsync(preferredAddress);
''',
    '''            var reconnect = await ConnectAsync(preferredAddress, false);
''',
    "maintenance no discovery",
)

bridge_path.write_text(bridge, encoding="utf-8")

# Python wrapper: every automatic/preflight reconnect explicitly disables discovery.
# The manual Connect button still uses the default allowDiscovery=true.
printer_path = Path("python_hotfix_native/printer.py")
printer = printer_path.read_text(encoding="utf-8")
printer = printer.replace(
    '{"command": "maintain", "preferredAddress": addr}',
    '{"command": "maintain", "preferredAddress": addr, "allowDiscovery": False}',
)
printer = printer.replace(
    '{"command": "connect", "preferredAddress": addr}',
    '{"command": "connect", "preferredAddress": addr, "allowDiscovery": False}',
)
printer = printer.replace(
    '{"command": "connect", "preferredAddress": self._last_address}',
    '{"command": "connect", "preferredAddress": self._last_address, "allowDiscovery": False}',
)

# Restore discovery for the one explicitly user-initiated connect path.
old_manual = '''        return self._executor.submit(self._request, {"command": "connect", "preferredAddress": addr, "allowDiscovery": False}, timeout)'''
new_manual = '''        return self._executor.submit(self._request, {"command": "connect", "preferredAddress": addr, "allowDiscovery": True}, timeout)'''
if old_manual not in printer:
    raise SystemExit("4.1.6 patch manual connect: expected transformed connect call")
printer = printer.replace(old_manual, new_manual, 1)

printer_path.write_text(printer, encoding="utf-8")
print("Applied Phomemo Studio 4.1.6 silent auto-reconnect patch")
