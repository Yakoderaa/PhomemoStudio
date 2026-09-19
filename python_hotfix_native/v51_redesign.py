from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, QSize, QSettings
from PySide6.QtGui import QAction, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication, QAbstractButton, QComboBox, QDockWidget, QFormLayout, QFrame,
    QGraphicsView, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QSlider, QSpinBox, QDoubleSpinBox, QStackedWidget, QToolBar,
    QToolButton, QVBoxLayout, QWidget,
)

from .studio_pro import (
    SHAPES, _asset, _find_canvas, _shape_icon, _start_update_check,
    _taskbar_identity, insert_shape, load_all_fonts,
)


ACCENT = "#6657F4"
TEXT = "#18202A"
MUTED = "#687386"
SURFACE = "#FFFFFF"
WORKSPACE = "#EEF1F6"
BORDER = "#DDE3EC"
RAIL = "#171B24"


def _norm(value: str) -> str:
    return " ".join((value or "").replace("&", "").replace(":", "").lower().split())


def _safe_disconnect(button):
    try:
        button.clicked.disconnect()
    except Exception:
        pass


def _ancestor_group(widget):
    p = widget.parentWidget() if widget else None
    while p is not None:
        if isinstance(p, QGroupBox):
            return p
        p = p.parentWidget()
    return None


def _button_text(button) -> str:
    try:
        return _norm(button.text())
    except Exception:
        return ""


def _find_legacy_button(window, *tokens):
    tokens = [_norm(t) for t in tokens if t]
    for button in getattr(window, "_v51_legacy_buttons", []):
        text = _button_text(button)
        if tokens and all(t in text for t in tokens):
            return button
    if len(tokens) > 1:
        for button in getattr(window, "_v51_legacy_buttons", []):
            text = _button_text(button)
            if any(t in text for t in tokens):
                return button
    return None


def _call_first(window, names):
    for name in names:
        fn = getattr(window, name, None)
        if callable(fn):
            return fn
    return None


def _proxy_button(window, label, *, tokens=(), methods=(), primary=False, compact=False):
    button = QPushButton(label)
    if primary:
        button.setProperty("role", "primary")
    if compact:
        button.setProperty("density", "compact")
    old = _find_legacy_button(window, *tokens) if tokens else None
    fn = _call_first(window, methods)
    if old is not None:
        button.clicked.connect(old.click)
    elif fn is not None:
        button.clicked.connect(fn)
    else:
        button.setEnabled(False)
        button.setToolTip("Esta acción no está disponible en este documento.")
    return button


def _icon_button(text, tooltip=""):
    b = QToolButton()
    b.setText(text)
    b.setToolTip(tooltip or text)
    b.setProperty("nav", True)
    b.setToolButtonStyle(Qt.ToolButtonTextOnly)
    b.setFixedSize(48, 44)
    return b


def _section(title: str, subtitle: str = ""):
    card = QFrame()
    card.setProperty("card", True)
    outer = QVBoxLayout(card)
    outer.setContentsMargins(16, 14, 16, 16)
    outer.setSpacing(10)
    t = QLabel(title)
    t.setProperty("sectionTitle", True)
    outer.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setWordWrap(True)
        s.setProperty("muted", True)
        outer.addWidget(s)
    return card, outer


def _field_for_label(window, captions, used):
    wanted = {_norm(x) for x in captions}
    for label in getattr(window, "_v51_legacy_labels", []):
        if _norm(label.text()) not in wanted:
            continue
        parent = label.parentWidget()
        layout = parent.layout() if parent else None
        if isinstance(layout, QFormLayout):
            for row in range(layout.rowCount()):
                li = layout.itemAt(row, QFormLayout.LabelRole)
                fi = layout.itemAt(row, QFormLayout.FieldRole)
                if li and li.widget() is label and fi and fi.widget() is not None:
                    w = fi.widget()
                    if id(w) not in used:
                        used.add(id(w))
                        return w
        # Fall back to nearby widgets in the same parent.
        if parent:
            for w in parent.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
                if w is label or isinstance(w, QLabel) or id(w) in used:
                    continue
                if isinstance(w, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QAbstractButton, QSlider)):
                    used.add(id(w))
                    return w
    return None


def _take_attr(window, name, used):
    w = getattr(window, name, None)
    if isinstance(w, QWidget) and id(w) not in used:
        used.add(id(w))
        return w
    return None


def _prepare_field(widget):
    if widget is None:
        return None
    widget.setVisible(True)
    widget.setEnabled(True)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    widget.setMinimumWidth(150)
    if isinstance(widget, QComboBox):
        widget.setMinimumContentsLength(12)
    return widget


