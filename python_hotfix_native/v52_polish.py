from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QAbstractSpinBox, QComboBox, QDoubleSpinBox, QGraphicsItem,
    QGraphicsPixmapItem, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QTabWidget, QToolButton, QVBoxLayout,
    QWidget,
)

try:
    import qtawesome as qta
except Exception:
    qta = None

from .studio_pro import _find_canvas


SOURCES = [
    ("fa6s", "Font Awesome"),
    ("mdi6", "Material Design"),
    ("ph", "Phosphor"),
    ("ri", "Remix"),
]

CATEGORY_KEYWORDS = {
    "Todos": (),
    "Hogar": ("house", "home", "bed", "bath", "couch", "door", "key", "lamp", "light", "fan"),
    "Cocina": ("kitchen", "utensil", "fork", "spoon", "knife", "bowl", "plate", "glass", "mug", "coffee", "bottle"),
    "Comida": ("food", "burger", "pizza", "apple", "carrot", "bread", "cake", "cookie", "cheese", "fish", "egg", "lemon"),
    "Animales": ("cat", "dog", "paw", "horse", "fish", "bird", "cow", "frog", "dragon", "otter", "hippo", "spider", "bug"),
    "Naturaleza": ("tree", "leaf", "seedling", "flower", "sun", "moon", "cloud", "rain", "snow", "mountain", "water", "wind"),
    "Trabajo": ("briefcase", "office", "file", "folder", "clipboard", "calendar", "printer", "paperclip", "pen", "pencil", "ruler"),
    "Salud": ("heart", "medical", "hospital", "stethoscope", "pill", "syringe", "bandage", "virus", "tooth", "brain", "eye"),
    "Comercio": ("store", "shop", "cart", "basket", "tag", "receipt", "cash", "wallet", "credit", "barcode", "box", "package"),
    "Transporte": ("car", "truck", "bus", "train", "plane", "ship", "bicycle", "motorcycle", "taxi", "road", "gas", "parking"),
    "Tecnología": ("computer", "laptop", "mobile", "phone", "wifi", "bluetooth", "usb", "keyboard", "mouse", "camera", "microchip", "battery"),
    "Comunicación": ("message", "comment", "chat", "envelope", "mail", "phone", "bell", "bullhorn", "microphone", "share", "at"),
    "Seguridad": ("lock", "shield", "key", "warning", "triangle", "fire", "helmet", "eye", "ban", "circle-x", "check"),
    "Fiestas": ("gift", "cake", "party", "balloon", "champagne", "star", "snowman", "tree", "heart", "music", "confetti"),
}

SPANISH_ALIASES = {
    "casa": "house home", "hogar": "house home", "cocina": "kitchen utensil",
    "comida": "food", "perro": "dog", "gato": "cat", "animal": "paw",
    "planta": "leaf flower tree", "flor": "flower", "arbol": "tree",
    "salud": "medical hospital", "medico": "medical doctor", "corazon": "heart",
    "tienda": "store shop", "carrito": "cart", "precio": "tag receipt",
    "auto": "car", "coche": "car", "avion": "plane", "camion": "truck",
    "telefono": "phone mobile", "computadora": "computer laptop", "wifi": "wifi",
    "mensaje": "message comment chat", "correo": "mail envelope",
    "candado": "lock", "seguridad": "shield lock", "alerta": "warning",
    "regalo": "gift", "cumpleanos": "cake gift", "navidad": "tree snowman gift",
}


def _norm(text: str) -> str:
    return " ".join((text or "").lower().replace("-", " ").replace("_", " ").split())


def _catalog_for(prefix: str):
    if qta is None:
        return []
    try:
        inst = qta._instance()
        cmap = getattr(inst, "charmap", {}).get(prefix, {})
        return sorted(cmap.keys())
    except Exception:
        return []


def open_catalog_size() -> int:
    return sum(len(_catalog_for(prefix)) for prefix, _ in SOURCES)


