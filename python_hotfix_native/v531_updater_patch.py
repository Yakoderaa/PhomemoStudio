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
        window.statusBar().showMessage("Falló la descarga de la actualización",6000)
        QMessageBox.warning(window,"Actualizaciones",str(error))
        return

    window.statusBar().showMessage("Actualización descargada. Cerrando, instalando y reiniciando…")
    try:
        installer = str(Path(path).resolve())
        current_pid = os.getpid()

        running_exe = Path(sys.executable).resolve()
        fallback_exe = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "PhomemoStudio" / "PhomemoStudio.exe"
        candidates = []
        if running_exe.name.lower() == "phomemostudio.exe":
            candidates.append(running_exe)
        if fallback_exe not in candidates:
            candidates.append(fallback_exe)

        log_root = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "PhomemoStudio"
        log_root.mkdir(parents=True, exist_ok=True)
        log_path = log_root / "update.log"
        helper_path = Path(tempfile.gettempdir()) / f"PhomemoStudio-update-{current_pid}.ps1"

        def psq(value):
            return str(value).replace("'", "''")

        candidate_literal = "@(" + ",".join("'" + psq(p) + "'" for p in candidates) + ")"
        helper = f"$ErrorActionPreference = 'Stop'\\n"
        helper += f"$installer = '{psq(installer)}'\\n"
        helper += f"$log = '{psq(log_path)}'\\n"
        helper += f"$oldPid = {current_pid}\\n"
        helper += f"$appCandidates = {candidate_literal}\\n"
        helper += r'''function Log([string]$m) {
    Add-Content -LiteralPath $log -Value ("$(Get-Date -Format o)  $m") -Encoding UTF8
}
try {
    Set-Content -LiteralPath $log -Value ("$(Get-Date -Format o)  updater started") -Encoding UTF8
    Log ("installer: " + $installer)
    Log ("old pid: " + $oldPid)

    # Give the GUI a chance to close cleanly. If a worker/thread keeps it alive,
    # terminate only the old Phomemo Studio process so the update cannot stall.
    for ($i = 0; $i -lt 48; $i++) {
        if (-not (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) {
        Log "main process still alive after graceful wait; forcing old process to stop"
        Stop-Process -Id $oldPid -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 750
    }
    if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) {
        throw "Phomemo Studio no pudo cerrarse para instalar la actualización."
    }
    Log "main process exited"

    if (-not (Test-Path -LiteralPath $installer)) {
        throw "No se encontró el instalador descargado: $installer"
    }

    $args = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CLOSEAPPLICATIONS','/NORESTARTAPPLICATIONS','/SP-')
    Log "starting installer"
    $p = Start-Process -FilePath $installer -ArgumentList $args -Wait -PassThru
    Log ("installer exit code: " + $p.ExitCode)
    if ($p.ExitCode -ne 0) {
        throw "El instalador terminó con código $($p.ExitCode)."
    }

    $app = $null
    for ($i = 0; $i -lt 80; $i++) {
        foreach ($candidate in $appCandidates) {
            if (Test-Path -LiteralPath $candidate) {
                $app = $candidate
                break
            }
        }
        if ($app) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $app) {
        throw "La instalación terminó pero no se encontró PhomemoStudio.exe."
    }

    # The installer itself also relaunches the app in silent mode. Wait briefly
    # and use this as a fallback only if it did not start it.
    Start-Sleep -Milliseconds 1200
    $running = Get-Process -Name "PhomemoStudio" -ErrorAction SilentlyContinue
    if (-not $running) {
        Log ("installer did not relaunch app; fallback launch: " + $app)
        Start-Process -FilePath $app
    } else {
        Log "app already relaunched by installer"
    }
    Log "done"
} catch {
    try { Log ("ERROR: " + $_.Exception.ToString()) } catch {}
    try {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "La actualización no pudo completarse. Detalle guardado en:`n$log`n`n$($_.Exception.Message)",
            "Phomemo Studio - Actualización"
        ) | Out-Null
    } catch {}
}
'''
        helper_path.write_text(helper, encoding="utf-8-sig")
        flags = (
            getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
            | getattr(subprocess,"DETACHED_PROCESS",0)
            | getattr(subprocess,"CREATE_NO_WINDOW",0)
        )
        subprocess.Popen(
            [
                "powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden", "-File", str(helper_path)
            ],
            creationflags=flags,
            close_fds=True,
            cwd=tempfile.gettempdir()
        )
        QApplication.instance().quit()
    except Exception as exc:
        QMessageBox.warning(
            window,
            "Actualizaciones",
            f"Se descargó la actualización, pero no pude iniciar el actualizador:\\n{exc}"
        )
"""
if old not in s:
    raise SystemExit("Updater target block not found")
s = s.replace(old, new)
studio.write_text(s, encoding="utf-8")
print("Applied robust updater V5.7 handoff/install/relaunch")
