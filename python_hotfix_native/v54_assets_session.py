from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, QRectF
from PySide6.QtGui import (
    QColor, QBrush, QFont, QImage, QImageReader, QPainterPath, QPen,
    QPixmap, QPolygonF
)
from PySide6.QtWidgets import (
    QAbstractButton, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFrame, QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem,
    QGraphicsPathItem, QGraphicsPixmapItem, QGraphicsPolygonItem,
    QGraphicsProxyWidget, QGraphicsRectItem, QGraphicsTextItem, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QTabWidget, QToolButton, QVBoxLayout, QWidget
)

try:
    from PySide6.QtSvg import QSvgRenderer
except Exception:
    QSvgRenderer = None

from .studio_pro import _find_canvas


ROLE_KIND = 1001
ROLE_ASSET = 1002
ROLE_NAME = 1003
ROLE_V54 = 1054


def _data_root() -> Path:
    override = os.environ.get("PHOMEMO_STUDIO_DATA_DIR", "").strip()
    if override:
        root = Path(override)
    else:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        root = Path(base) / "PhomemoStudio"
    root.mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(exist_ok=True)
    (root / "session_pixmaps").mkdir(exist_ok=True)
    return root


def _library_path() -> Path:
    return _data_root() / "library.json"


def _session_path() -> Path:
    return _data_root() / "autosave.json"


def _atomic_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _load_library() -> list[dict]:
    raw = _read_json(_library_path(), [])
    if not isinstance(raw, list):
        return []
    out = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path", ""))
        if not rel:
            continue
        if (_data_root() / rel).exists():
            out.append(entry)
    return out


def _save_library(entries: list[dict]) -> None:
    _atomic_json(_library_path(), entries)


def _asset_file(entry: dict) -> Path:
    return _data_root() / str(entry.get("path", ""))


def _svg_pixmap(path: Path, target: QSize | None = None) -> QPixmap:
    if QSvgRenderer is None:
        return QPixmap()
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return QPixmap()
    size = renderer.defaultSize()
    if not size.isValid() or size.width() <= 0 or size.height() <= 0:
        size = QSize(512, 512)
    max_side = 1200
    if max(size.width(), size.height()) > max_side:
        size.scale(max_side, max_side, Qt.KeepAspectRatio)
    if target is not None and target.isValid():
        size.scale(target, Qt.KeepAspectRatio)
    image = QImage(max(1, size.width()), max(1, size.height()), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    from PySide6.QtGui import QPainter
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(image)


def _load_pixmap(path: Path, target: QSize | None = None) -> QPixmap:
    if not path.exists():
        return QPixmap()
    if path.suffix.lower() == ".svg":
        return _svg_pixmap(path, target)
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    if target is not None and target.isValid():
        size = reader.size()
        if size.isValid():
            size.scale(target, Qt.KeepAspectRatio)
            reader.setScaledSize(size)
    image = reader.read()
    if not image.isNull():
        return QPixmap.fromImage(image)
    pm = QPixmap(str(path))
    if not pm.isNull() and target is not None:
        return pm.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pm


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _import_one(path: Path) -> tuple[dict | None, str | None]:
    try:
        if not path.is_file():
            return None, "El archivo no existe."
        allowed = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".svg"}
        ext = path.suffix.lower()
        if ext not in allowed:
            return None, f"Formato no compatible: {ext or 'sin extensión'}"
        digest = _hash_file(path)
        asset_id = digest[:24]
        dest = _data_root() / "assets" / f"{asset_id}{ext}"
        if not dest.exists():
            shutil.copy2(path, dest)
        pm = _load_pixmap(dest)
        if pm.isNull():
            return None, f"No se pudo renderizar {path.name}."
        entries = _load_library()
        for old in entries:
            if old.get("id") == asset_id:
                return old, None
        entry = {
            "id": asset_id,
            "name": path.name,
            "path": str(Path("assets") / dest.name).replace("\\", "/"),
            "kind": "svg" if ext == ".svg" else "image",
            "width": int(pm.width()),
            "height": int(pm.height()),
            "added_at": int(time.time()),
        }
        entries.insert(0, entry)
        _save_library(entries)
        return entry, None
    except Exception as exc:
        return None, str(exc)


