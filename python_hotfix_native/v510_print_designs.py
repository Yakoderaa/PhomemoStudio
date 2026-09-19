from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAction, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget
)

from .studio_pro import _find_canvas
from .v54_assets_session import (
    _atomic_json, _data_root, _is_user_item, _named_widget_state,
    _restore_item, _restore_widget_state, _serialize_item, save_session
)

OVERLAY_ROLE = 1098


def _design_root() -> Path:
    root = _data_root() / "designs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _index_path() -> Path:
    return _design_root() / "index.json"


def _load_index() -> list[dict]:
    try:
        data = json.loads(_index_path().read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict) and x.get("id")]
    except Exception:
        pass
    return []


def _save_index(entries: list[dict]) -> None:
    _atomic_json(_index_path(), entries)


def _design_path(design_id: str) -> Path:
    return _design_root() / f"{design_id}.json"


def _preview_path(design_id: str) -> Path:
    return _design_root() / f"{design_id}.png"


def _capture_document(window) -> dict:
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        raise RuntimeError("No encontré el lienzo activo.")
    scene = view.scene()
    items = []
    for item in reversed(scene.items()):
        if item.data(OVERLAY_ROLE):
            continue
        if not _is_user_item(item):
            continue
        data = _serialize_item(item)
        if data is not None:
            items.append(data)
    rect = scene.sceneRect()
    return {
        "format": 1,
        "scene_rect": [float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height())],
        "items": items,
        "widgets": _named_widget_state(window),
    }


def _render_preview(window, path: Path) -> None:
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return
    scene = view.scene()
    overlays = [item for item in scene.items() if item.data(OVERLAY_ROLE)]
    states = [(item, item.isVisible()) for item in overlays]
    try:
        for item, _visible in states:
            item.setVisible(False)
        source = scene.sceneRect()
        if source.isNull() or source.width() <= 0 or source.height() <= 0:
            source = scene.itemsBoundingRect()
        if source.isNull() or source.width() <= 0 or source.height() <= 0:
            return

        size = QSize(360, 160)
        image = QImage(size, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.white)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        target = QRectF(0, 0, size.width(), size.height())
        scene.render(painter, target, source, Qt.KeepAspectRatio)
        painter.end()
        image.save(str(path), "PNG")
    finally:
        for item, visible in states:
            try:
                item.setVisible(visible)
            except Exception:
                pass


def _new_id(name: str) -> str:
    seed = f"{name}|{time.time_ns()}".encode("utf-8")
    return hashlib.sha1(seed).hexdigest()[:20]


def _find_by_name(entries: list[dict], name: str):
    wanted = name.strip().casefold()
    for entry in entries:
        if str(entry.get("name", "")).strip().casefold() == wanted:
            return entry
    return None


