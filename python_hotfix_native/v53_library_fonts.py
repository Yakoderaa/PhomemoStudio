from __future__ import annotations

import os
from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, QStringListModel, QFileSystemWatcher, QSettings
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QFontComboBox, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QStackedWidget, QToolButton, QVBoxLayout,
    QWidget,
)

try:
    import qtawesome as qta
except Exception:
    qta = None

from .studio_pro import _font_dirs, load_all_fonts
from .v52_polish import _insert_open_icon


# Categories intentionally describe common label-design needs. They do not copy
# proprietary Print Master assets; they make the open catalog easier to browse.
CATEGORY_KEYWORDS = {
    "Todos": (),
    "Etiquetas y precio": ("tag", "label", "ticket", "receipt", "barcode", "qrcode", "qr", "price", "sale", "coupon"),
    "Marcos y decoración": ("border", "frame", "square", "circle", "ornament", "sparkle", "star", "ribbon", "banner", "badge", "seal"),
    "Hogar": ("home", "house", "bed", "bath", "couch", "sofa", "door", "key", "lamp", "light", "fan", "hanger"),
    "Cocina": ("kitchen", "utensil", "fork", "spoon", "knife", "bowl", "plate", "glass", "mug", "coffee", "bottle", "cup"),
    "Comida y bebida": ("food", "burger", "pizza", "apple", "carrot", "bread", "cake", "cookie", "cheese", "fish", "egg", "lemon", "wine", "beer"),
    "Animales": ("cat", "dog", "paw", "horse", "fish", "bird", "cow", "frog", "rabbit", "bear", "butterfly", "bug"),
    "Naturaleza": ("tree", "leaf", "seedling", "flower", "sun", "moon", "cloud", "rain", "snow", "mountain", "water", "wind", "plant"),
    "Ropa y organización": ("shirt", "tshirt", "sock", "shoe", "hanger", "box", "archive", "drawer", "basket", "package", "storage"),
    "Oficina y estudio": ("briefcase", "office", "file", "folder", "clipboard", "calendar", "printer", "paperclip", "pen", "pencil", "ruler", "book"),
    "Salud y cuidado": ("heart", "medical", "hospital", "stethoscope", "pill", "syringe", "bandage", "tooth", "brain", "eye", "soap"),
    "Comercio": ("store", "shop", "cart", "basket", "tag", "receipt", "cash", "wallet", "credit", "barcode", "box", "package", "gift"),
    "Transporte": ("car", "truck", "bus", "train", "plane", "ship", "bicycle", "motorcycle", "taxi", "road", "gas", "parking"),
    "Tecnología": ("computer", "laptop", "mobile", "phone", "wifi", "bluetooth", "usb", "keyboard", "mouse", "camera", "microchip", "battery"),
    "Comunicación": ("message", "comment", "chat", "envelope", "mail", "phone", "bell", "bullhorn", "microphone", "share", "at"),
    "Seguridad": ("lock", "shield", "key", "warning", "triangle", "fire", "helmet", "eye", "ban", "check", "danger"),
    "Fiestas y regalos": ("gift", "cake", "party", "balloon", "champagne", "star", "snowman", "tree", "heart", "music", "confetti", "candle"),
    "Bebés y niños": ("baby", "child", "kid", "stroller", "bottle", "toy", "game", "school", "puzzle", "teddy"),
    "Mascotas": ("paw", "dog", "cat", "bone", "fish", "pet"),
    "Viajes": ("suitcase", "luggage", "plane", "passport", "map", "location", "hotel", "camp", "tent", "mountain"),
    "Herramientas": ("tool", "hammer", "wrench", "screwdriver", "drill", "scissors", "ruler", "paint", "brush"),
    "Símbolos": ("check", "xmark", "plus", "minus", "info", "question", "warning", "arrow", "chevron", "circle", "square"),
}

SPANISH_ALIASES = {
    "casa": "home house", "hogar": "home house", "cocina": "kitchen utensil",
    "comida": "food", "bebida": "drink cup bottle", "cafe": "coffee mug",
    "perro": "dog", "gato": "cat", "mascota": "paw dog cat", "animal": "paw",
    "planta": "leaf flower tree plant", "flor": "flower", "arbol": "tree",
    "salud": "medical hospital heart", "medico": "medical doctor", "corazon": "heart",
    "tienda": "store shop", "carrito": "cart", "precio": "price tag receipt sale",
    "etiqueta": "tag label", "ticket": "ticket receipt", "codigo": "barcode qrcode qr",
    "marco": "frame border", "borde": "border frame", "cinta": "ribbon banner",
    "auto": "car", "coche": "car", "avion": "plane", "camion": "truck",
    "telefono": "phone mobile", "computadora": "computer laptop", "wifi": "wifi",
    "mensaje": "message comment chat", "correo": "mail envelope",
    "candado": "lock", "seguridad": "shield lock", "alerta": "warning",
    "regalo": "gift", "cumpleanos": "cake gift party", "navidad": "tree snowman gift",
    "ropa": "shirt tshirt hanger", "zapato": "shoe", "caja": "box package storage",
    "viaje": "travel suitcase luggage plane map", "bebe": "baby child", "nino": "child kid",
}