def _insert_open_icon(window, prefix: str, name: str):
    if qta is None:
        return
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return
    try:
        icon = qta.icon(f"{prefix}.{name}", color="#111827")
        pm = icon.pixmap(QSize(240, 240))
    except Exception:
        return
    item = QGraphicsPixmapItem(pm)
    item.setTransformationMode(Qt.SmoothTransformation)
    item.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
    item.setData(1001, "open-icon")
    item.setData(1002, f"{prefix}.{name}")
    scale = 0.42
    item.setScale(scale)
    center = view.mapToScene(view.viewport().rect().center())
    br = item.boundingRect()
    item.setPos(center.x() - br.width() * scale / 2, center.y() - br.height() * scale / 2)
    view.scene().addItem(item)
    item.setSelected(True)


def _matches_category(name: str, category: str) -> bool:
    words = CATEGORY_KEYWORDS.get(category, ())
    if not words:
        return True
    n = _norm(name)
    return any(word in n for word in words)


def _expanded_query(text: str) -> list[str]:
    q = _norm(text)
    if not q:
        return []
    words = q.split()
    expanded = list(words)
    for w in words:
        if w in SPANISH_ALIASES:
            expanded.extend(SPANISH_ALIASES[w].split())
    return list(dict.fromkeys(expanded))


