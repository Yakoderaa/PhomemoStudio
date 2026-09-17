from __future__ import annotations

import hashlib, json, os, re, subprocess, tempfile, urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO = "Yakoderaa/PhomemoStudio"
API = f"https://api.github.com/repos/{REPO}/releases/latest"

@dataclass
class ReleaseInfo:
    version: str
    installer_url: str
    hash_url: str
    notes: str = ""


def parse_version(v: str) -> tuple[int,...]:
    nums = re.findall(r"\d+", v)
    return tuple(int(x) for x in nums[:4])


def get_latest(timeout=15) -> ReleaseInfo:
    req=urllib.request.Request(API+f"?t={os.urandom(4).hex()}",headers={"User-Agent":"PhomemoStudio/4.2","Cache-Control":"no-cache","Pragma":"no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data=json.load(r)
    installer=hash_url=None
    for a in data.get("assets",[]):
        if a.get("name")=="PhomemoStudioSetup.exe": installer=a.get("browser_download_url")
        elif a.get("name")=="PhomemoStudioSetup.exe.sha256": hash_url=a.get("browser_download_url")
    if not installer or not hash_url:
        raise RuntimeError("La release más reciente no contiene el instalador y su SHA-256.")
    return ReleaseInfo(data["tag_name"].lstrip("vV"),installer,hash_url,data.get("body") or "")


def download_verified(info: ReleaseInfo, progress=None) -> Path:
    hash_req=urllib.request.Request(info.hash_url,headers={"User-Agent":"PhomemoStudio/4.2","Cache-Control":"no-cache"})
    with urllib.request.urlopen(hash_req,timeout=20) as r:
        expected=r.read().decode("utf-8").strip().split()[0].lower()
    root=Path(os.getenv("LOCALAPPDATA") or tempfile.gettempdir())/"PhomemoStudio"/"Updates"/info.version
    root.mkdir(parents=True,exist_ok=True)
    final=root/"PhomemoStudioSetup.exe"; part=root/"PhomemoStudioSetup.exe.part"
    part.unlink(missing_ok=True)
    req=urllib.request.Request(info.installer_url,headers={"User-Agent":"PhomemoStudio/4.2","Cache-Control":"no-cache"})
    with urllib.request.urlopen(req,timeout=90) as r, open(part,"wb") as f:
        total=int(r.headers.get("Content-Length") or 0); done=0
        while True:
            chunk=r.read(256*1024)
            if not chunk: break
            f.write(chunk); done += len(chunk)
            if progress: progress(done,total)
    actual=hashlib.sha256(part.read_bytes()).hexdigest().lower()
    if actual != expected:
        part.unlink(missing_ok=True)
        raise RuntimeError("La descarga terminó, pero el SHA-256 no coincide con GitHub. No se instalará nada.")
    part.replace(final)
    return final


def launch_installer(path: Path):
    """Start a delayed, silent installer so the current EXE can close before replacement."""
    path=Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
    if os.name=="nt":
        escaped=str(path).replace("'","''")
        script=(
            "Start-Sleep -Milliseconds 900; "
            f"Start-Process -FilePath '{escaped}' -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/CLOSEAPPLICATIONS','/NORESTART','/SP-'"
        )
        subprocess.Popen(["powershell.exe","-NoProfile","-NonInteractive","-WindowStyle","Hidden","-Command",script],close_fds=True,creationflags=flags)
    else:
        subprocess.Popen([str(path)],close_fds=True)