def _norm(text: str) -> str:
    return " ".join((text or "").lower().replace("-", " ").replace("_", " ").split())


def _catalog_sources():
    if qta is None:
        return []
    try:
        inst = qta._instance()
        rows = []
        for prefix, cmap in sorted(inst.charmap.items()):
            if not cmap:
                continue
            pretty = {
                "fa6": "Font Awesome Regular", "fa6s": "Font Awesome Solid", "fa6b": "Font Awesome Brands",
                "fa5": "Font Awesome 5 Regular", "fa5s": "Font Awesome 5 Solid", "fa5b": "Font Awesome 5 Brands",
                "mdi": "Material Design", "mdi6": "Material Design 6", "ph": "Phosphor", "ri": "Remix",
                "ei": "Elusive", "msc": "Material Symbols",
            }.get(prefix, prefix.upper())
            rows.append((prefix, pretty, cmap))
        return rows
    except Exception:
        return []


def catalog_size() -> int:
    return sum(len(cmap) for _, _, cmap in _catalog_sources())


def _expanded_query(text: str) -> list[str]:
    q = _norm(text)
    if not q:
        return []
    out = list(q.split())
    for word in list(out):
        out.extend(SPANISH_ALIASES.get(word, "").split())
    return list(dict.fromkeys(x for x in out if x))


def _matches_category(name: str, category: str) -> bool:
    words = CATEGORY_KEYWORDS.get(category, ())
    if not words:
        return True
    n = _norm(name)
    return any(w in n for w in words)


