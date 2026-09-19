from pathlib import Path

studio = Path("python_app/phomemo_studio/studio_pro.py")
s = studio.read_text(encoding="utf-8")
old = '''def _on_update_downloaded(window, path, error):
    window._studio_update_busy=False
    if error:
        window.statusBar().showMessage("Falló la descarga de la actualización",6000); QMessageBox.warning(window,"Actualizaciones",str(error)); return
    window.statusBar().showMessage("Actualización descargada. Cerrando para instalar…")
    try:
        flags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)|getattr(subprocess,"DETACHED_PROCESS",0)|getattr(subprocess,"CREATE_NO_WINDOW",0)
        cmd=f'timeout /t 2 /nobreak >nul & "{path}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /NORESTARTAPPLICATIONS'
        subprocess.Popen(["cmd.exe","/c",cmd],creationflags=flags,close_fds=True)
        QApplication.instance().quit()
    except Exception as exc: QMessageBox.warning(window,"Actualizaciones",f"Se descargó la actualización, pero no pude iniciar el instalador:\\n{exc}")
'''
new = r"""def _on_update_downloaded(window, path, error):
    window._studio_update_busy=False
    if error:
        window.statusBar().showMessage("Falló la descarga de la actualización",6000); QMessageBox.warning(window,"Actualizaciones",str(error)); return
    window.statusBar().showMessage("Actualización descargada. Instalando y reiniciando…")
    try:
        installer = str(Path(path).resolve())
        current_pid = os.getpid()
        install_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "PhomemoStudio"
        app_exe = install_dir / "PhomemoStudio.exe"
        log_path = Path(tempfile.gettempdir()) / "PhomemoStudio-update.log"
        helper_path = Path(tempfile.gettempdir()) / "PhomemoStudio-update.ps1"

        def psq(value):
            return str(value).replace("'", "''")

        helper = f'''$ErrorActionPreference = 'Stop'\n'''
        helper += f'''$installer = '{psq(installer)}'\n'''
        helper += f'''$app = '{psq(app_exe)}'\n'''
        helper += f'''$log = '{psq(log_path)}'\n'''
        helper += f'''$oldPid = {current_pid}\n'''
        helper += r'''function Log([string]$m) { Add-Content -LiteralPath $log -Value ("$(Get-Date -Format o)  $m") -Encoding UTF8 }
try {
    Set-Content -LiteralPath $log -Value ("$(Get-Date -Format o)  updater started") -Encoding UTF8
    for ($i = 0; $i -lt 120; $i++) {
        if (-not (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) { throw "Phomemo Studio no terminó a tiempo." }
    Log "main process exited"
    if (-not (Test-Path -LiteralPath $installer)) { throw "No se encontró el instalador descargado: $installer" }
    $args = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CLOSEAPPLICATIONS','/NORESTARTAPPLICATIONS')
    Log "starting installer"
    $p = Start-Process -FilePath $installer -ArgumentList $args -Wait -PassThru
    Log ("installer exit code: " + $p.ExitCode)
    if ($p.ExitCode -ne 0) { throw "El instalador terminó con código $($p.ExitCode)." }
    for ($i = 0; $i -lt 80; $i++) {
        if (Test-Path -LiteralPath $app) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not (Test-Path -LiteralPath $app)) { throw "La instalación terminó pero no apareció $app" }
    Log "relaunching app"
    Start-Process -FilePath $app
    Log "done"
} catch {
    try { Log ("ERROR: " + $_.Exception.ToString()) } catch {}
    try {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show("La actualización no pudo completarse. Detalle guardado en:`n$log`n`n$($_.Exception.Message)", "Phomemo Studio - Actualización") | Out-Null
    } catch {}
}
'''
        helper_path.write_text(helper, encoding="utf-8-sig")
        flags = getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0) | getattr(subprocess,"DETACHED_PROCESS",0) | getattr(subprocess,"CREATE_NO_WINDOW",0)
        subprocess.Popen([
            "powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-WindowStyle", "Hidden", "-File", str(helper_path)
        ], creationflags=flags, close_fds=True, cwd=tempfile.gettempdir())
        QApplication.instance().quit()
    except Exception as exc:
        QMessageBox.warning(window,"Actualizaciones",f"Se descargó la actualización, pero no pude iniciar el actualizador:\n{exc}")
"""
if old not in s:
    raise SystemExit("Updater target block not found")
s = s.replace(old, new)
studio.write_text(s, encoding="utf-8")
print("Applied V5.3.1 robust updater handoff/install/relaunch")