def _add_form_row(form, caption, widget):
    widget = _prepare_field(widget)
    if widget is not None:
        form.addRow(caption, widget)
        return True
    return False


def _build_text_inspector(window, parent_layout, used):
    card, lay = _section("Texto", "Propiedades tipográficas del elemento seleccionado.")
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(10)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

    rows = [
        ("Contenido", ("Texto", "Contenido")),
        ("Fuente", ("Fuente", "Tipografía")),
        ("Tamaño", ("Tamaño", "Tamaño de fuente")),
        ("Grosor", ("Grosor", "Peso")),
        ("Alineación", ("Alineación", "Alinear")),
        ("Espaciado", ("Espaciado", "Tracking")),
        ("Interlineado", ("Interlineado",)),
    ]
    count = 0
    for caption, names in rows:
        count += int(_add_form_row(form, caption, _field_for_label(window, names, used)))

    # Common attribute names across the older editor builds.
    attrs = [
        ("Contenido", ("text_edit", "text_input", "text_value")),
        ("Fuente", ("font_combo", "font_family", "font_box")),
        ("Tamaño", ("font_size", "font_size_spin", "text_size")),
        ("Grosor", ("font_weight", "weight_combo", "font_weight_combo")),
    ]
    for caption, candidates in attrs:
        if any(_norm(caption) == _norm(form.itemAt(i, QFormLayout.LabelRole).widget().text())
               for i in range(form.rowCount()) if form.itemAt(i, QFormLayout.LabelRole)):
            continue
        w = None
        for name in candidates:
            w = _take_attr(window, name, used)
            if w:
                break
        count += int(_add_form_row(form, caption, w))

    if count:
        lay.addLayout(form)
    else:
        info = QLabel("Seleccioná un texto en el lienzo para ver sus controles. Los controles originales siguen conectados al editor y aparecen aquí cuando están disponibles.")
        info.setWordWrap(True)
        info.setProperty("muted", True)
        lay.addWidget(info)
    parent_layout.addWidget(card)


def _build_transform_inspector(window, parent_layout, used):
    card, lay = _section("Posición y transformación")
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(10)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    count = 0
    for caption, names in [
        ("X", ("X", "Posición X")), ("Y", ("Y", "Posición Y")),
        ("Ancho", ("Ancho", "Width")), ("Alto", ("Alto", "Height")),
        ("Rotación", ("Rotación", "Ángulo")), ("Opacidad", ("Opacidad",)),
    ]:
        count += int(_add_form_row(form, caption, _field_for_label(window, names, used)))
    if count:
        lay.addLayout(form)
    else:
        hint = QLabel("Mover, redimensionar y rotar se mantienen disponibles directamente desde el lienzo.")
        hint.setWordWrap(True)
        hint.setProperty("muted", True)
        lay.addWidget(hint)
    parent_layout.addWidget(card)


def _build_document_inspector(window, parent_layout, used):
    card, lay = _section("Etiqueta", "Documento y rollo de la D30.")
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(10)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

    size = _take_attr(window, "size_combo", used)
    if size:
        _add_form_row(form, "Formato", size)
    roll_name = _take_attr(window, "roll_name", used)
    if roll_name:
        _add_form_row(form, "Rollo", roll_name)
    total = _take_attr(window, "roll_total", used)
    if total:
        _add_form_row(form, "Inicial", total)
    remaining = _take_attr(window, "roll_remaining", used)
    if remaining:
        _add_form_row(form, "Restantes", remaining)
    usable = _take_attr(window, "roll_usable", used)
    if usable:
        usable.setMinimumWidth(80)
        _add_form_row(form, "Utilizables", usable)
    if form.rowCount():
        lay.addLayout(form)

    cal = _take_attr(window, "calibrate_btn", used)
    if cal:
        cal.setText("Calibrar D30 / rollo")
        cal.setProperty("role", "secondary")
        lay.addWidget(cal)
    else:
        lay.addWidget(_proxy_button(window, "Calibrar D30 / rollo", tokens=("calibrar",), methods=("calibrate",)))
    parent_layout.addWidget(card)