def _build_xl_library(window):
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(10)

    title = QLabel("Biblioteca XL")
    title.setStyleSheet("font-size:17px;font-weight:700;")
    outer.addWidget(title)
    subtitle = QLabel("Miles de objetos de colecciones abiertas, organizados para etiquetas. Escribí para filtrar al instante.")
    subtitle.setWordWrap(True)
    subtitle.setProperty("muted", True)
    outer.addWidget(subtitle)

    search = QLineEdit()
    search.setObjectName("v53ObjectSearch")
    search.setPlaceholderText("Buscar: marco, cocina, precio, regalo, mascota, viaje…")
    search.setClearButtonEnabled(True)
    outer.addWidget(search)

    filters = QHBoxLayout()
    category = QComboBox(); category.setObjectName("v53ObjectCategory"); category.addItems(list(CATEGORY_KEYWORDS))
    source = QComboBox(); source.setObjectName("v53ObjectSource"); source.addItem("Todas las colecciones", "*")
    for prefix, label, _ in _catalog_sources():
        source.addItem(label, prefix)
    filters.addWidget(category, 1); filters.addWidget(source, 1)
    outer.addLayout(filters)

    count = QLabel(); count.setObjectName("v53ObjectCount"); count.setProperty("muted", True)
    outer.addWidget(count)

    scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget(); grid = QGridLayout(inner); grid.setContentsMargins(0, 4, 6, 12); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8)
    scroll.setWidget(inner); outer.addWidget(scroll, 1)

    more = QPushButton("Mostrar 200 más")
    more.setProperty("role", "secondary")
    outer.addWidget(more)

    state = {"limit": 200, "matches": []}

    def clear_grid():
        while grid.count():
            it = grid.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()

    def collect():
        selected_source = source.currentData()
        selected_category = category.currentText()
        terms = _expanded_query(search.text())
        rows = []
        seen = set()
        for prefix, label, cmap in _catalog_sources():
            if selected_source != "*" and selected_source != prefix:
                continue
            for name in cmap.keys():
                if not _matches_category(name, selected_category):
                    continue
                normalized = _norm(name)
                if terms and not all(any(piece in normalized for piece in term.split()) for term in terms):
                    # Match any expanded term, which feels natural while typing.
                    if not any(term in normalized for term in terms):
                        continue
                key = (prefix, name)
                if key in seen:
                    continue
                seen.add(key); rows.append((prefix, label, name))
        return rows

    def render(reset=True):
        if reset:
            state["limit"] = 200
            state["matches"] = collect()
        clear_grid()
        subset = state["matches"][:state["limit"]]
        cols = 3
        for i, (prefix, label, name) in enumerate(subset):
            b = QToolButton()
            text = name.replace("-", " ").replace("_", " ")
            if len(text) > 18:
                text = text[:17] + "…"
            b.setText(text)
            try:
                b.setIcon(qta.icon(f"{prefix}.{name}", color="#18202A"))
            except Exception:
                continue
            b.setIconSize(QSize(36, 36)); b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setProperty("shapeTile", True); b.setFixedSize(92, 78)
            b.setToolTip(f"{label} · {name}")
            b.clicked.connect(partial(_insert_open_icon, window, prefix, name))
            grid.addWidget(b, i // cols, i % cols)
        total = len(state["matches"]); shown = min(state["limit"], total)
        count.setText(f"{total:,} objetos encontrados · mostrando {shown:,}".replace(",", "."))
        more.setVisible(shown < total)

    def load_more():
        state["limit"] += 200; render(False)

    search.textChanged.connect(lambda _="": render(True))
    category.currentIndexChanged.connect(lambda _=0: render(True))
    source.currentIndexChanged.connect(lambda _=0: render(True))
    more.clicked.connect(load_more)
    render(True)
    return page


def _install_library_entry(window):
    pages = getattr(window, "_v51_drawer_pages", None)
    if not isinstance(pages, dict) or "Biblioteca" in pages:
        return
    stack = window.findChild(QStackedWidget, "v51DrawerStack")
    rail = window.findChild(QWidget, "v51Rail")
    if stack is None or rail is None or rail.layout() is None:
        return
    page = _build_xl_library(window)
    pages["Biblioteca"] = page
    stack.addWidget(page)

    button = QToolButton(); button.setText("✦"); button.setToolTip("Biblioteca XL")
    button.setProperty("nav", True); button.setToolButtonStyle(Qt.ToolButtonTextOnly); button.setFixedSize(48, 44)
    button.clicked.connect(lambda _=False: window._v51_show_drawer("Biblioteca"))
    caption = QLabel("Biblioteca"); caption.setProperty("railCaption", True); caption.setAlignment(Qt.AlignCenter)
    lay = rail.layout(); index = max(0, lay.count() - 1)
    lay.insertWidget(index, button, 0, Qt.AlignHCenter); lay.insertWidget(index + 1, caption)
    getattr(window, "_v51_nav_buttons", {})["Biblioteca"] = button

    settings = QSettings("Yakoderaa", "PhomemoStudio")
    if not settings.value("v53/libraryIntroduced", False, type=bool):
        window._v51_show_drawer("Biblioteca")
        settings.setValue("v53/libraryIntroduced", True)


def _font_combo_candidates(window):
    families = set(QFontComboBox().itemText(i) for i in range(QFontComboBox().count()))
    result = []
    for combo in window.findChildren(QComboBox):
        hint = _norm(combo.objectName())
        current = combo.currentText().strip()
        if isinstance(combo, QFontComboBox) or "font" in hint or "fuente" in hint or current in families:
            result.append(combo)
    # De-duplicate while preserving order.
    seen = set(); out = []
    for c in result:
        if id(c) not in seen:
            seen.add(id(c)); out.append(c)
    return out


def _font_dir_signature():
    sig = []
    for root in _font_dirs():
        try:
            st = root.stat(); sig.append((str(root), int(st.st_mtime_ns)))
        except Exception:
            continue
    return tuple(sig)


def _setup_font_search(window):
    state = {"families": [], "signature": None}

    def refresh(force=False):
        signature = _font_dir_signature()
        if not force and signature == state["signature"]:
            return
        state["signature"] = signature
        load_all_fonts()
        from PySide6.QtGui import QFontDatabase
        families = sorted(QFontDatabase.families(), key=str.casefold)
        if not force and families == state["families"]:
            return
        state["families"] = families
        for combo in _font_combo_candidates(window):
            typed = combo.lineEdit().text() if combo.isEditable() and combo.lineEdit() else combo.currentText()
            combo.blockSignals(True)
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            combo.clear(); combo.addItems(families)
            combo.setCurrentText(typed)
            model = QStringListModel(families, combo)
            completer = QCompleter(model, combo)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            completer.setFilterMode(Qt.MatchContains)
            completer.setMaxVisibleItems(18)
            combo.setCompleter(completer)
            if combo.lineEdit():
                combo.lineEdit().setClearButtonEnabled(True)
                combo.lineEdit().setPlaceholderText("Escribí para buscar una fuente…")
            combo.blockSignals(False)

    # Windows Fonts and Adobe roots usually emit a directory change; watch them.
    watcher = QFileSystemWatcher(window)
    watch_paths = [str(p) for p in _font_dirs() if p.exists()]
    if watch_paths:
        watcher.addPaths(watch_paths)
    watcher.directoryChanged.connect(lambda _p: QTimer.singleShot(350, lambda: refresh(True)))
    watcher.fileChanged.connect(lambda _p: QTimer.singleShot(350, lambda: refresh(True)))
    window._v53_font_watcher = watcher

    # Fallback polling catches Adobe/CoreSync changes in nested directories and
    # Windows per-user font installs that do not always trigger the watcher.
    timer = QTimer(window); timer.setInterval(7000); timer.timeout.connect(lambda: refresh(False)); timer.start()
    window._v53_font_timer = timer
    window._v53_refresh_fonts = lambda: refresh(True)
    refresh(True)


def enhance(window):
    _setup_font_search(window)
    _install_library_entry(window)
    window.statusBar().showMessage("V5.3 · fuentes dinámicas + Biblioteca XL", 5000)


def install(MainWindow):
    if getattr(MainWindow, "_v53_library_fonts_installed", False):
        return
    MainWindow._v53_library_fonts_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