def save_design(window, name: str | None = None):
    if name is None:
        current = getattr(window, "_v510_current_design_name", "")
        name, ok = QInputDialog.getText(window, "Guardar diseño", "Nombre del diseño:", text=current)
        if not ok:
            return None
    name = str(name).strip()
    if not name:
        QMessageBox.warning(window, "Diseños", "Escribí un nombre para guardar el diseño.")
        return None

    entries = _load_index()
    existing = _find_by_name(entries, name)
    if existing is not None:
        answer = QMessageBox.question(
            window,
            "Reemplazar diseño",
            f"Ya existe “{name}”. ¿Querés reemplazarlo?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return None
        design_id = str(existing["id"])
        entry = existing
    else:
        design_id = _new_id(name)
        entry = {"id": design_id, "name": name}
        entries.insert(0, entry)

    payload = _capture_document(window)
    payload["id"] = design_id
    payload["name"] = name
    payload["saved_at"] = int(time.time())
    _atomic_json(_design_path(design_id), payload)
    _render_preview(window, _preview_path(design_id))

    entry.update({
        "name": name,
        "saved_at": payload["saved_at"],
        "preview": _preview_path(design_id).name,
    })
    entries = [e for e in entries if e.get("id") == design_id] + [e for e in entries if e.get("id") != design_id]
    _save_index(entries)

    window._v510_current_design_id = design_id
    window._v510_current_design_name = name
    _refresh_library(window)
    window.statusBar().showMessage(f"Diseño guardado: {name}", 4500)
    return design_id


def duplicate_design(window):
    current = getattr(window, "_v510_current_design_name", "")
    suggested = f"{current} copia" if current else "Copia del diseño"
    name, ok = QInputDialog.getText(window, "Duplicar diseño", "Nombre de la copia:", text=suggested)
    if not ok:
        return None
    return save_design(window, name)


def load_design(window, design_id: str):
    path = _design_path(design_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        QMessageBox.warning(window, "Diseños", f"No pude abrir el diseño.\n\n{exc}")
        return False

    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return False
    scene = view.scene()

    controller = getattr(window, "_v55_transform_controller", None)
    if controller is not None:
        controller.set_overlay_visible(False)

    scene.clearSelection()
    for item in list(scene.items()):
        if item.data(OVERLAY_ROLE):
            continue
        if _is_user_item(item):
            scene.removeItem(item)

    rect = data.get("scene_rect")
    if isinstance(rect, list) and len(rect) == 4:
        try:
            scene.setSceneRect(QRectF(*[float(v) for v in rect]))
        except Exception:
            pass

    restored = 0
    for raw in data.get("items", []):
        if not isinstance(raw, dict):
            continue
        item = _restore_item(raw)
        if item is not None:
            scene.addItem(item)
            restored += 1

    _restore_widget_state(window, data.get("widgets", {}))
    window._v510_current_design_id = design_id
    window._v510_current_design_name = str(data.get("name", "Diseño"))
    if controller is not None:
        controller.target = None
        controller.set_overlay_visible(True)
        controller.refresh_selection()
    binder = getattr(window, "_v56_text_binder", None)
    if binder is not None:
        binder.sync_from_selection()

    save_session(window, announce=False)
    history = getattr(window, "_v57_history", None)
    if history is not None:
        history.undo_stack = []
        history.redo_stack = []
        history._initialized = False
        history.initialize()

    window.statusBar().showMessage(f"Diseño cargado: {window._v510_current_design_name}", 4500)
    return True


def delete_design(window, design_id: str):
    entries = _load_index()
    entry = next((e for e in entries if e.get("id") == design_id), None)
    if entry is None:
        return
    name = str(entry.get("name", "Diseño"))
    answer = QMessageBox.question(
        window,
        "Eliminar diseño",
        f"¿Eliminar “{name}” de la biblioteca?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if answer != QMessageBox.Yes:
        return
    for path in (_design_path(design_id), _preview_path(design_id)):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
    _save_index([e for e in entries if e.get("id") != design_id])
    if getattr(window, "_v510_current_design_id", None) == design_id:
        window._v510_current_design_id = None
        window._v510_current_design_name = ""
    _refresh_library(window)


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear_layout(child)


def _design_card(window, entry: dict) -> QWidget:
    card = QFrame()
    card.setProperty("card", True)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(8, 8, 8, 8)
    lay.setSpacing(6)

    design_id = str(entry.get("id"))
    preview = _preview_path(design_id)
    open_button = QToolButton()
    open_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    open_button.setText(str(entry.get("name", "Diseño")))
    open_button.setToolTip("Abrir este diseño")
    open_button.setMinimumSize(132, 105)
    if preview.exists():
        pm = QPixmap(str(preview))
        if not pm.isNull():
            open_button.setIcon(QIcon(pm))
            open_button.setIconSize(QSize(118, 64))
    open_button.clicked.connect(lambda _=False, did=design_id: load_design(window, did))
    lay.addWidget(open_button)

    actions = QHBoxLayout()
    load_btn = QPushButton("Abrir")
    load_btn.clicked.connect(lambda _=False, did=design_id: load_design(window, did))
    delete_btn = QPushButton("Eliminar")
    delete_btn.clicked.connect(lambda _=False, did=design_id: delete_design(window, did))
    actions.addWidget(load_btn)
    actions.addWidget(delete_btn)
    lay.addLayout(actions)
    return card


def _refresh_library(window):
    grid = getattr(window, "_v510_design_grid", None)
    if grid is None:
        return
    _clear_layout(grid)
    entries = _load_index()
    query = getattr(window, "_v510_design_search", None)
    needle = query.text().strip().casefold() if query is not None else ""
    if needle:
        entries = [e for e in entries if needle in str(e.get("name", "")).casefold()]
    count = getattr(window, "_v510_design_count", None)
    if count is not None:
        count.setText(f"{len(entries)} diseño(s) guardado(s)")
    empty = getattr(window, "_v510_design_empty", None)
    if empty is not None:
        empty.setVisible(not entries)
    for i, entry in enumerate(entries):
        grid.addWidget(_design_card(window, entry), i // 2, i % 2)
    grid.setRowStretch((len(entries) + 1) // 2 + 1, 1)


def _rebuild_designs_page(window):
    pages = getattr(window, "_v51_drawer_pages", {})
    page = pages.get("Diseños")
    if page is None or page.layout() is None:
        return
    layout = page.layout()
    _clear_layout(layout)
    layout.setSpacing(10)

    info = QLabel("Tus diseños se guardan localmente y siguen disponibles al cerrar o reiniciar Phomemo Studio.")
    info.setWordWrap(True)
    info.setProperty("muted", True)
    layout.addWidget(info)

    row = QHBoxLayout()
    save_btn = QPushButton("Guardar diseño")
    save_btn.setObjectName("v510SaveDesign")
    save_btn.setProperty("role", "primary")
    save_btn.clicked.connect(lambda: save_design(window))
    dup_btn = QPushButton("Duplicar")
    dup_btn.clicked.connect(lambda: duplicate_design(window))
    row.addWidget(save_btn, 1)
    row.addWidget(dup_btn)
    layout.addLayout(row)

    search = QLineEdit()
    search.setObjectName("v510DesignSearch")
    search.setPlaceholderText("Buscar diseños…")
    search.setClearButtonEnabled(False)
    layout.addWidget(search)
    window._v510_design_search = search

    count = QLabel()
    count.setProperty("muted", True)
    layout.addWidget(count)
    window._v510_design_count = count

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    host = QWidget()
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 4, 6, 12)
    grid.setSpacing(8)
    scroll.setWidget(host)
    layout.addWidget(scroll, 1)
    window._v510_design_grid = grid

    empty = QLabel("Todavía no guardaste ningún diseño.")
    empty.setAlignment(Qt.AlignCenter)
    empty.setProperty("muted", True)
    layout.addWidget(empty)
    window._v510_design_empty = empty

    search.textChanged.connect(lambda _="": _refresh_library(window))
    _refresh_library(window)


def _redirect_save_surfaces(window):
    # Replace the V5.1 proxy buttons that were wired to the legacy template
    # implementation before this persistent library existed.
    for button in window.findChildren(QPushButton):
        text = button.text().replace("&", "").strip().casefold()
        if text == "guardar":
            try:
                button.clicked.disconnect()
            except Exception:
                pass
            button.clicked.connect(lambda _=False: save_design(window))
        elif text == "duplicar":
            try:
                button.clicked.disconnect()
            except Exception:
                pass
            button.clicked.connect(lambda _=False: duplicate_design(window))

    for action in window.findChildren(QAction):
        text = action.text().replace("&", "").strip().casefold()
        if text == "guardar diseño":
            try:
                action.triggered.disconnect()
            except Exception:
                pass
            action.triggered.connect(lambda _=False: save_design(window))
        elif text == "duplicar diseño":
            try:
                action.triggered.disconnect()
            except Exception:
                pass
            action.triggered.connect(lambda _=False: duplicate_design(window))


def enhance(window):
    _rebuild_designs_page(window)
    _redirect_save_surfaces(window)
    window._v510_save_design = lambda name=None: save_design(window, name)
    window._v510_load_design = lambda design_id: load_design(window, design_id)
    window.statusBar().showMessage(
        "V5.10 · impresión estable · biblioteca persistente de diseños",
        6000,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v510_installed", False):
        return
    MainWindow._v510_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