def _find_entry(asset_id: str) -> dict | None:
    for entry in _load_library():
        if entry.get("id") == asset_id:
            return entry
    return None


def _insert_asset(window, entry: dict):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        QMessageBox.warning(window, "Imágenes", "No encontré el lienzo activo.")
        return None
    pm = _load_pixmap(_asset_file(entry))
    if pm.isNull():
        QMessageBox.warning(window, "Imágenes", f"No pude abrir {entry.get('name', 'la imagen')}.")
        return None

    item = QGraphicsPixmapItem(pm)
    item.setTransformationMode(Qt.SmoothTransformation)
    item.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
    item.setData(ROLE_KIND, "imported-image")
    item.setData(ROLE_ASSET, entry.get("id"))
    item.setData(ROLE_NAME, entry.get("name"))
    item.setData(ROLE_V54, True)

    max_w, max_h = 260.0, 190.0
    scale = min(1.0, max_w / max(1, pm.width()), max_h / max(1, pm.height()))
    item.setScale(scale)
    center = view.mapToScene(view.viewport().rect().center())
    br = item.boundingRect()
    item.setPos(center.x() - br.width() * scale / 2, center.y() - br.height() * scale / 2)
    view.scene().clearSelection()
    view.scene().addItem(item)
    item.setSelected(True)
    _schedule_save(window)
    return item


def _import_paths(window, paths, insert=True):
    imported = []
    errors = []
    for raw in paths:
        entry, error = _import_one(Path(raw))
        if entry is not None:
            imported.append(entry)
            if insert:
                _insert_asset(window, entry)
        elif error:
            errors.append(f"{Path(raw).name}: {error}")
    _refresh_library_ui(window)
    if imported:
        window.statusBar().showMessage(
            f"{len(imported)} imagen(es) importada(s) · guardadas en la biblioteca", 5000
        )
    if errors:
        QMessageBox.warning(window, "Imágenes", "No se pudieron importar:\n\n" + "\n".join(errors[:8]))
    return imported


def _choose_images(window):
    files, _ = QFileDialog.getOpenFileNames(
        window,
        "Importar imágenes",
        "",
        "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;PNG (*.png);;JPEG (*.jpg *.jpeg);;SVG (*.svg);;Todos los archivos (*.*)",
    )
    if files:
        _import_paths(window, files, insert=True)


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


def _thumbnail_button(window, entry: dict) -> QWidget:
    card = QFrame()
    card.setObjectName("v54AssetCard")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(7, 7, 7, 7)
    lay.setSpacing(5)

    button = QToolButton()
    button.setObjectName("v54AssetTile")
    button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    pm = _load_pixmap(_asset_file(entry), QSize(96, 72))
    if not pm.isNull():
        from PySide6.QtGui import QIcon
        button.setIcon(QIcon(pm))
    button.setIconSize(QSize(96, 72))
    name = str(entry.get("name", "Imagen"))
    short = name if len(name) <= 20 else name[:18] + "…"
    button.setText(short)
    button.setToolTip(name + "\nClic para insertar en el lienzo")
    button.setMinimumSize(116, 112)
    button.clicked.connect(lambda _=False, e=entry: _insert_asset(window, e))
    lay.addWidget(button)
    return card


