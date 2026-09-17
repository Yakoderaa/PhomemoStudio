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
    req=urllib.request.Request(API+f"?t={os.urandom(4).hex()}",headers={"User-Agent":"PhomemoStudio/4","Cache-Control":"no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data=json.load(r)
    installer=hash_url=None
    for a in data.get("assets",[]):
        if a.get("name")=="PhomemoStudioSetup.exe": installer=a.get("browser_download_url")
        if a.get("name")=="PhomemoStudioSetup.exe.sha256": hash_url=a.get("browser_download_url")
    if not installer or not hash_url: raise RuntimeError("La release no contiene instalador y SHA-256.")
    return ReleaseInfo(data["tag_name"].lstrip("vV"),installer,hash_url,data.get("body") or "")

def download_verified(info: ReleaseInfo, progress=None) -> Path:
    with urllib.request.urlopen(info.hash_url,timeout=15) as r:
        expected=r.read().decode("utf-8").strip().split()[0].lower()
    root=Path(os.getenv("LOCALAPPDATA") or tempfile.gettempdir())/"PhomemoStudio"/"Updates"/info.version
    root.mkdir(parents=True,exist_ok=True); final=root/"PhomemoStudioSetup.exe"; part=root/"PhomemoStudioSetup.exe.part"
    req=urllib.request.Request(info.installer_url,headers={"User-Agent":"PhomemoStudio/4"})
    with urllib.request.urlopen(req,timeout=60) as r, open(part,"wb") as f:
        total=int(r.headers.get("Content-Length") or 0); done=0
        while True:
            chunk=r.read(128*1024)
            if not chunk: break
            f.write(chunk); done += len(chunk)
            if progress: progress(done,total)
    actual=hashlib.sha256(part.read_bytes()).hexdigest().lower()
    if actual != expected:
        part.unlink(missing_ok=True); raise RuntimeError("El SHA-256 descargado no coincide con GitHub.")
    part.replace(final); return final

def launch_installer(path: Path):
    subprocess.Popen([str(path),"/SILENT","/SUPPRESSMSGBOXES","/CLOSEAPPLICATIONS","/RESTARTAPPLICATIONS"],close_fds=True)
