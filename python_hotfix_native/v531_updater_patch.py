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
        installer = Path(path).resolve()
        if not installer.exists():
            raise RuntimeError(f"No se encontró el instalador descargado: {installer}")

        current_pid = os.getpid()
        running_exe = Path(sys.executable).resolve()
        installed_dir = running_exe.parent
        bundled_helper = installed_dir / "PhomemoStudioUpdater.exe"

        if not bundled_helper.exists():
            raise RuntimeError(
                "Falta PhomemoStudioUpdater.exe junto a la aplicación. "
                "Instalá esta versión manualmente una vez y las siguientes podrán actualizarse solas."
            )

        helper_copy = Path(tempfile.gettempdir()) / f"PhomemoStudioUpdater-{current_pid}.exe"
        try:
            import shutil
            shutil.copy2(bundled_helper, helper_copy)
        except Exception as exc:
            raise RuntimeError(f"No pude preparar el actualizador auxiliar: {exc}") from exc

        log_root = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "PhomemoStudio"
        log_root.mkdir(parents=True, exist_ok=True)
        log_path = log_root / "update.log"

        flags = (
            getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
            | getattr(subprocess,"DETACHED_PROCESS",0)
            | getattr(subprocess,"CREATE_NO_WINDOW",0)
        )
        subprocess.Popen(
            [
                str(helper_copy),
                "--installer", str(installer),
                "--pid", str(current_pid),
                "--app", str(running_exe),
                "--log", str(log_path),
            ],
            creationflags=flags,
            close_fds=True,
            cwd=tempfile.gettempdir(),
        )

        # Quit through the normal Qt path first; the helper waits for this exact
        # PID and only force-closes it if a worker thread prevents shutdown.
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
print("Applied standalone EXE updater handoff/install/relaunch")
