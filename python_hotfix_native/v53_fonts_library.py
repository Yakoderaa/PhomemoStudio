from __future__ import annotations

import os
from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, QStringListModel
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QFontComboBox, QGraphicsItem, QGraphicsPixmapItem,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

try:
    import qtawesome as qta
except Exception:
    qta = None

from .studio_pro import _find_canvas, _font_dirs


# QtAwesome 1.4.x ships these free/open icon collections.  The list deliberately
# includes both visual styles where the upstream font exposes them, so the user
# can choose a thin/regular/solid look instead of being limited to one subset.
ICON_SOURCES = [
    ("fa6", "Font Awesome 6 · regular"),
    ("fa6s", "Font Awesome 6 · sólido"),
    ("fa6b", "Font Awesome 6 · marcas"),
    ("fa5", "Font Awesome 5 · regular"),
    ("fa5s", "Font Awesome 5 · sólido"),
    ("fa5b", "Font Awesome 5 · marcas"),
    ("ei", "Elusive Icons"),
    ("mdi6", "Material Design Icons 6"),
    ("mdi", "Material Design Icons 5"),
    ("ph", "Phosphor"),
    ("ri", "Remix Icon"),
    ("msc", "Microsoft Codicons"),
]

PROBES = {
    "fa6": "flag", "fa6s": "house", "fa6b": "github",
    "fa5": "flag", "fa5s": "home", "fa5b": "github",
    "ei": "asl", "mdi6": "home", "mdi": "home",
    "ph": "microphone-fill", "ri": "home-line", "msc": "squirrel",
}

CATEGORY_KEYWORDS = {
    "Todos": (),
    "Etiquetas y precios": ("tag", "label", "price", "sale", "discount", "ticket", "receipt", "barcode", "qr", "coupon"),
    "Marcos y contenedores": ("frame", "border", "square", "rectangle", "circle", "box", "badge", "outline", "crop", "focus"),
    "Flechas": ("arrow", "chevron", "caret", "direction", "forward", "back", "up", "down"),
    "Hogar": ("house", "home", "bed", "bath", "couch", "door", "key", "lamp", "light", "fan", "garage"),
    "Cocina": ("kitchen", "utensil", "fork", "spoon", "knife", "bowl", "plate", "glass", "mug", "coffee", "bottle", "chef"),
    "Comida y bebidas": ("food", "burger", "pizza", "apple", "carrot", "bread", "cake", "cookie", "cheese", "fish", "egg", "lemon", "wine", "beer", "drink"),
    "Animales": ("cat", "dog", "paw", "horse", "fish", "bird", "cow", "frog", "dragon", "otter", "hippo", "spider", "bug", "rabbit", "turtle"),
    "Naturaleza": ("tree", "leaf", "seedling", "flower", "sun", "moon", "cloud", "rain", "snow", "mountain", "water", "wind", "fire"),
    "Personas": ("person", "user", "people", "face", "man", "woman", "child", "body", "account"),
    "Bebés": ("baby", "child", "stroller", "bottle", "pacifier", "diaper"),
    "Ropa y belleza": ("shirt", "dress", "shoe", "hat", "glasses", "scissors", "hair", "lipstick", "face", "spa", "hanger"),
    "Salud": ("heart", "medical", "hospital", "stethoscope", "pill", "syringe", "bandage", "virus", "tooth", "brain", "eye", "doctor"),
    "Comercio": ("store", "shop", "cart", "basket", "tag", "receipt", "cash", "wallet", "credit", "barcode", "box", "package", "money"),
    "Envíos": ("package", "box", "truck", "shipping", "delivery", "warehouse", "map", "location", "pin", "fragile"),
    "Oficina": ("briefcase", "office", "file", "folder", "clipboard", "calendar", "printer", "paperclip", "pen", "pencil", "ruler", "document"),
    "Educación": ("school", "book", "graduate", "graduation", "pencil", "ruler", "calculator", "student", "teacher", "alphabet"),
    "Herramientas": ("hammer", "wrench", "screw", "tool", "drill", "saw", "ruler", "measure", "paint", "brush"),
    "Transporte": ("car", "truck", "bus", "train", "plane", "ship", "bicycle", "motorcycle", "taxi", "road", "gas", "parking"),
    "Viajes": ("plane", "suitcase", "passport", "map", "hotel", "beach", "camp", "tent", "mountain", "location"),
    "Tecnología": ("computer", "laptop", "mobile", "phone", "wifi", "bluetooth", "usb", "keyboard", "mouse", "camera", "microchip", "battery", "robot"),
    "Comunicación": ("message", "comment", "chat", "envelope", "mail", "phone", "bell", "bullhorn", "microphone", "share", "at"),
    "Seguridad": ("lock", "shield", "key", "warning", "triangle", "fire", "helmet", "eye", "ban", "check", "alert"),
    "Limpieza": ("broom", "vacuum", "spray", "soap", "wash", "clean", "brush", "water", "bucket"),
    "Baño": ("bath", "shower", "toilet", "soap", "water", "sink", "towel"),
    "Deportes": ("ball", "football", "basketball", "baseball", "tennis", "golf", "run", "bike", "medal", "trophy", "swim"),
    "Música": ("music", "note", "guitar", "piano", "microphone", "headphone", "speaker", "radio", "drum"),
    "Juegos": ("game", "controller", "dice", "chess", "cards", "puzzle", "joystick"),
    "Fiesta": ("gift", "cake", "party", "balloon", "champagne", "star", "music", "confetti", "candle"),
    "Navidad": ("christmas", "snowman", "tree", "gift", "bell", "snow", "candy", "star", "santa"),
    "Amor": ("heart", "love", "kiss", "rose", "ring", "gift", "valentine"),
    "Clima": ("sun", "cloud", "rain", "snow", "wind", "storm", "lightning", "temperature", "weather"),
    "Tiempo": ("clock", "time", "calendar", "timer", "hour", "watch", "history", "alarm"),
    "Reciclaje": ("recycle", "trash", "bin", "leaf", "earth", "eco", "green", "battery"),
    "Símbolos": ("check", "close", "plus", "minus", "star", "heart", "circle", "square", "info", "question", "warning"),
}

