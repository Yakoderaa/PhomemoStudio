import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PHOMEMO_STUDIO_DATA_DIR"] = tempfile.mkdtemp(prefix="phomemo-v606-")

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from phomemo_studio.ui import MainWindow
from phomemo_studio.studio_pro import _find_canvas
from phomemo_studio.v5101_exact_print import SUPERSAMPLE, _label_source_rect
from phomemo_studio.v56_text_lines_rotation import ROLE_KIND, insert_line
from phomemo_studio.v603_print_queue_concentration import (
    STIPPLE_THRESHOLD,
    _intentional_stipple_mask,
)
from phomemo_studio.v604_alignment_multiselect import (
    SAFE_MARGIN_MM,
    SAFE_MARGIN_PX,
    _safe_label_rect,
)
from phomemo_studio.v605_canvas_workspace import SAFE_ZONE_ROLE, _ensure_workspace
from phomemo_studio.v606_quality_safearea import _clean_header_status

w = MainWindow()
QApplication.processEvents()
_ensure_workspace(w, recenter=False)
QApplication.processEvents()

view = _find_canvas(w)
scene = view.scene()

# Rendering quality: 4x vector supersampling before returning to physical 203 dpi.
assert SUPERSAMPLE == 4

# The editor exposes a non-printing 1 mm safe guide.
assert abs(SAFE_MARGIN_MM - 1.0) < 0.001
assert 7.0 < SAFE_MARGIN_PX < 9.0
safe_guides = [item for item in scene.items() if item.data(SAFE_ZONE_ROLE)]
assert len(safe_guides) == 1, len(safe_guides)
assert safe_guides[0].data(1098)

# Alignment card contains center, four edges and all four corners.
buttons = getattr(w, "_v604_alignment_buttons", {})
expected_modes = {
    "center", "top", "bottom", "left", "right",
    "top-left", "top-right", "bottom-left", "bottom-right",
}
assert set(buttons) == expected_modes, set(buttons)

label = _label_source_rect(scene)
safe = _safe_label_rect(label)
assert abs((safe.left() - label.left()) - SAFE_MARGIN_PX) < 0.01
assert abs((label.right() - safe.right()) - SAFE_MARGIN_PX) < 0.01
assert abs((safe.top() - label.top()) - SAFE_MARGIN_PX) < 0.01
assert abs((label.bottom() - safe.bottom()) - SAFE_MARGIN_PX) < 0.01

# Rounded "Marco etiqueta" is one continuous path that follows the label's
# curved corners inside the same safe area.
frame = insert_line(w, "Marco etiqueta", "label-frame")
assert frame is not None
assert frame.data(ROLE_KIND) == "studio-frame"
mapped = frame.sceneTransform().mapRect(frame.path().boundingRect())
assert abs(mapped.left() - safe.left()) < 0.05, (mapped, safe)
assert abs(mapped.right() - safe.right()) < 0.05, (mapped, safe)
assert abs(mapped.top() - safe.top()) < 0.05, (mapped, safe)
assert abs(mapped.bottom() - safe.bottom()) < 0.05, (mapped, safe)
assert frame.pen().capStyle() == Qt.RoundCap
assert frame.pen().joinStyle() == Qt.RoundJoin
local = frame.path().boundingRect()
assert frame.path().contains(local.center())
assert not frame.path().contains(local.topLeft())

# Intentional stippling: small isolated gray/dark components survive even when
# they are not pure black. A continuous gray patch must NOT be classified as stipple.
probe = Image.new("L", (120, 60), 255)
draw = ImageDraw.Draw(probe)
dots = [(15, 15), (30, 18), (45, 14), (60, 20), (75, 16)]
for x, y in dots:
    draw.ellipse((x-1, y-1, x+1, y+1), fill=min(200, STIPPLE_THRESHOLD))
draw.rectangle((88, 10, 108, 30), fill=165)

mask = _intentional_stipple_mask(probe)
for x, y in dots:
    assert mask.getpixel((x, y)) != 0, (x, y)
assert mask.getpixel((98, 20)) == 0

# Missing battery/paper information no longer leaves an ugly dash in the header.
w.battery.setText("Batería —")
w.paper.setText("Papel —")
_clean_header_status(w)
assert w.battery.text() == "Batería"
assert w.paper.text() == "Papel"

# Real values remain untouched.
w.battery.setText("Batería 87%")
w.paper.setText("Papel OK")
_clean_header_status(w)
assert w.battery.text() == "Batería 87%"
assert w.paper.text() == "Papel OK"

timer = getattr(w, "_v606_header_clean_timer", None)
assert timer is not None and timer.isActive()

w.close()
print("V6.0.6 stipple preservation + rounded frame + safe corners + header cleanup smoke OK")