def _build_open_library(window):
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(10)

    info = QLabel("Biblioteca abierta: miles de iconos reutilizables de colecciones con licencia abierta.")
    info.setWordWrap(True)
    info.setProperty("muted", True)
    outer.addWidget(info)

    filters = QHBoxLayout()
    source = QComboBox()
    source.setObjectName("v52IconSource")
    source.addItem("Todas las colecciones", "*")
    for prefix, label in SOURCES:
        source.addItem(label, prefix)
    category = QComboBox()
    category.setObjectName("v52IconCategory")
    category.addItems(list(CATEGORY_KEYWORDS.keys()))
    filters.addWidget(source, 1)
    filters.addWidget(category, 1)
    outer.addLayout(filters)

    search = QLineEdit()
    search.setObjectName("v52IconSearch")
    search.setPlaceholderText("Buscar iconos: casa, comida, salud, auto, regalo…")
    outer.addWidget(search)

    count = QLabel()
    count.setObjectName("v52IconCount")
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

    more = QPushButton("Mostrar más")
    more.setObjectName("v52LoadMore")
    more.setProperty("role", "secondary")
    outer.addWidget(more)

    state = {"limit": 120, "matches": []}

    def clear_grid():
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def build_matches():
        selected_prefix = source.currentData()
        selected_category = category.currentText()
        query_terms = _expanded_query(search.text())
        matches = []
        for prefix, label in SOURCES:
            if selected_prefix != "*" and selected_prefix != prefix:
                continue
            for name in _catalog_for(prefix):
                if not _matches_category(name, selected_category):
                    continue
                normalized = _norm(name)
                if query_terms and not any(term in normalized for term in query_terms):
                    continue
                matches.append((prefix, label, name))
        return matches

    def render(reset=True):
        if reset:
            state["limit"] = 120
            state["matches"] = build_matches()
        clear_grid()
        subset = state["matches"][: state["limit"]]
        for i, (prefix, label, name) in enumerate(subset):
            b = QToolButton()
            title = name.replace("-", " ").replace("_", " ")
            if len(title) > 17:
                title = title[:16] + "…"
            b.setText(title)
            try:
                b.setIcon(qta.icon(f"{prefix}.{name}", color="#18202A"))
            except Exception:
                continue
            b.setIconSize(QSize(34, 34))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setProperty("shapeTile", True)
            b.setFixedSize(92, 76)
            b.setToolTip(f"{label}: {name}")
            b.clicked.connect(partial(_insert_open_icon, window, prefix, name))
            grid.addWidget(b, i // 3, i % 3)
        total = len(state["matches"])
        shown = min(state["limit"], total)
        count.setText(f"{total:,} recursos encontrados · mostrando {shown:,}".replace(",", "."))
        more.setVisible(shown < total)

    def load_more():
        state["limit"] += 120
        render(False)

    source.currentIndexChanged.connect(lambda _=0: render(True))
    category.currentIndexChanged.connect(lambda _=0: render(True))
    search.textChanged.connect(lambda _="": render(True))
    more.clicked.connect(load_more)
    render(True)
    return page


def _install_library_tabs(window):
    pages = getattr(window, "_v51_drawer_pages", {})
    shape_page = pages.get("Formas")
    if shape_page is None or shape_page.findChild(QTabWidget, "v52OpenLibraryTabs") is not None:
        return
    old_layout = shape_page.layout()
    if old_layout is None:
        return

    shapes_tab = QWidget()
    shapes_layout = QVBoxLayout(shapes_tab)
    shapes_layout.setContentsMargins(0, 0, 0, 0)
    shapes_layout.setSpacing(10)
    while old_layout.count():
        item = old_layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(shapes_tab)
            shapes_layout.addWidget(w)

    tabs = QTabWidget()
    tabs.setObjectName("v52OpenLibraryTabs")
    tabs.addTab(shapes_tab, "Formas")
    tabs.addTab(_build_open_library(window), "Iconos")
    old_layout.addWidget(tabs)


def _all_spinboxes(window):
    return list(window.findChildren(QSpinBox)) + list(window.findChildren(QDoubleSpinBox))


def _modernize_numeric_controls(window):
    for spin in _all_spinboxes(window):
        try:
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
            spin.setProperty("modernStepper", True)
            spin.setMinimumHeight(36)
        except Exception:
            pass

    extra = '''
    QSpinBox[modernStepper="true"], QDoubleSpinBox[modernStepper="true"] {
        background:#FFFFFF; border:1px solid #D9E0EA; border-radius:10px;
        padding:6px 58px 6px 10px; min-height:24px;
    }
    QSpinBox[modernStepper="true"]:focus, QDoubleSpinBox[modernStepper="true"]:focus {
        border:1px solid #7668F6;
    }
    QSpinBox[modernStepper="true"]::up-button, QDoubleSpinBox[modernStepper="true"]::up-button {
        subcontrol-origin:border; subcontrol-position:top right;
        width:27px; height:17px; background:#F4F2FF;
        border-left:1px solid #E2DFFE; border-bottom:1px solid #E2DFFE;
        border-top-right-radius:9px;
    }
    QSpinBox[modernStepper="true"]::down-button, QDoubleSpinBox[modernStepper="true"]::down-button {
        subcontrol-origin:border; subcontrol-position:bottom right;
        width:27px; height:17px; background:#F8F9FC;
        border-left:1px solid #E3E7EE; border-bottom-right-radius:9px;
    }
    QSpinBox[modernStepper="true"]::up-button:hover, QDoubleSpinBox[modernStepper="true"]::up-button:hover,
    QSpinBox[modernStepper="true"]::down-button:hover, QDoubleSpinBox[modernStepper="true"]::down-button:hover {
        background:#EDE9FE;
    }
    QTabWidget#v52OpenLibraryTabs::pane { border:0; background:transparent; }
    QTabWidget#v52OpenLibraryTabs QTabBar::tab {
        background:#EEF1F6; color:#596579; padding:8px 16px; margin-right:6px;
        border-radius:9px; font-weight:600;
    }
    QTabWidget#v52OpenLibraryTabs QTabBar::tab:selected {
        background:#6657F4; color:white;
    }
    '''
    window.setStyleSheet(window.styleSheet() + extra)


def enhance(window):
    _modernize_numeric_controls(window)
    _install_library_tabs(window)


def install(MainWindow):
    if getattr(MainWindow, "_v52_polish_installed", False):
        return
    MainWindow._v52_polish_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