SPANISH_ALIASES = {
    "casa": "house home", "hogar": "house home", "cocina": "kitchen utensil chef",
    "comida": "food", "bebida": "drink bottle", "cafe": "coffee mug",
    "perro": "dog", "gato": "cat", "animal": "paw", "pajaro": "bird",
    "planta": "leaf flower tree", "flor": "flower", "arbol": "tree", "nube": "cloud",
    "sol": "sun", "luna": "moon", "lluvia": "rain", "nieve": "snow",
    "salud": "medical hospital", "medico": "medical doctor", "corazon": "heart",
    "diente": "tooth", "pastilla": "pill", "vacuna": "syringe",
    "tienda": "store shop", "carrito": "cart", "precio": "tag price receipt", "descuento": "discount sale",
    "etiqueta": "tag label", "codigo": "barcode qr", "caja": "box package",
    "envio": "shipping delivery package", "camion": "truck", "almacen": "warehouse",
    "auto": "car", "coche": "car", "avion": "plane", "tren": "train", "bicicleta": "bicycle bike",
    "telefono": "phone mobile", "computadora": "computer laptop", "wifi": "wifi", "camara": "camera",
    "mensaje": "message comment chat", "correo": "mail envelope", "campana": "bell",
    "candado": "lock", "seguridad": "shield lock", "alerta": "warning alert",
    "limpieza": "clean broom vacuum soap", "escoba": "broom", "aspiradora": "vacuum", "jabon": "soap",
    "ropa": "shirt dress hanger", "zapato": "shoe", "belleza": "spa lipstick hair",
    "escuela": "school book student", "libro": "book", "lapiz": "pencil",
    "herramienta": "tool wrench hammer", "martillo": "hammer", "llave": "wrench key",
    "deporte": "sport ball trophy", "pelota": "ball", "futbol": "football soccer",
    "musica": "music note", "guitarra": "guitar", "auricular": "headphone",
    "juego": "game controller dice", "regalo": "gift", "cumpleanos": "cake gift party",
    "navidad": "christmas tree snowman gift", "amor": "love heart", "bebe": "baby child",
    "reloj": "clock time", "calendario": "calendar", "reciclar": "recycle trash eco",
    "flecha": "arrow chevron", "marco": "frame border", "circulo": "circle", "estrella": "star",
}