def _refresh_library_ui(window):
    grid = getattr(window, "_v54_asset_grid", None)
    count = getattr(window, "_v54_asset_count", None)
    empty = getattr(window, "_v54_asset_empty", None)
    search = getattr(window, "_v54_asset_search", None)
    if grid is None:
        return
    _clear_layout(grid)
    entries = _load_library()
    query = (search.text() if search is not None else "").strip().casefold()
    if query:
        entries = [e for e in entries if query in str(e.get("name", "")).casefold()]
    if count is not None:
        count.setText(f"{len(entries)} recurso(s) importado(s)")
    if empty is not None:
        empty.setVisible(not entries)
    for i, entry in enumerate(entries):
        grid.addWidget(_thumbnail_button(window, entry), i // 2, i % 2)
    grid.setRowStretch((len(entries) + 1) // 2 + 1, 1)


def _build_library_tab(window) -> QWidget:
    tab = QWidget()
    outer = QVBoxLayout(tab)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(9)

    info = QLabel("Tus imágenes quedan guardadas acá aunque cierres la app o apagues la PC.")
    info.setWordWrap(True)
    info.setProperty("muted", True)
    outer.addWidget(info)

    row = QHBoxLayout()
    imp = QPushButton("Importar imágenes")
    imp.setObjectName("v54ImportImages")
    imp.setProperty("role", "primary")
    imp.clicked.connect(lambda: _choose_images(window))
    row.addWidget(imp, 1)
    outer.addLayout(row)

    search = QLineEdit()
    search.setObjectName("v54AssetSearch")
    search.setPlaceholderText("Buscar en imágenes importadas…")
    search.setClearButtonEnabled(False)
    outer.addWidget(search)
    window._v54_asset_search = search

    count = QLabel()
    count.setObjectName("v54AssetCount")
    count.setProperty("muted", True)
    outer.addWidget(count)
    window._v54_asset_count = count

    scroll = QScrollArea()
    scroll.setObjectName("v54AssetScroll")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget()
    grid = QGridLayout(inner)
    grid.setContentsMargins(0, 4, 6, 12)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)
    scroll.setWidget(inner)
    outer.addWidget(scroll, 1)
    window._v54_asset_grid = grid

    empty = QLabel("Todavía no importaste imágenes.\nUsá “Importar imágenes” para agregar PNG, JPG, WebP o SVG.")
    empty.setAlignment(Qt.AlignCenter)
    empty.setWordWrap(True)
    empty.setProperty("muted", True)
    outer.addWidget(empty)
    window._v54_asset_empty = empty

    search.textChanged.connect(lambda _="": _refresh_library_ui(window))
    QTimer.singleShot(0, lambda: _refresh_library_ui(window))
    return tab


def _install_image_library(window):
    pages = getattr(window, "_v51_drawer_pages", {})
    page = pages.get("Imágenes")
    if page is None or page.findChild(QTabWidget, "v54ImageLibraryTabs") is not None:
        return

    old = page.layout()
    if old is None:
        return

    actions = QWidget()
    actions_lay = QVBoxLayout(actions)
    actions_lay.setContentsMargins(0, 0, 0, 0)
    actions_lay.setSpacing(9)
    while old.count():
        item = old.takeAt(0)
        w = item.widget()
        child = item.layout()
        if w is not None:
            w.setParent(actions)
            actions_lay.addWidget(w)
        elif child is not None:
            holder = QWidget()
            holder.setLayout(child)
            actions_lay.addWidget(holder)

    for button in actions.findChildren(QAbstractButton):
        text = button.text().replace("&", "").strip().casefold()
        if "insertar imagen" in text or "insertar svg" in text:
            try:
                button.clicked.disconnect()
            except Exception:
                pass
            button.setText("Importar imagen")
            button.clicked.connect(lambda _=False: _choose_images(window))

    tabs = QTabWidget()
    tabs.setObjectName("v54ImageLibraryTabs")
    tabs.addTab(_build_library_tab(window), "Biblioteca")
    tabs.addTab(actions, "Importar / Exportar")
    old.addWidget(tabs, 1)
    window._v54_image_tabs = tabs


def _color_to_data(color: QColor):
    return [color.red(), color.green(), color.blue(), color.alpha()]


def _color_from_data(data, fallback="#111827"):
    try:
        return QColor(*[int(x) for x in data])
    except Exception:
        return QColor(fallback)


def _pen_to_data(pen: QPen):
    return {
        "color": _color_to_data(pen.color()),
        "width": float(pen.widthF()),
        "style": int(pen.style()),
    }


def _pen_from_data(data) -> QPen:
    pen = QPen(_color_from_data((data or {}).get("color", [17, 24, 39, 255])))
    try:
        pen.setWidthF(float((data or {}).get("width", 1.0)))
        pen.setStyle(Qt.PenStyle(int((data or {}).get("style", int(Qt.SolidLine)))))
    except Exception:
        pass
    return pen


def _brush_to_data(brush: QBrush):
    return {"color": _color_to_data(brush.color()), "style": int(brush.style())}


def _brush_from_data(data) -> QBrush:
    brush = QBrush(_color_from_data((data or {}).get("color", [0, 0, 0, 255])))
    try:
        brush.setStyle(Qt.BrushStyle(int((data or {}).get("style", int(Qt.SolidPattern)))))
    except Exception:
        pass
    return brush


def _common_item(item: QGraphicsItem):
    return {
        "x": float(item.pos().x()),
        "y": float(item.pos().y()),
        "z": float(item.zValue()),
        "rotation": float(item.rotation()),
        "scale": float(item.scale()),
        "opacity": float(item.opacity()),
        "visible": bool(item.isVisible()),
        "data_kind": item.data(ROLE_KIND),
        "data_asset": item.data(ROLE_ASSET),
        "data_name": item.data(ROLE_NAME),
    }


def _apply_common(item: QGraphicsItem, data: dict):
    item.setPos(float(data.get("x", 0)), float(data.get("y", 0)))
    item.setZValue(float(data.get("z", 0)))
    item.setRotation(float(data.get("rotation", 0)))
    item.setScale(float(data.get("scale", 1)))
    item.setOpacity(float(data.get("opacity", 1)))
    item.setVisible(bool(data.get("visible", True)))
    item.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
    for role, key in ((ROLE_KIND, "data_kind"), (ROLE_ASSET, "data_asset"), (ROLE_NAME, "data_name")):
        if data.get(key) is not None:
            item.setData(role, data.get(key))
    item.setData(ROLE_V54, True)


def _path_to_data(path: QPainterPath):
    out = []
    for i in range(path.elementCount()):
        e = path.elementAt(i)
        out.append([int(e.type), float(e.x), float(e.y)])
    return out


def _path_from_data(elements) -> QPainterPath:
    p = QPainterPath()
    i = 0
    while i < len(elements):
        t, x, y = elements[i]
        if int(t) == int(QPainterPath.MoveToElement):
            p.moveTo(x, y)
            i += 1
        elif int(t) == int(QPainterPath.LineToElement):
            p.lineTo(x, y)
            i += 1
        elif int(t) == int(QPainterPath.CurveToElement) and i + 2 < len(elements):
            _, x1, y1 = elements[i + 1]
            _, x2, y2 = elements[i + 2]
            p.cubicTo(x, y, x1, y1, x2, y2)
            i += 3
        else:
            i += 1
    return p


def _cache_pixmap(pm: QPixmap) -> str | None:
    if pm.isNull():
        return None
    path_dir = _data_root() / "session_pixmaps"
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    if not pm.save(buf, "PNG"):
        return None
    raw = bytes(data)
    digest = hashlib.sha256(raw).hexdigest()[:24]
    out = path_dir / f"{digest}.png"
    if not out.exists():
        out.write_bytes(raw)
    return str(Path("session_pixmaps") / out.name).replace("\\", "/")


def _serialize_item(item: QGraphicsItem) -> dict | None:
    if isinstance(item, QGraphicsProxyWidget):
        return None
    d = _common_item(item)

    if isinstance(item, QGraphicsTextItem):
        font = item.font()
        d.update({
            "type": "text",
            "text": item.toPlainText(),
            "html": item.toHtml(),
            "color": _color_to_data(item.defaultTextColor()),
            "font": {
                "family": font.family(),
                "point": float(font.pointSizeF()),
                "pixel": int(font.pixelSize()),
                "weight": int(font.weight()),
                "italic": bool(font.italic()),
                "underline": bool(font.underline()),
                "strike": bool(font.strikeOut()),
            },
            "text_width": float(item.textWidth()),
        })
        return d

    if isinstance(item, QGraphicsPixmapItem):
        asset_id = item.data(ROLE_ASSET)
        rel = None
        if asset_id:
            entry = _find_entry(str(asset_id))
            if entry:
                rel = entry.get("path")
        if not rel:
            rel = _cache_pixmap(item.pixmap())
        if not rel:
            return None
        d.update({"type": "pixmap", "path": rel})
        return d

    if isinstance(item, QGraphicsPathItem):
        d.update({
            "type": "path",
            "path_elements": _path_to_data(item.path()),
            "pen": _pen_to_data(item.pen()),
            "brush": _brush_to_data(item.brush()),
        })
        return d

    if isinstance(item, QGraphicsRectItem):
        r = item.rect()
        d.update({
            "type": "rect", "rect": [r.x(), r.y(), r.width(), r.height()],
            "pen": _pen_to_data(item.pen()), "brush": _brush_to_data(item.brush())
        })
        return d

    if isinstance(item, QGraphicsEllipseItem):
        r = item.rect()
        d.update({
            "type": "ellipse", "rect": [r.x(), r.y(), r.width(), r.height()],
            "pen": _pen_to_data(item.pen()), "brush": _brush_to_data(item.brush())
        })
        return d

    if isinstance(item, QGraphicsLineItem):
        line = item.line()
        d.update({
            "type": "line", "line": [line.x1(), line.y1(), line.x2(), line.y2()],
            "pen": _pen_to_data(item.pen())
        })
        return d

    if isinstance(item, QGraphicsPolygonItem):
        poly = item.polygon()
        d.update({
            "type": "polygon",
            "points": [[float(p.x()), float(p.y())] for p in poly],
            "pen": _pen_to_data(item.pen()), "brush": _brush_to_data(item.brush())
        })
        return d

    return None


def _restore_item(data: dict) -> QGraphicsItem | None:
    kind = data.get("type")
    item = None

    if kind == "text":
        item = QGraphicsTextItem()
        html = data.get("html")
        if html:
            item.setHtml(str(html))
        else:
            item.setPlainText(str(data.get("text", "")))
        item.setDefaultTextColor(_color_from_data(data.get("color", [17, 24, 39, 255])))
        fd = data.get("font", {})
        font = QFont(str(fd.get("family", "")))
        point = float(fd.get("point", -1))
        pixel = int(fd.get("pixel", -1))
        if point > 0:
            font.setPointSizeF(point)
        elif pixel > 0:
            font.setPixelSize(pixel)
        try:
            font.setWeight(QFont.Weight(int(fd.get("weight", int(QFont.Weight.Normal)))))
        except Exception:
            pass
        font.setItalic(bool(fd.get("italic", False)))
        font.setUnderline(bool(fd.get("underline", False)))
        font.setStrikeOut(bool(fd.get("strike", False)))
        item.setFont(font)
        tw = float(data.get("text_width", -1))
        if tw > 0:
            item.setTextWidth(tw)

    elif kind == "pixmap":
        path = _data_root() / str(data.get("path", ""))
        pm = _load_pixmap(path)
        if pm.isNull():
            return None
        item = QGraphicsPixmapItem(pm)
        item.setTransformationMode(Qt.SmoothTransformation)

    elif kind == "path":
        item = QGraphicsPathItem(_path_from_data(data.get("path_elements", [])))
        item.setPen(_pen_from_data(data.get("pen")))
        item.setBrush(_brush_from_data(data.get("brush")))

    elif kind in ("rect", "ellipse"):
        vals = data.get("rect", [0, 0, 10, 10])
        rect = QRectF(*[float(x) for x in vals])
        item = QGraphicsRectItem(rect) if kind == "rect" else QGraphicsEllipseItem(rect)
        item.setPen(_pen_from_data(data.get("pen")))
        item.setBrush(_brush_from_data(data.get("brush")))

    elif kind == "line":
        vals = [float(x) for x in data.get("line", [0, 0, 10, 10])]
        item = QGraphicsLineItem(*vals)
        item.setPen(_pen_from_data(data.get("pen")))

    elif kind == "polygon":
        poly = QPolygonF()
        from PySide6.QtCore import QPointF
        for x, y in data.get("points", []):
            poly.append(QPointF(float(x), float(y)))
        item = QGraphicsPolygonItem(poly)
        item.setPen(_pen_from_data(data.get("pen")))
        item.setBrush(_brush_from_data(data.get("brush")))

    if item is not None:
        _apply_common(item, data)
    return item


def _is_user_item(item: QGraphicsItem) -> bool:
    if isinstance(item, QGraphicsProxyWidget):
        return False
    if item.data(ROLE_V54) or item.data(ROLE_KIND):
        return True
    flags = item.flags()
    return bool(flags & (QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable))


def _named_widget_state(window):
    result = {}
    widgets = (
        window.findChildren(QSpinBox)
        + window.findChildren(QDoubleSpinBox)
        + window.findChildren(QComboBox)
        + window.findChildren(QCheckBox)
    )
    for widget in widgets:
        name = widget.objectName()
        if not name or name.startswith(("v52", "v53", "v54")):
            continue
        try:
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                result[name] = {"kind": "number", "value": widget.value()}
            elif isinstance(widget, QComboBox):
                result[name] = {"kind": "combo", "index": widget.currentIndex(), "text": widget.currentText()}
            elif isinstance(widget, QCheckBox):
                result[name] = {"kind": "check", "checked": widget.isChecked()}
        except Exception:
            pass
    for attr in ("roll_total", "roll_remaining", "roll_initial", "size_combo"):
        widget = getattr(window, attr, None)
        if widget is None:
            continue
        key = f"@{attr}"
        try:
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                result[key] = {"kind": "number", "value": widget.value()}
            elif isinstance(widget, QComboBox):
                result[key] = {"kind": "combo", "index": widget.currentIndex(), "text": widget.currentText()}
        except Exception:
            pass
    return result


def _restore_widget_state(window, state):
    for key, data in (state or {}).items():
        widget = getattr(window, key[1:], None) if key.startswith("@") else window.findChild(QWidget, key)
        if widget is None:
            continue
        try:
            if data.get("kind") == "number" and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(data.get("value"))
            elif data.get("kind") == "combo" and isinstance(widget, QComboBox):
                idx = int(data.get("index", -1))
                if 0 <= idx < widget.count():
                    widget.setCurrentIndex(idx)
                elif data.get("text"):
                    widget.setCurrentText(str(data.get("text")))
            elif data.get("kind") == "check" and isinstance(widget, QCheckBox):
                widget.setChecked(bool(data.get("checked")))
        except Exception:
            pass


def save_session(window, announce=False) -> bool:
    if getattr(window, "_v54_restoring", False):
        return False
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return False
    scene = view.scene()
    try:
        items = []
        skipped = 0
        for item in reversed(scene.items()):
            if not _is_user_item(item):
                continue
            data = _serialize_item(item)
            if data is not None:
                items.append(data)
            else:
                skipped += 1
        sr = scene.sceneRect()
        payload = {
            "version": 1,
            "saved_at": int(time.time()),
            "scene_rect": [sr.x(), sr.y(), sr.width(), sr.height()],
            "items": items,
            "widgets": _named_widget_state(window),
            "drawer_page": getattr(window, "_v51_current_drawer", None),
            "drawer_visible": bool(getattr(window, "_v51_drawer", QWidget()).isVisible()) if hasattr(window, "_v51_drawer") else None,
            "inspector_visible": bool(getattr(window, "_v51_inspector", QWidget()).isVisible()) if hasattr(window, "_v51_inspector") else None,
            "skipped_items": skipped,
        }
        _atomic_json(_session_path(), payload)
        window._v54_last_saved = payload["saved_at"]
        label = getattr(window, "_v54_autosave_label", None)
        if label is not None:
            label.setText("Guardado automático: al día")
        if announce:
            window.statusBar().showMessage("Sesión guardada", 3000)
        return True
    except Exception as exc:
        label = getattr(window, "_v54_autosave_label", None)
        if label is not None:
            label.setText("Guardado automático: error")
        if announce:
            QMessageBox.warning(window, "Guardado automático", str(exc))
        return False


def _schedule_save(window):
    timer = getattr(window, "_v54_save_timer", None)
    if timer is not None and not getattr(window, "_v54_restoring", False):
        timer.start()


def restore_session(window, announce=False) -> bool:
    data = _read_json(_session_path(), None)
    if not isinstance(data, dict):
        return False
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return False

    scene = view.scene()
    window._v54_restoring = True
    try:
        for item in list(scene.items()):
            if _is_user_item(item):
                scene.removeItem(item)

        rect = data.get("scene_rect")
        if isinstance(rect, list) and len(rect) == 4:
            try:
                scene.setSceneRect(QRectF(*[float(x) for x in rect]))
            except Exception:
                pass

        restored = 0
        for item_data in data.get("items", []):
            if not isinstance(item_data, dict):
                continue
            item = _restore_item(item_data)
            if item is not None:
                scene.addItem(item)
                restored += 1

        _restore_widget_state(window, data.get("widgets", {}))

        drawer_page = data.get("drawer_page")
        if drawer_page and hasattr(window, "_v51_show_drawer"):
            try:
                window._v51_show_drawer(drawer_page)
            except Exception:
                pass
        if data.get("drawer_visible") is False and hasattr(window, "_v51_hide_drawer"):
            try:
                window._v51_hide_drawer()
            except Exception:
                pass

        inspector = getattr(window, "_v51_inspector", None)
        if inspector is not None and data.get("inspector_visible") is not None:
            inspector.setVisible(bool(data.get("inspector_visible")))

        label = getattr(window, "_v54_autosave_label", None)
        if label is not None:
            label.setText("Guardado automático: sesión restaurada")
        if announce:
            window.statusBar().showMessage(f"Sesión restaurada · {restored} elemento(s)", 5000)
        return True
    except Exception as exc:
        if announce:
            QMessageBox.warning(window, "Restaurar sesión", str(exc))
        return False
    finally:
        window._v54_restoring = False


def _install_autosave(window):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return

    save_timer = QTimer(window)
    save_timer.setSingleShot(True)
    save_timer.setInterval(1200)
    save_timer.timeout.connect(lambda: save_session(window, announce=False))
    window._v54_save_timer = save_timer

    periodic = QTimer(window)
    periodic.setInterval(15000)
    periodic.timeout.connect(lambda: save_session(window, announce=False))
    periodic.start()
    window._v54_periodic_timer = periodic

    try:
        view.scene().changed.connect(lambda _regions: _schedule_save(window))
    except Exception:
        pass

    tabs = getattr(window, "_v54_image_tabs", None)
    if tabs is not None:
        library_tab = tabs.widget(0)
        if library_tab is not None and library_tab.layout() is not None:
            label = QLabel("Guardado automático: activo")
            label.setObjectName("v54AutosaveStatus")
            label.setProperty("muted", True)
            library_tab.layout().insertWidget(1, label)
            window._v54_autosave_label = label

    QTimer.singleShot(350, lambda: restore_session(window, announce=False))


def _install_file_menu_actions(window):
    menu = window.menuBar()
    archivo = None
    for action in menu.actions():
        if action.menu() and action.text().replace("&", "").strip().casefold() == "archivo":
            archivo = action.menu()
            break
    if archivo is None:
        return
    archivo.addSeparator()
    save_action = archivo.addAction("Guardar sesión ahora")
    save_action.triggered.connect(lambda: save_session(window, announce=True))
    restore_action = archivo.addAction("Restaurar última sesión")
    restore_action.triggered.connect(lambda: restore_session(window, announce=True))
    window._v54_save_action = save_action
    window._v54_restore_action = restore_action


def enhance(window):
    _install_image_library(window)
    _install_autosave(window)
    _install_file_menu_actions(window)
    window.statusBar().showMessage(
        "V5.4 · biblioteca de imágenes persistente · importación corregida · guardado automático activo",
        6500,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v54_installed", False):
        return
    MainWindow._v54_installed = True

    original_init = MainWindow.__init__
    original_close = getattr(MainWindow, "closeEvent", None)

    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        enhance(self)

    def wrapped_close(self, event):
        try:
            save_session(self, announce=False)
        except Exception:
            pass
        if original_close is not None:
            return original_close(self, event)
        event.accept()

    MainWindow.__init__ = wrapped_init
    MainWindow.closeEvent = wrapped_close