def _build_printer_card(window, parent_layout, used):
    card, lay = _section("Impresora")
    conn = _take_attr(window, "conn", used)
    if conn:
        conn.setWordWrap(True)
        conn.setProperty("connection", True)
        lay.addWidget(conn)
    chips = QHBoxLayout()
    chips.setSpacing(8)
    for name in ("battery", "paper", "roll_status"):
        w = _take_attr(window, name, used)
        if w:
            w.setProperty("chip", True)
            chips.addWidget(w)
    chips.addStretch(1)
    lay.addLayout(chips)
    connect = _take_attr(window, "connect_btn", used)
    if connect:
        connect.setProperty("role", "primary")
        lay.addWidget(connect)
    parent_layout.addWidget(card)


def _shape_categories():
    return {
        "Básicas": ["Rectángulo", "Rectángulo redondeado", "Círculo", "Elipse", "Triángulo", "Triángulo invertido", "Rombo", "Cápsula", "Anillo", "Marco"],
        "Polígonos y estrellas": ["Pentágono", "Hexágono", "Octágono", "Decágono", "Estrella 4", "Estrella 5", "Estrella 6", "Estrella 8", "Estrella 12", "Explosión"],
        "Flechas": ["Flecha derecha", "Flecha izquierda", "Flecha arriba", "Flecha abajo", "Chevrón"],
        "Etiquetas": ["Etiqueta", "Ticket", "Banderín", "Cinta", "Marcador", "Escudo", "Burbuja"],
        "Orgánicas": ["Corazón", "Nube", "Gota", "Luna", "Flor", "Onda"],
        "Símbolos": ["Rayo", "Cruz", "Casa", "Reloj de arena"],
    }


