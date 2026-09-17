from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
import json
import math
import os
import tempfile
from typing import Any

DPI = 203
DOTS_PER_MM = DPI / 25.4
SUPPORTED_SIZES = [(40,12),(30,12),(22,12),(12,12),(30,14),(40,15),(30,15)]


def mm_to_dots(mm: float) -> int:
    return max(1, int(round(mm * DOTS_PER_MM)))


def label_pixels(width_mm: float, height_mm: float) -> tuple[int,int]:
    return mm_to_dots(width_mm), mm_to_dots(height_mm)


@dataclass
class Element:
    kind: str
    x: float
    y: float
    w: float
    h: float
    text: str = ""
    font: str = "Arial"
    font_size: int = 16
    bold: bool = False
    stroke: int = 2
    path: str = ""
    image_mode: str = "lineart"
    lock_aspect: bool = True
    shape: str = "rect"
    fill: bool = False
    rotation: float = 0.0
    opacity: float = 1.0

    def clamp(self, width: float, height: float) -> None:
        self.w = max(2, min(self.w, width))
        self.h = max(2, min(self.h, height))
        self.x = min(max(0, self.x), max(0, width-self.w))
        self.y = min(max(0, self.y), max(0, height-self.h))


@dataclass
class Template:
    id: str
    name: str
    group: str = "General"
    width_mm: int = 40
    height_mm: int = 12
    elements: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AppState:
    groups: list[str] = field(default_factory=lambda:["General"])
    templates: list[Template] = field(default_factory=list)
    roll_name: str = "12×40 · 80 etiquetas"
    roll_total: int = 80
    roll_remaining: int = 80
    density: int = 6
    continuous: bool = False
    feed_dots: int = 0
    auto_reconnect: bool = True
    auto_power_connect: bool = True
    auto_calibrate_new_roll: bool = False
    last_template_id: str | None = None
    last_device_address: str | None = None


class StateStore:
    def __init__(self, path: Path | None = None):
        if path is None:
            root = Path(os.getenv("LOCALAPPDATA") or Path.home()/".local"/"share") / "PhomemoStudio"
            path = root / "state-v4.json"
        self.path = Path(path)

    def load(self) -> AppState:
        if not self.path.exists():
            return AppState()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            templates = [Template(**x) for x in raw.pop("templates", [])]
            allowed = {f.name for f in AppState.__dataclass_fields__.values()}
            raw = {k:v for k,v in raw.items() if k in allowed}
            state = AppState(**raw)
            state.templates = templates
            state.roll_total = max(1, int(state.roll_total))
            state.roll_remaining = max(0, min(int(state.roll_remaining), state.roll_total))
            state.density = max(1, min(8, int(state.density)))
            state.feed_dots = max(0, min(255, int(state.feed_dots)))
            if "General" not in state.groups:
                state.groups.insert(0, "General")
            return state
        except Exception:
            return AppState()

    def save(self, state: AppState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(state)
        fd, tmp = tempfile.mkstemp(prefix="state-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush(); os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


def make_print_packet(bitmap_bytes: bytes, width_px: int, height_px: int, density: int = 6,
                      continuous: bool = False, feed_dots: int = 0) -> list[bytes]:
    density = max(1, min(8, int(density)))
    feed_dots = max(0, min(255, int(feed_dots)))
    width_bytes = math.ceil(width_px / 8)
    expected = width_bytes * height_px
    if len(bitmap_bytes) != expected:
        raise ValueError(f"Raster size mismatch: got {len(bitmap_bytes)}, expected {expected}")
    packets = [
        bytes([0x1B,0x37,0x07,density,0x02]),
        bytes([0x1F,0x11,0x0B if continuous else 0x0A]),
        bytes([0x1B,0x40,0x1D,0x76,0x30,0x00,width_bytes & 0xff,(width_bytes>>8)&0xff,height_px&0xff,(height_px>>8)&0xff]),
        bitmap_bytes,
    ]
    if feed_dots:
        packets.append(bytes([0x1B,0x4A,feed_dots]))
    packets.append(bytes([0x1B,0x64,0x00]))
    return packets


def pack_mono_pixels(pixels: list[list[bool]]) -> tuple[bytes,int,int]:
    if not pixels or not pixels[0]:
        raise ValueError("empty pixels")
    h = len(pixels); w = len(pixels[0])
    if any(len(row) != w for row in pixels):
        raise ValueError("ragged pixels")
    wb = math.ceil(w/8)
    out = bytearray(wb*h)
    for y,row in enumerate(pixels):
        for x,black in enumerate(row):
            if black:
                out[y*wb + x//8] |= (0x80 >> (x%8))
    return bytes(out), w, h