def _norm(text: str) -> str:
    return " ".join((text or "").lower().replace("-", " ").replace("_", " ").split())


def _ensure_prefix(prefix: str):
    if qta is None:
        return
    probe = PROBES.get(prefix)
    if not probe:
        return
    try:
        qta.icon(f"{prefix}.{probe}")
    except Exception:
        pass


def _catalog_for(prefix: str):
    if qta is None:
        return []
    _ensure_prefix(prefix)
    try:
        cmap = getattr(qta._instance(), "charmap", {}).get(prefix, {})
        return sorted(cmap.keys())
    except Exception:
        return []


def massive_catalog_size() -> int:
    return sum(len(_catalog_for(prefix)) for prefix, _ in ICON_SOURCES)


def _expanded_query(text: str) -> list[str]:
    words = _norm(text).split()
    out = list(words)
    for word in words:
        out.extend(SPANISH_ALIASES.get(word, "").split())
    return list(dict.fromkeys(x for x in out if x))


def _matches_category(name: str, category: str) -> bool:
    keys = CATEGORY_KEYWORDS.get(category, ())
    if not keys:
        return True
    n = _norm(name)
    return any(key in n for key in keys)


def _insert_icon(window, prefix: str, name: str):
    if qta is None:
        return
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return
    try:
        icon = qta.icon(f"{prefix}.{name}", color="#111827")
        pm = icon.pixmap(QSize(256, 256))
    except Exception:
        return
    item = QGraphicsPixmapItem(pm)
    item.setTransformationMode(Qt.SmoothTransformation)
    item.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
    item.setData(1001, "open-icon")
    item.setData(1002, f"{prefix}.{name}")
    scale = 0.40
    item.setScale(scale)
    center = view.mapToScene(view.viewport().rect().center())
    br = item.boundingRect()
    item.setPos(center.x() - br.width() * scale / 2, center.y() - br.height() * scale / 2)
    view.scene().addItem(item)
    item.setSelected(True)