def _build_shapes_page(window):
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(10)
    search = QLineEdit()
    search.setPlaceholderText("Buscar entre todas las formas…")
    search.setObjectName("v51ShapeSearch")
    outer.addWidget(search)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget()
    body = QVBoxLayout(inner)
    body.setContentsMargins(0, 4, 6, 12)
    body.setSpacing(14)
    buttons = []
    known = set()

    for category, names in _shape_categories().items():
        names = [n for n in names if n in SHAPES]
        if not names:
            continue
        known.update(names)
        heading = QLabel(category)
        heading.setProperty("drawerHeading", True)
        body.addWidget(heading)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for i, name in enumerate(names):
            b = QToolButton()
            b.setText(name)
            b.setIcon(_shape_icon(name))
            b.setIconSize(QSize(48, 38))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setProperty("shapeTile", True)
            b.setFixedSize(92, 76)
            b.clicked.connect(partial(insert_shape, window, name))
            grid.addWidget(b, i // 3, i % 3)
            buttons.append((b, name, heading, grid_host))
        body.addWidget(grid_host)

    extras = [n for n in SHAPES if n not in known]
    if extras:
        heading = QLabel("Más")
        heading.setProperty("drawerHeading", True)
        body.addWidget(heading)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, name in enumerate(extras):
            b = QToolButton()
            b.setText(name)
            b.setIcon(_shape_icon(name))
            b.setIconSize(QSize(48, 38))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setProperty("shapeTile", True)
            b.setFixedSize(92, 76)
            b.clicked.connect(partial(insert_shape, window, name))
            grid.addWidget(b, i // 3, i % 3)
            buttons.append((b, name, heading, grid_host))
        body.addWidget(grid_host)

    body.addStretch(1)
    scroll.setWidget(inner)
    outer.addWidget(scroll, 1)

    def filter_shapes(text):
        query = _norm(text)
        groups = {}
        for button, name, heading, host in buttons:
            visible = not query or query in _norm(name)
            button.setVisible(visible)
            groups.setdefault((heading, host), False)
            groups[(heading, host)] = groups[(heading, host)] or visible
        for (heading, host), visible in groups.items():
            heading.setVisible(visible)
            host.setVisible(visible)

    search.textChanged.connect(filter_shapes)
    return page


def _find_group(window, tokens, exclude=()):
    tokens = [_norm(t) for t in tokens]
    exclude = [_norm(t) for t in exclude]
    for group in getattr(window, "_v51_legacy_groups", []):
        title = _norm(group.title())
        if any(x in title for x in exclude):
            continue
        if any(t in title for t in tokens):
            return group
    return None


def _drawer_info(title, text):
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(0, 0, 0, 0)
    card, cl = _section(title)
    desc = QLabel(text)
    desc.setWordWrap(True)
    desc.setProperty("muted", True)
    cl.addWidget(desc)
    lay.addWidget(card)
    lay.addStretch(1)
    return page, lay


def _build_designs_page(window):
    page, lay = _drawer_info("Diseños", "Guardá, duplicá y reutilizá tus etiquetas sin llenar el área de trabajo de controles.")
    group = _find_group(window, ("biblioteca", "plantilla", "diseño"), exclude=("forma",))
    if group:
        group.setParent(page)
        group.setVisible(True)
        lay.insertWidget(0, group)
    row = QHBoxLayout()
    row.addWidget(_proxy_button(window, "Guardar", tokens=("guardar",), methods=("save_template",)))
    row.addWidget(_proxy_button(window, "Duplicar", tokens=("duplicar",), methods=("duplicate_template",)))
    lay.insertLayout(max(0, lay.count() - 1), row)
    return page


def _build_text_page(window):
    page, lay = _drawer_info("Texto", "Agregá texto y después ajustalo desde Propiedades. La lista completa de fuentes instaladas en Windows y Adobe se carga al iniciar.")
    add = _proxy_button(window, "Añadir texto", tokens=("texto",), methods=("add_text", "insert_text", "new_text"), primary=True)
    lay.insertWidget(max(0, lay.count() - 1), add)
    return page


def _build_images_page(window):
    page, lay = _drawer_info("Imágenes", "Insertá recursos gráficos y exportá el resultado terminado.")
    for label, tokens, methods in [
        ("Insertar imagen", ("imagen",), ("add_image", "insert_image", "open_image")),
        ("Insertar SVG", ("svg",), ("add_svg", "insert_svg")),
        ("Exportar PNG", ("png",), ("export_png",)),
    ]:
        lay.insertWidget(max(0, lay.count() - 1), _proxy_button(window, label, tokens=tokens, methods=methods, primary=label == "Insertar imagen"))
    return page


def _build_queue_page(window):
    page, lay = _drawer_info("Cola de impresión", "Prepará varias etiquetas y mandalas a la D30 en una sola sesión.")
    group = _find_group(window, ("cola", "queue"))
    if group:
        group.setParent(page)
        group.setVisible(True)
        lay.insertWidget(0, group)
    else:
        for label, tokens, methods in [
            ("Añadir a cola", ("cola",), ("add_to_queue",)),
            ("Imprimir cola", ("imprimir", "cola"), ("print_queue",)),
        ]:
            lay.insertWidget(max(0, lay.count() - 1), _proxy_button(window, label, tokens=tokens, methods=methods, primary="Imprimir" in label))
    return page


def _build_drawer(window):
    drawer = QFrame()
    drawer.setObjectName("v51Drawer")
    drawer.setFixedWidth(326)
    layout = QVBoxLayout(drawer)
    layout.setContentsMargins(18, 18, 14, 18)
    layout.setSpacing(12)

    head = QHBoxLayout()
    title = QLabel("Diseños")
    title.setObjectName("v51DrawerTitle")
    close = QToolButton()
    close.setText("×")
    close.setToolTip("Ocultar panel")
    close.setObjectName("v51DrawerClose")
    close.setFixedSize(30, 30)
    head.addWidget(title)
    head.addStretch(1)
    head.addWidget(close)
    layout.addLayout(head)

    stack = QStackedWidget()
    stack.setObjectName("v51DrawerStack")
    pages = {
        "Diseños": _build_designs_page(window),
        "Texto": _build_text_page(window),
        "Formas": _build_shapes_page(window),
        "Imágenes": _build_images_page(window),
        "Cola": _build_queue_page(window),
    }
    for page in pages.values():
        stack.addWidget(page)
    layout.addWidget(stack, 1)

    def show_page(name):
        page = pages[name]
        title.setText(name)
        stack.setCurrentWidget(page)
        drawer.show()
        window._v51_current_drawer = name
        QSettings("Yakoderaa", "PhomemoStudio").setValue("ui/drawerPage", name)
        QSettings("Yakoderaa", "PhomemoStudio").setValue("ui/drawerVisible", True)

    def hide_drawer():
        drawer.hide()
        QSettings("Yakoderaa", "PhomemoStudio").setValue("ui/drawerVisible", False)

    close.clicked.connect(hide_drawer)
    window._v51_show_drawer = show_page
    window._v51_hide_drawer = hide_drawer
    window._v51_drawer_pages = pages
    return drawer


def _build_rail(window):
    rail = QFrame()
    rail.setObjectName("v51Rail")
    rail.setFixedWidth(76)
    lay = QVBoxLayout(rail)
    lay.setContentsMargins(12, 14, 12, 14)
    lay.setSpacing(8)

    icon = _asset("sr-gato.png") or _asset("sr-gato.ico")
    logo = QLabel()
    logo.setObjectName("v51RailLogo")
    logo.setFixedSize(48, 48)
    logo.setAlignment(Qt.AlignCenter)
    if icon:
        logo.setPixmap(QIcon(str(icon)).pixmap(QSize(38, 38)))
    else:
        logo.setText("PS")
    lay.addWidget(logo)
    lay.addSpacing(12)

    buttons = {}
    for symbol, name in [("⌂", "Diseños"), ("T", "Texto"), ("◇", "Formas"), ("▧", "Imágenes"), ("≡", "Cola")]:
        b = _icon_button(symbol, name)
        b.setObjectName("v51Nav" + name.replace("á", "a"))
        b.clicked.connect(lambda _=False, n=name: window._v51_show_drawer(n))
        lay.addWidget(b, 0, Qt.AlignHCenter)
        caption = QLabel(name)
        caption.setProperty("railCaption", True)
        caption.setAlignment(Qt.AlignCenter)
        lay.addWidget(caption)
        buttons[name] = b
    lay.addStretch(1)
    window._v51_nav_buttons = buttons
    return rail


def _build_header(window, used):
    header = QFrame()
    header.setObjectName("v51Header")
    header.setFixedHeight(68)
    lay = QHBoxLayout(header)
    lay.setContentsMargins(20, 10, 18, 10)
    lay.setSpacing(10)

    brand = QVBoxLayout()
    title = QLabel("Phomemo Studio")
    title.setObjectName("v51Brand")
    subtitle = QLabel("Editor de etiquetas · D30")
    subtitle.setProperty("muted", True)
    brand.addWidget(title)
    brand.addWidget(subtitle)
    lay.addLayout(brand)
    lay.addSpacing(14)

    for label, tokens, methods in [
        ("Guardar", ("guardar",), ("save_template",)),
        ("Duplicar", ("duplicar",), ("duplicate_template",)),
        ("PNG", ("png",), ("export_png",)),
    ]:
        lay.addWidget(_proxy_button(window, label, tokens=tokens, methods=methods, compact=True))

    lay.addStretch(1)

    progress = _take_attr(window, "progress", used)
    if progress:
        progress.setFixedWidth(130)
        lay.addWidget(progress)

    upd = QPushButton("Actualizar")
    upd.setObjectName("v51UpdateButton")
    upd.clicked.connect(lambda: _start_update_check(window))
    lay.addWidget(upd)

    print_button = _proxy_button(window, "Imprimir", tokens=("imprimir", "actual"), methods=("print_current",), primary=True)
    print_button.setObjectName("v51PrintButton")
    lay.addWidget(print_button)
    return header


def _zoom_set(view, percent, label):
    percent = max(25, min(400, int(percent)))
    view.resetTransform()
    scale = percent / 100.0
    view.scale(scale, scale)
    label.setText(f"{percent}%")


def _build_stage(window, canvas, used):
    stage = QFrame()
    stage.setObjectName("v51Stage")
    outer = QVBoxLayout(stage)
    outer.setContentsMargins(18, 14, 18, 18)
    outer.setSpacing(10)

    bar = QFrame()
    bar.setObjectName("v51CanvasBar")
    row = QHBoxLayout(bar)
    row.setContentsMargins(12, 7, 12, 7)
    row.setSpacing(8)
    doc = QLabel("Lienzo")
    doc.setProperty("canvasTitle", True)
    row.addWidget(doc)
    row.addStretch(1)

    cal = _proxy_button(window, "Calibrar", tokens=("calibrar",), methods=("calibrate",), compact=True)
    row.addWidget(cal)
    reset = QPushButton("100%")
    reset.setProperty("density", "compact")
    minus = QToolButton(); minus.setText("−"); minus.setFixedSize(30, 30)
    plus = QToolButton(); plus.setText("+"); plus.setFixedSize(30, 30)
    zoom_label = QLabel("100%")
    zoom_label.setObjectName("v51ZoomLabel")
    zoom_label.setFixedWidth(44)
    zoom_label.setAlignment(Qt.AlignCenter)
    row.addWidget(minus); row.addWidget(zoom_label); row.addWidget(plus); row.addWidget(reset)
    outer.addWidget(bar)

    canvas_host = QFrame()
    canvas_host.setObjectName("v51CanvasHost")
    canvas_lay = QVBoxLayout(canvas_host)
    canvas_lay.setContentsMargins(24, 24, 24, 24)
    canvas.setParent(canvas_host)
    canvas.setVisible(True)
    canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    canvas_lay.addWidget(canvas, 1)
    outer.addWidget(canvas_host, 1)

    state = {"zoom": 100}
    def delta(amount):
        state["zoom"] = max(25, min(400, state["zoom"] + amount))
        _zoom_set(canvas, state["zoom"], zoom_label)
    minus.clicked.connect(lambda: delta(-10))
    plus.clicked.connect(lambda: delta(10))
    reset.clicked.connect(lambda: (state.update(zoom=100), _zoom_set(canvas, 100, zoom_label)))
    return stage


def _build_inspector(window, used):
    inspector = QFrame()
    inspector.setObjectName("v51Inspector")
    inspector.setMinimumWidth(330)
    inspector.setMaximumWidth(390)
    outer = QVBoxLayout(inspector)
    outer.setContentsMargins(12, 14, 14, 14)
    outer.setSpacing(10)

    head = QHBoxLayout()
    title = QLabel("Propiedades")
    title.setObjectName("v51InspectorTitle")
    hide = QToolButton(); hide.setText("›"); hide.setToolTip("Ocultar propiedades"); hide.setFixedSize(30, 30)
    head.addWidget(title); head.addStretch(1); head.addWidget(hide)
    outer.addLayout(head)

    scroll = QScrollArea()
    scroll.setObjectName("v51InspectorScroll")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    body = QWidget()
    lay = QVBoxLayout(body)
    lay.setContentsMargins(0, 0, 4, 14)
    lay.setSpacing(12)

    _build_text_inspector(window, lay, used)
    _build_transform_inspector(window, lay, used)
    _build_document_inspector(window, lay, used)
    _build_printer_card(window, lay, used)
    lay.addStretch(1)
    scroll.setWidget(body)
    outer.addWidget(scroll, 1)

    hide.clicked.connect(lambda: _set_inspector_visible(window, False))
    return inspector


def _set_inspector_visible(window, visible):
    inspector = getattr(window, "_v51_inspector", None)
    if inspector:
        inspector.setVisible(bool(visible))
        QSettings("Yakoderaa", "PhomemoStudio").setValue("ui/inspectorVisible", bool(visible))


def _reset_panels(window):
    window._v51_show_drawer("Formas")
    _set_inspector_visible(window, True)


def _rebuild_menus(window):
    menu = window.menuBar()
    menu.clear()

    archivo = menu.addMenu("Archivo")
    for title, tokens, methods in [
        ("Guardar diseño", ("guardar",), ("save_template",)),
        ("Duplicar diseño", ("duplicar",), ("duplicate_template",)),
        ("Exportar PNG", ("png",), ("export_png",)),
    ]:
        a = QAction(title, window)
        old = _find_legacy_button(window, *tokens)
        fn = _call_first(window, methods)
        if old: a.triggered.connect(old.click)
        elif fn: a.triggered.connect(fn)
        else: a.setEnabled(False)
        archivo.addAction(a)

    insertar = menu.addMenu("Insertar")
    actions = [
        ("Texto", "Texto"), ("Formas…", "Formas"), ("Imagen…", "Imágenes")
    ]
    for title, page in actions:
        a = QAction(title, window)
        a.triggered.connect(lambda _=False, p=page: window._v51_show_drawer(p))
        insertar.addAction(a)

    ver = menu.addMenu("Ver")
    for title, page in [("Diseños", "Diseños"), ("Biblioteca de formas", "Formas"), ("Imágenes", "Imágenes"), ("Cola de impresión", "Cola")]:
        a = QAction(title, window)
        a.triggered.connect(lambda _=False, p=page: window._v51_show_drawer(p))
        ver.addAction(a)
    ver.addSeparator()
    props = QAction("Mostrar propiedades", window)
    props.triggered.connect(lambda: _set_inspector_visible(window, True))
    ver.addAction(props)
    reset = QAction("Restablecer paneles", window)
    reset.triggered.connect(lambda: _reset_panels(window))
    ver.addAction(reset)

    impresora = menu.addMenu("Impresora")
    connect = QAction("Conectar / desconectar D30", window)
    old = getattr(window, "connect_btn", None)
    if isinstance(old, QAbstractButton): connect.triggered.connect(old.click)
    else:
        fn = _call_first(window, ("toggle_connect",))
        if fn: connect.triggered.connect(fn)
    impresora.addAction(connect)
    cal = QAction("Calibrar D30 / rollo", window)
    fn = _call_first(window, ("calibrate",))
    if fn: cal.triggered.connect(fn)
    impresora.addAction(cal)
    pr = QAction("Imprimir etiqueta", window)
    fn = _call_first(window, ("print_current",))
    if fn: pr.triggered.connect(fn)
    impresora.addAction(pr)

    ayuda = menu.addMenu("Ayuda")
    upd = QAction("Buscar actualizaciones", window)
    upd.triggered.connect(lambda: _start_update_check(window))
    ayuda.addAction(upd)


def _apply_style(window):
    window.setMinimumSize(1260, 780)
    window.setStyleSheet(f'''
    QMainWindow {{ background:{WORKSPACE}; color:{TEXT}; }}
    QWidget {{ font-family:"Segoe UI Variable","Segoe UI"; font-size:12px; color:{TEXT}; }}
    QMenuBar {{ background:{SURFACE}; border-bottom:1px solid {BORDER}; padding:3px 8px; }}
    QMenuBar::item {{ padding:6px 9px; border-radius:6px; }}
    QMenuBar::item:selected {{ background:#F0F2F7; }}
    QMenu {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:8px; padding:5px; }}
    QMenu::item {{ padding:7px 24px 7px 12px; border-radius:5px; }}
    QMenu::item:selected {{ background:#F0EEFF; color:#5143D9; }}
    QStatusBar {{ background:{SURFACE}; border-top:1px solid {BORDER}; color:{MUTED}; min-height:24px; }}
    QFrame#v51Header {{ background:{SURFACE}; border-bottom:1px solid {BORDER}; }}
    QLabel#v51Brand {{ font-size:17px; font-weight:700; }}
    QFrame#v51Rail {{ background:{RAIL}; border:0; }}
    QLabel#v51RailLogo {{ color:white; font-size:16px; font-weight:700; }}
    QToolButton[nav="true"] {{ color:#E7EAF0; background:transparent; border:1px solid transparent; border-radius:12px; font-size:21px; padding:0; }}
    QToolButton[nav="true"]:hover {{ background:#272D3A; border-color:#343B4A; }}
    QLabel[railCaption="true"] {{ color:#AEB6C5; font-size:9px; }}
    QFrame#v51Drawer {{ background:{SURFACE}; border-right:1px solid {BORDER}; }}
    QLabel#v51DrawerTitle, QLabel#v51InspectorTitle {{ font-size:18px; font-weight:700; }}
    QToolButton#v51DrawerClose {{ font-size:20px; background:transparent; border:0; border-radius:8px; }}
    QToolButton#v51DrawerClose:hover {{ background:#F0F2F7; }}
    QFrame#v51Stage {{ background:{WORKSPACE}; }}
    QFrame#v51CanvasBar {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:11px; }}
    QLabel[canvasTitle="true"] {{ font-weight:700; }}
    QFrame#v51CanvasHost {{ background:#D9DEE8; border:1px solid #CDD4DF; border-radius:14px; }}
    QGraphicsView {{ background:#C8CFDB; border:0; border-radius:9px; }}
    QFrame#v51Inspector {{ background:#F8F9FC; border-left:1px solid {BORDER}; }}
    QFrame[card="true"] {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:12px; }}
    QLabel[sectionTitle="true"] {{ font-size:13px; font-weight:700; }}
    QLabel[muted="true"] {{ color:{MUTED}; font-size:11px; }}
    QLabel[chip="true"] {{ background:#F1F3F7; border:1px solid #E3E7EE; border-radius:10px; padding:4px 7px; color:#536071; }}
    QLabel[connection="true"] {{ font-weight:600; padding:4px 0; }}
    QLabel[drawerHeading="true"] {{ color:#4E5969; font-weight:700; padding-top:3px; }}
    QPushButton, QToolButton {{ background:{SURFACE}; color:{TEXT}; border:1px solid #D6DCE6; border-radius:8px; padding:7px 11px; min-height:20px; }}
    QPushButton:hover, QToolButton:hover {{ background:#F7F7FC; border-color:#B8B2FF; }}
    QPushButton[role="primary"] {{ background:{ACCENT}; color:white; border-color:{ACCENT}; font-weight:700; }}
    QPushButton[role="primary"]:hover {{ background:#5748E8; border-color:#5748E8; }}
    QPushButton[role="secondary"] {{ background:#F0EEFF; color:#5143D9; border-color:#D8D2FF; font-weight:600; }}
    QPushButton[density="compact"] {{ padding:5px 9px; min-height:18px; }}
    QToolButton[shapeTile="true"] {{ background:#FAFBFD; border:1px solid #E1E5EC; border-radius:10px; padding:5px; font-size:9px; }}
    QToolButton[shapeTile="true"]:hover {{ background:#F1EFFF; border-color:#AFA7FF; color:#5143D9; }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background:{SURFACE}; border:1px solid #D6DCE6; border-radius:8px; padding:7px 9px; min-height:22px; }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color:#8B80FF; }}
    QComboBox::drop-down {{ width:24px; border:0; }}
    QScrollArea {{ background:transparent; border:0; }}
    QScrollArea > QWidget > QWidget {{ background:transparent; }}
    QGroupBox {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px; margin-top:13px; padding:12px; font-weight:700; }}
    QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 5px; }}
    QListWidget {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:8px; padding:4px; }}
    QListWidget::item {{ padding:7px; border-radius:6px; }}
    QListWidget::item:selected {{ background:#EFEDFF; color:#5143D9; }}
    QSlider::groove:horizontal {{ height:5px; background:#DDE2EA; border-radius:2px; }}
    QSlider::handle:horizontal {{ width:15px; margin:-5px 0; background:{ACCENT}; border-radius:7px; }}
    QProgressBar {{ background:#E5E9F0; border:0; border-radius:5px; text-align:center; min-height:9px; }}
    QProgressBar::chunk {{ background:{ACCENT}; border-radius:5px; }}
    ''')


def _capture_legacy(window):
    window._v51_legacy_buttons = list(window.findChildren(QAbstractButton))
    window._v51_legacy_labels = list(window.findChildren(QLabel))
    window._v51_legacy_groups = list(window.findChildren(QGroupBox))


def redesign(window):
    if getattr(window, "_v51_done", False):
        return
    window._v51_done = True
    _taskbar_identity(window)
    load_all_fonts()
    _capture_legacy(window)

    # Remove the previous V5 presentation while keeping its functions/signals alive.
    for dock in window.findChildren(QDockWidget):
        dock.hide()
    for toolbar in window.findChildren(QToolBar):
        toolbar.hide()

    # Take ownership of the legacy central widget before installing the new UI.
    # QMainWindow.setCentralWidget() deletes the previous central widget; several
    # printer/state controls (including QSlider instances) are still used by the
    # backend even though they are not shown in the modern layout.
    old_central = window.takeCentralWidget()
    if old_central is not None:
        old_central.setParent(window)
        old_central.hide()
    canvas = _find_canvas(window)
    if canvas is None:
        return

    used = set()
    new_root = QWidget()
    new_root.setObjectName("v51Root")
    root = QVBoxLayout(new_root)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    header = _build_header(window, used)
    root.addWidget(header)

    work = QWidget()
    work.setObjectName("v51Workspace")
    work_lay = QHBoxLayout(work)
    work_lay.setContentsMargins(0, 0, 0, 0)
    work_lay.setSpacing(0)

    rail = _build_rail(window)
    drawer = _build_drawer(window)
    inspector = _build_inspector(window, used)
    stage = _build_stage(window, canvas, used)
    window._v51_drawer = drawer
    window._v51_inspector = inspector

    work_lay.addWidget(rail)
    work_lay.addWidget(drawer)
    work_lay.addWidget(stage, 1)
    work_lay.addWidget(inspector)
    root.addWidget(work, 1)

    window.setCentralWidget(new_root)
    window._v51_legacy_central = old_central
    if old_central and old_central is not new_root:
        old_central.hide()

    _rebuild_menus(window)
    _apply_style(window)

    settings = QSettings("Yakoderaa", "PhomemoStudio")
    page = settings.value("ui/drawerPage", "Formas")
    if page not in window._v51_drawer_pages:
        page = "Formas"
    if settings.value("ui/drawerVisible", True, type=bool):
        window._v51_show_drawer(page)
    else:
        drawer.hide()
    _set_inspector_visible(window, settings.value("ui/inspectorVisible", True, type=bool))

    # Make sure every font selector sees fonts activated by Windows/Adobe.
    families = QFontDatabase.families()
    for combo in window.findChildren(QComboBox):
        try:
            hint = _norm(combo.objectName() + " " + combo.currentText())
            if "fuente" in hint or "font" in hint or combo.currentText() in families:
                current = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(families)
                combo.setCurrentText(current)
                combo.blockSignals(False)
        except Exception:
            pass

    window.statusBar().showMessage("Interfaz V5.1 lista · paneles recuperables desde Ver", 5000)


def install(MainWindow):
    if getattr(MainWindow, "_v51_redesign_installed", False):
        return
    MainWindow._v51_redesign_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        redesign(self)

    MainWindow.__init__ = wrapped
