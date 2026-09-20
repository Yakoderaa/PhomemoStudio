from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path


def log_line(path: Path, message: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}\n")


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


def kill_pid(pid: int):
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    installer = Path(args.installer).resolve()
    app_path = Path(args.app).resolve()
    log = Path(args.log).resolve()

    try:
        log.write_text("", encoding="utf-8")
    except Exception:
        pass

    log_line(log, f"helper started pid={os.getpid()}")
    log_line(log, f"old app pid={args.pid}")
    log_line(log, f"installer={installer}")
    log_line(log, f"app={app_path}")

    # Give the app up to 12 seconds to close normally.
    deadline = time.time() + 12.0
    while time.time() < deadline and pid_exists(args.pid):
        time.sleep(0.25)

    if pid_exists(args.pid):
        log_line(log, "old app still alive; terminating only that process tree")
        kill_pid(args.pid)
        time.sleep(1.0)

    if pid_exists(args.pid):
        raise RuntimeError("Phomemo Studio no pudo cerrarse para instalar la actualización.")

    if not installer.exists():
        raise RuntimeError(f"No se encontró el instalador descargado: {installer}")

    cmd = [
        str(installer),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CLOSEAPPLICATIONS",
        "/NORESTARTAPPLICATIONS",
        "/SP-",
    ]
    log_line(log, "starting installer")
    proc = subprocess.run(
        cmd,
        cwd=str(installer.parent),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    log_line(log, f"installer exit={proc.returncode}")
    if proc.returncode not in (0,):
        raise RuntimeError(f"El instalador terminó con código {proc.returncode}.")

    candidates = [
        app_path,
        Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "PhomemoStudio" / "PhomemoStudio.exe",
    ]
    installed = None
    for _ in range(60):
        for candidate in candidates:
            if candidate.exists():
                installed = candidate
                break
        if installed is not None:
            break
        time.sleep(0.25)

    if installed is None:
        raise RuntimeError("La instalación terminó, pero no se encontró PhomemoStudio.exe.")

    # Give Inno's optional Run section a chance, then use this helper as a guaranteed fallback.
    time.sleep(1.5)
    running = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq PhomemoStudio.exe", "/NH"],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    if "PhomemoStudio.exe" not in (running.stdout or ""):
        log_line(log, f"relaunch fallback: {installed}")
        subprocess.Popen(
            [str(installed)],
            cwd=str(installed.parent),
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            close_fds=True,
        )
    else:
        log_line(log, "app already relaunched by installer")

    log_line(log, "update completed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        try:
            log_arg = None
            for i, arg in enumerate(sys.argv):
                if arg == "--log" and i + 1 < len(sys.argv):
                    log_arg = Path(sys.argv[i + 1])
                    break
            if log_arg:
                log_line(log_arg, f"ERROR: {exc!r}")
        except Exception:
            pass
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"La actualización no pudo completarse.\n\n{exc}",
                "Phomemo Studio - Actualización",
                0x10,
            )
        except Exception:
            pass
        raise