def _build_massive_library(window):
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(9)

    headline = QLabel("Biblioteca de objetos")
    headline.setProperty("sectionTitle", True)
    outer.addWidget(headline)
    info = QLabel("Miles de objetos de colecciones abiertas, agrupados para crear etiquetas. Buscá en español o por nombre del icono.")
    info.setWordWrap(True)
    info.setProperty("muted", True)
    outer.addWidget(info)

    filters = QHBoxLayout()
    source = QComboBox()
    source.setObjectName("v53ObjectSource")
    source.addItem("Todas las colecciones", "*")
    for prefix, label in ICON_SOURCES:
        source.addItem(label, prefix)
    category = QComboBox()
    category.setObjectName("v53ObjectCategory")
    category.addItems(list(CATEGORY_KEYWORDS.keys()))
    filters.addWidget(source, 1)
    filters.addWidget(category, 1)
    outer.addLayout(filters)

    search = QLineEdit()
    search.setObjectName("v53ObjectSearch")
    search.setClearButtonEnabled(True)
    search.setPlaceholderText("Buscar: etiqueta, casa, comida, gato, envío, corazón…")
    outer.addWidget(search)

    count = QLabel()
    count.setObjectName("v53ObjectCount")
    count.setProperty("muted", True)
    outer.addWidget(count)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget()
    grid = QGridLayout(inner)
    grid.setContentsMargins(0, 4, 6, 12)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)
    scroll.setWidget(inner)
    outer.addWidget(scroll, 1)

    more = QPushButton("Mostrar 180 más")
    more.setProperty("role", "secondary")
    outer.addWidget(more)

    state = {"limit": 180, "matches": []}

    def clear_grid():
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def build_matches():
        selected_source = source.currentData()
        selected_category = category.currentText()
        terms = _expanded_query(search.text())
        result = []
        for prefix, label in ICON_SOURCES:
            if selected_source != "*" and prefix != selected_source:
                continue
            for name in _catalog_for(prefix):
                if not _matches_category(name, selected_category):
                    continue
                normalized = _norm(name)
                if terms and not all(any(part in normalized for part in term.split()) for term in terms[:1]):
                    if not any(term in normalized for term in terms):
                        continue
                result.append((prefix, label, name))
        return result

    def render(reset=True):
        if reset:
            state["limit"] = 180
            state["matches"] = build_matches()
        clear_grid()
        subset = state["matches"][: state["limit"]]
        rendered = 0
        for prefix, label, name in subset:
            try:
                icon = qta.icon(f"{prefix}.{name}", color="#18202A")
            except Exception:
                continue
            b = QToolButton()
            title = name.replace("-", " ").replace("_", " ")
            if len(title) > 18:
                title = title[:17] + "…"
            b.setText(title)
            b.setIcon(icon)
            b.setIconSize(QSize(36, 36))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setProperty("shapeTile", True)
            b.setFixedSize(92, 78)
            b.setToolTip(f"{label} · {name}")
            b.clicked.connect(partial(_insert_icon, window, prefix, name))
            grid.addWidget(b, rendered // 3, rendered % 3)
            rendered += 1
        total = len(state["matches"])
        shown = min(state["limit"], total)
        count.setText(f"{total:,} objetos encontrados · mostrando {shown:,}".replace(",", "."))
        more.setVisible(shown < total)

    source.currentIndexChanged.connect(lambda _=0: render(True))
    category.currentIndexChanged.connect(lambda _=0: render(True))
    search.textChanged.connect(lambda _="": render(True))
    more.clicked.connect(lambda: (state.__setitem__("limit", state["limit"] + 180), render(False)))
    render(True)
    return page


DECOR_CATEGORIES = ["Marcos", "Separadores", "Sellos", "Cintas", "Esquinas"]
DECOR_COUNT_PER_CATEGORY = 24


def _decor_pixmap(category: str, variant: int, size=QSize(300, 210)):
    from PySide6.QtGui import QPixmap
    pm = QPixmap(size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#111827"), 5)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    w, h = size.width(), size.height()
    pad = 18 + (variant % 4) * 5

    if category == "Marcos":
        radius = 4 + (variant % 6) * 5
        p.drawRoundedRect(pad, pad, w - 2 * pad, h - 2 * pad, radius, radius)
        if variant % 2:
            p.drawRoundedRect(pad + 14, pad + 14, w - 2 * (pad + 14), h - 2 * (pad + 14), max(3, radius - 3), max(3, radius - 3))
        if variant % 3 == 0:
            for x, y in ((pad, pad), (w-pad, pad), (pad, h-pad), (w-pad, h-pad)):
                p.drawEllipse(x-8, y-8, 16, 16)
    elif category == "Separadores":
        y = h // 2
        p.drawLine(24, y, w - 24, y)
        count = 1 + variant % 5
        for i in range(count):
            x = w//2 + (i - (count-1)/2) * 26
            if variant % 3 == 0:
                p.drawEllipse(int(x-6), y-6, 12, 12)
            elif variant % 3 == 1:
                p.drawRect(int(x-6), y-6, 12, 12)
            else:
                p.drawLine(int(x-7), y-7, int(x+7), y+7); p.drawLine(int(x+7), y-7, int(x-7), y+7)
    elif category == "Sellos":
        r = 62 + (variant % 3) * 8
        p.drawEllipse(w//2-r, h//2-r, 2*r, 2*r)
        if variant % 2:
            p.drawEllipse(w//2-r+12, h//2-r+12, 2*(r-12), 2*(r-12))
        spokes = 4 + (variant % 8)
        for i in range(spokes):
            import math
            a = math.radians(i * 360 / spokes)
            x1 = w//2 + int((r-18)*math.cos(a)); y1 = h//2 + int((r-18)*math.sin(a))
            x2 = w//2 + int((r-4)*math.cos(a)); y2 = h//2 + int((r-4)*math.sin(a))
            p.drawLine(x1,y1,x2,y2)
    elif category == "Cintas":
        y1, y2 = 65, h-65
        p.drawRoundedRect(42, y1, w-84, y2-y1, 12, 12)
        tail = 24 + (variant % 4) * 7
        p.drawLine(42, y1+8, 12, y1-tail); p.drawLine(12, y1-tail, 28, h//2); p.drawLine(28, h//2, 12, y2+tail); p.drawLine(12, y2+tail, 42, y2-8)
        p.drawLine(w-42, y1+8, w-12, y1-tail); p.drawLine(w-12, y1-tail, w-28, h//2); p.drawLine(w-28, h//2, w-12, y2+tail); p.drawLine(w-12, y2+tail, w-42, y2-8)
    else:  # Esquinas
        length = 60 + (variant % 5) * 10
        for sx, sy, dx, dy in ((18,18,1,1),(w-18,18,-1,1),(18,h-18,1,-1),(w-18,h-18,-1,-1)):
            p.drawLine(sx, sy, sx+dx*length, sy)
            p.drawLine(sx, sy, sx, sy+dy*length)
            if variant % 2:
                p.drawEllipse(sx-6, sy-6, 12, 12)
    p.end()
    return pm


def _insert_decor(window, category: str, variant: int):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return
    pm = _decor_pixmap(category, variant)
    item = QGraphicsPixmapItem(pm)
    item.setTransformationMode(Qt.SmoothTransformation)
    item.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
    item.setData(1001, "generated-decor")
    item.setData(1002, f"{category}-{variant+1}")
    scale = 0.38
    item.setScale(scale)
    center = view.mapToScene(view.viewport().rect().center())
    br = item.boundingRect()
    item.setPos(center.x() - br.width()*scale/2, center.y() - br.height()*scale/2)
    view.scene().addItem(item)
    item.setSelected(True)


def _build_decor_library(window):
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0,0,0,0)
    outer.setSpacing(9)
    info = QLabel("120 adornos originales generados dentro de Phomemo Studio: marcos, sellos, cintas, separadores y esquinas.")
    info.setWordWrap(True); info.setProperty("muted", True); outer.addWidget(info)
    category = QComboBox(); category.addItems(["Todos"] + DECOR_CATEGORIES); outer.addWidget(category)
    search = QLineEdit(); search.setClearButtonEnabled(True); search.setPlaceholderText("Buscar adorno…"); outer.addWidget(search)
    scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget(); grid = QGridLayout(inner); grid.setContentsMargins(0,4,6,12); grid.setSpacing(8); scroll.setWidget(inner); outer.addWidget(scroll,1)

    def render():
        while grid.count():
            it=grid.takeAt(0); w=it.widget();
            if w is not None: w.deleteLater()
        selected=category.currentText(); query=_norm(search.text()); pos=0
        for cat in DECOR_CATEGORIES:
            if selected != "Todos" and cat != selected: continue
            for variant in range(DECOR_COUNT_PER_CATEGORY):
                label=f"{cat} {variant+1:02d}"
                if query and query not in _norm(label): continue
                b=QToolButton(); b.setText(label); b.setIconSize(QSize(60,42)); b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); b.setProperty("shapeTile",True); b.setFixedSize(92,78)
                from PySide6.QtGui import QIcon
                b.setIcon(QIcon(_decor_pixmap(cat,variant,QSize(90,60))))
                b.clicked.connect(partial(_insert_decor,window,cat,variant))
                grid.addWidget(b,pos//3,pos%3); pos+=1
    category.currentIndexChanged.connect(lambda _=0:render()); search.textChanged.connect(lambda _="":render()); render()
    return page


def _install_expanded_library(window):
    tabs = window.findChild(QTabWidget, "v52OpenLibraryTabs")
    if tabs is None or tabs.property("v53Expanded"):
        return
    tabs.setProperty("v53Expanded", True)
    if tabs.count() >= 2:
        old = tabs.widget(1)
        tabs.removeTab(1)
        old.deleteLater()
    tabs.insertTab(1, _build_massive_library(window), "Objetos")
    tabs.insertTab(2, _build_decor_library(window), "Adornos")
    tabs.setCurrentIndex(1)


# ---------- Live font discovery + searchable typeface selector ----------

def _font_files_state():
    state = {}
    for root in _font_dirs():
        try:
            files = []
            for pattern in ("*.ttf", "*.otf", "*.ttc", "*.otc"):
                files.extend(root.rglob(pattern))
        except Exception:
            continue
        for path in files[:12000]:
            try:
                st = path.stat()
                state[str(path)] = (st.st_mtime_ns, st.st_size)
            except Exception:
                pass
    return state


def _font_combos(window, families):
    famset = set(families)
    result = []
    for combo in window.findChildren(QComboBox):
        try:
            hint = _norm(combo.objectName())
            current = combo.currentText()
            is_font = isinstance(combo, QFontComboBox) or "font" in hint or "fuente" in hint or "tipografia" in hint
            if not is_font and current in famset and combo.count() > 20:
                is_font = True
            if is_font:
                result.append(combo)
        except Exception:
            pass
    return result


def _configure_font_combo(combo, families):
    current = combo.currentText()
    combo.blockSignals(True)
    try:
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setDuplicatesEnabled(False)
        existing = [combo.itemText(i) for i in range(combo.count())]
        if existing != families:
            combo.clear(); combo.addItems(families)
        if current:
            combo.setCurrentText(current)
        line = combo.lineEdit()
        if line is not None:
            line.setPlaceholderText("Escribí para buscar una fuente…")
            line.setClearButtonEnabled(True)
        model = QStringListModel(families, combo)
        completer = QCompleter(model, combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)
        completer.setMaxVisibleItems(18)
        combo.setCompleter(completer)
        combo._v53_font_model = model
        combo._v53_font_completer = completer
        if line is not None and not line.property("v53FontSearchConnected"):
            line.setProperty("v53FontSearchConnected", True)
            line.textEdited.connect(lambda _text, c=completer: c.complete())
    finally:
        combo.blockSignals(False)


def refresh_fonts(window, announce=False):
    before = set(getattr(window, "_v53_families", []))
    families = sorted(QFontDatabase.families(), key=lambda s: s.casefold())
    for combo in _font_combos(window, families):
        _configure_font_combo(combo, families)
    window._v53_families = families
    added = sorted(set(families) - before)
    if announce and added:
        preview = ", ".join(added[:3]) + ("…" if len(added) > 3 else "")
        window.statusBar().showMessage(f"Fuentes actualizadas · {len(added)} nueva(s): {preview}", 7000)
    return families


def _poll_fonts(window):
    new_state = _font_files_state()
    old_state = getattr(window, "_v53_font_state", {})
    changed = [p for p, meta in new_state.items() if old_state.get(p) != meta]
    if changed:
        for path in changed:
            try:
                QFontDatabase.addApplicationFont(path)
            except Exception:
                pass
        window._v53_font_state = new_state
        refresh_fonts(window, announce=True)
        return
    # Some Windows font registrations change the system database before/without
    # a file timestamp that we can observe.  Compare family names as a fallback.
    current = sorted(QFontDatabase.families(), key=lambda s: s.casefold())
    if current != getattr(window, "_v53_families", []):
        refresh_fonts(window, announce=True)


def _install_font_refresh_action(window):
    menu = window.menuBar()
    target = None
    for action in menu.actions():
        if action.menu() and action.text().replace("&", "").lower() in ("ver", "ayuda"):
            target = action.menu(); break
    if target is None:
        return
    target.addSeparator()
    action = target.addAction("Actualizar fuentes ahora")
    action.triggered.connect(lambda: (_poll_fonts(window), refresh_fonts(window, announce=True)))


def _install_live_fonts(window):
    window._v53_font_state = _font_files_state()
    window._v53_families = []
    # Explicitly load any files visible in Windows/user/Adobe font folders.
    for path in window._v53_font_state:
        try:
            QFontDatabase.addApplicationFont(path)
        except Exception:
            pass
    refresh_fonts(window, announce=False)
    timer = QTimer(window)
    timer.setInterval(8000)
    timer.timeout.connect(lambda: _poll_fonts(window))
    timer.start()
    window._v53_font_timer = timer
    _install_font_refresh_action(window)


def enhance(window):
    _install_live_fonts(window)
    _install_expanded_library(window)
    window.statusBar().showMessage("V5.3 · fuentes con búsqueda y actualización automática · biblioteca masiva cargada", 6000)


def install(MainWindow):
    if getattr(MainWindow, "_v53_installed", False):
        return
    MainWindow._v53_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
