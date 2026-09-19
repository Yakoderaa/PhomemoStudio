from __future__ import annotations

import math
from functools import partial

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, QTimer, Qt, QStringListModel
from PySide6.QtGui import (
    QColor, QBrush, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap,
    QTextBlockFormat, QTextCursor
)
from PySide6.QtWidgets import (
    QAbstractButton, QComboBox, QCompleter, QDoubleSpinBox, QFormLayout, QFrame, QGraphicsEllipseItem,
    QGraphicsItem, QGraphicsPathItem, QGraphicsTextItem, QGridLayout, QLabel,
    QLineEdit, QPlainTextEdit, QScrollArea, QSpinBox, QTabWidget, QTextEdit,
    QToolButton, QVBoxLayout, QWidget
)

from .studio_pro import _find_canvas

OVERLAY_ROLE = 1098
ROLE_KIND = 1001
ROLE_NAME = 1003


def _norm(value: str) -> str:
    return " ".join((value or "").strip().casefold().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").split())


def _schedule(window):
    try:
        from .v54_assets_session import _schedule_save
        _schedule_save(window)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Live text inspector binding
# ---------------------------------------------------------------------------

def _install_native_text_card(window):
    inspector = getattr(window, "_v51_inspector", None)
    if inspector is None or getattr(window, "_v56_text_fields", None):
        return

    # Hide the legacy Text card. It visually existed but its reused callbacks no
    # longer addressed the currently selected graphics item reliably.
    for label in inspector.findChildren(QLabel):
        if _norm(label.text()) == "texto":
            parent = label.parentWidget()
            if isinstance(parent, QFrame):
                parent.hide()
                break

    scroll = inspector.findChild(QScrollArea, "v51InspectorScroll")
    body = scroll.widget() if scroll is not None else None
    body_layout = body.layout() if body is not None else None
    if body_layout is None:
        return

    card = QFrame()
    card.setObjectName("v56LiveTextCard")
    card.setProperty("sectionCard", True)
    outer = QVBoxLayout(card)
    outer.setContentsMargins(14, 14, 14, 14)
    outer.setSpacing(10)

    title = QLabel("Texto")
    title.setProperty("sectionTitle", True)
    outer.addWidget(title)

    desc = QLabel("Editá directamente el texto seleccionado. Los cambios se ven en el lienzo en tiempo real.")
    desc.setWordWrap(True)
    desc.setProperty("muted", True)
    outer.addWidget(desc)

    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(9)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

    content = QPlainTextEdit()
    content.setObjectName("v56TextContent")
    content.setMaximumHeight(76)
    content.setPlaceholderText("Contenido del texto")
    form.addRow("Contenido", content)

    font = QComboBox()
    font.setObjectName("v56TextFont")
    font.setEditable(True)
    font.setInsertPolicy(QComboBox.NoInsert)
    font.setMinimumContentsLength(12)
    font.setMinimumHeight(34)
    font.lineEdit().setPlaceholderText("Escribí para buscar una fuente…")
    font.lineEdit().setClearButtonEnabled(False)
    families = sorted(QFontDatabase.families(), key=lambda x: x.casefold())
    font.addItems(families)
    model = QStringListModel(families, font)
    completer = QCompleter(model, font)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    completer.setFilterMode(Qt.MatchContains)
    completer.setMaxVisibleItems(18)
    font.setCompleter(completer)
    font._v56_model = model
    font._v56_completer = completer
    font.lineEdit().textEdited.connect(lambda _="": completer.complete())
    form.addRow("Fuente", font)

    size = QDoubleSpinBox()
    size.setObjectName("v56TextSize")
    size.setRange(1.0, 500.0)
    size.setDecimals(1)
    size.setValue(12.0)
    size.setSuffix(" pt")
    form.addRow("Tamaño", size)

    weight = QComboBox()
    weight.setObjectName("v56TextWeight")
    for name, value in [
        ("Fina", 300), ("Normal", 400), ("Media", 500),
        ("Seminegrita", 600), ("Negrita", 700), ("Extra negrita", 800), ("Black", 900)
    ]:
        weight.addItem(name, value)
    form.addRow("Grosor", weight)

    align = QComboBox()
    align.setObjectName("v56TextAlignment")
    align.addItems(["Izquierda", "Centro", "Derecha", "Justificado"])
    form.addRow("Alineación", align)

    tracking = QDoubleSpinBox()
    tracking.setObjectName("v56TextTracking")
    tracking.setRange(-20.0, 100.0)
    tracking.setDecimals(1)
    tracking.setValue(0.0)
    tracking.setSuffix(" px")
    form.addRow("Espaciado", tracking)

    line_height = QDoubleSpinBox()
    line_height.setObjectName("v56TextLineHeight")
    line_height.setRange(0.5, 4.0)
    line_height.setDecimals(2)
    line_height.setSingleStep(0.05)
    line_height.setValue(1.0)
    line_height.setSuffix(" ×")
    form.addRow("Interlineado", line_height)

    outer.addLayout(form)
    body_layout.insertWidget(0, card)

    window._v56_text_fields = {
        "contenido": content,
        "fuente": font,
        "tamano": size,
        "grosor": weight,
        "alineacion": align,
        "espaciado": tracking,
        "interlineado": line_height,
    }

    def refresh_family_list():
        latest = sorted(QFontDatabase.families(), key=lambda x: x.casefold())
        previous = [font.itemText(i) for i in range(font.count())]
        if latest == previous:
            return
        current = font.currentText()
        font.blockSignals(True)
        font.clear()
        font.addItems(latest)
        font.setCurrentText(current)
        font.blockSignals(False)
        model.setStringList(latest)

    timer = QTimer(window)
    timer.setInterval(5000)
    timer.timeout.connect(refresh_family_list)
    timer.start()
    window._v56_font_refresh_timer = timer



def _form_fields(window):
    inspector = getattr(window, "_v51_inspector", None)
    if inspector is None:
        return {}

    wanted = {
        "contenido", "fuente", "tamano", "grosor", "peso",
        "alineacion", "espaciado", "tracking", "interlineado"
    }
    result = {}

    def walk_layout(layout):
        if layout is None:
            return
        if isinstance(layout, QFormLayout):
            for row in range(layout.rowCount()):
                li = layout.itemAt(row, QFormLayout.LabelRole)
                fi = layout.itemAt(row, QFormLayout.FieldRole)
                label = li.widget() if li else None
                field = fi.widget() if fi else None
                if isinstance(label, QLabel) and field is not None:
                    key = _norm(label.text())
                    if key in wanted and key not in result:
                        result[key] = field
        for i in range(layout.count()):
            item = layout.itemAt(i)
            child_layout = item.layout()
            child_widget = item.widget()
            if child_layout is not None:
                walk_layout(child_layout)
            elif child_widget is not None and child_widget.layout() is not None:
                walk_layout(child_widget.layout())

    walk_layout(inspector.layout())
    return result


def _selected_text(window):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return None
    selected = [i for i in view.scene().selectedItems() if not i.data(OVERLAY_ROLE)]
    if len(selected) != 1:
        return None
    item = selected[0]
    if isinstance(item, QGraphicsTextItem):
        return item
    return None


def _set_editor_text(widget, value: str):
    if isinstance(widget, QLineEdit):
        widget.setText(value)
    elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
        widget.setPlainText(value)


def _editor_text(widget):
    if isinstance(widget, QLineEdit):
        return widget.text()
    if isinstance(widget, (QTextEdit, QPlainTextEdit)):
        return widget.toPlainText()
    return None


def _font_weight_from_widget(widget) -> int:
    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        value = int(widget.value())
        # Qt accepts Weight enum values roughly 100..900.
        return max(100, min(900, value))
    if isinstance(widget, QComboBox):
        data = widget.currentData()
        try:
            return max(100, min(900, int(data)))
        except Exception:
            pass
        text = _norm(widget.currentText())
        if any(x in text for x in ("black", "heavy", "900")):
            return 900
        if any(x in text for x in ("extra bold", "extrabold", "800")):
            return 800
        if any(x in text for x in ("bold", "negrita", "700")):
            return 700
        if any(x in text for x in ("semi", "demi", "600")):
            return 600
        if any(x in text for x in ("medium", "500")):
            return 500
        if any(x in text for x in ("light", "300")):
            return 300
        if any(x in text for x in ("thin", "100")):
            return 100
    return 400


def _apply_alignment(item: QGraphicsTextItem, text: str):
    key = _norm(text)
    alignment = Qt.AlignLeft
    if any(x in key for x in ("centro", "centrado", "center")):
        alignment = Qt.AlignHCenter
    elif any(x in key for x in ("derecha", "right")):
        alignment = Qt.AlignRight
    elif any(x in key for x in ("justif", "justify")):
        alignment = Qt.AlignJustify
    cursor = item.textCursor()
    cursor.select(QTextCursor.Document)
    fmt = QTextBlockFormat()
    fmt.setAlignment(alignment)
    cursor.mergeBlockFormat(fmt)
    item.setTextCursor(cursor)


def _apply_line_height(item: QGraphicsTextItem, value):
    try:
        value = float(value)
    except Exception:
        return
    # Treat small values as multipliers and larger values as percentages.
    percent = value * 100.0 if 0 < value <= 4.0 else value
    percent = max(50.0, min(400.0, percent))
    cursor = item.textCursor()
    cursor.select(QTextCursor.Document)
    fmt = QTextBlockFormat()
    fmt.setLineHeight(percent, QTextBlockFormat.ProportionalHeight)
    cursor.mergeBlockFormat(fmt)
    item.setTextCursor(cursor)


class TextInspectorBinder(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.view = _find_canvas(window)
        self.fields = getattr(window, "_v56_text_fields", None) or _form_fields(window)
        self._syncing = False
        self._connections = []
        if self.view is None or self.view.scene() is None:
            return
        self.view.scene().selectionChanged.connect(self.sync_from_selection)
        self._connect_fields()
        QTimer.singleShot(0, self.sync_from_selection)

    def _connect(self, signal, fn):
        try:
            signal.connect(fn)
            self._connections.append((signal, fn))
        except Exception:
            pass

    def _connect_fields(self):
        for key, widget in self.fields.items():
            if key == "contenido":
                if isinstance(widget, QLineEdit):
                    self._connect(widget.textEdited, lambda _="", k=key: self.apply(k))
                elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
                    self._connect(widget.textChanged, lambda k=key: self.apply(k))
            elif isinstance(widget, QComboBox):
                self._connect(widget.currentTextChanged, lambda _="", k=key: self.apply(k))
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                self._connect(widget.valueChanged, lambda _=0, k=key: self.apply(k))
            elif isinstance(widget, QAbstractButton):
                self._connect(widget.clicked, lambda _=False, k=key: self.apply(k))

    def sync_from_selection(self):
        item = _selected_text(self.window)
        enabled = item is not None
        for widget in self.fields.values():
            widget.setEnabled(enabled)
        if item is None:
            return
        self._syncing = True
        try:
            font = item.font()
            for key, widget in self.fields.items():
                if key == "contenido":
                    _set_editor_text(widget, item.toPlainText())
                elif key == "fuente" and isinstance(widget, QComboBox):
                    widget.setCurrentText(font.family())
                elif key == "tamano" and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    size = font.pointSizeF()
                    if size <= 0:
                        size = float(font.pixelSize() if font.pixelSize() > 0 else 12)
                    widget.setValue(size)
                elif key in ("grosor", "peso"):
                    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                        widget.setValue(int(font.weight()))
                    elif isinstance(widget, QComboBox):
                        numeric = int(font.weight())
                        found = -1
                        for i in range(widget.count()):
                            try:
                                if int(widget.itemData(i)) == numeric:
                                    found = i
                                    break
                            except Exception:
                                pass
                        if found >= 0:
                            widget.setCurrentIndex(found)
                elif key in ("espaciado", "tracking") and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(float(font.letterSpacing()))
        finally:
            self._syncing = False

    def apply(self, key: str):
        if self._syncing:
            return
        item = _selected_text(self.window)
        if item is None:
            return
        widget = self.fields.get(key)
        if widget is None:
            return

        self._syncing = True
        try:
            if key == "contenido":
                value = _editor_text(widget)
                if value is not None and value != item.toPlainText():
                    cursor = item.textCursor()
                    fmt = cursor.charFormat()
                    item.setPlainText(value)
                    cursor = item.textCursor()
                    cursor.select(QTextCursor.Document)
                    cursor.mergeCharFormat(fmt)
                    item.setTextCursor(cursor)

            elif key == "fuente" and isinstance(widget, QComboBox):
                value = widget.currentText().strip()
                if value:
                    font = item.font()
                    font.setFamily(value)
                    item.setFont(font)

            elif key == "tamano" and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                font = item.font()
                font.setPointSizeF(max(1.0, float(widget.value())))
                item.setFont(font)

            elif key in ("grosor", "peso"):
                font = item.font()
                weight = _font_weight_from_widget(widget)
                try:
                    font.setWeight(QFont.Weight(weight))
                except Exception:
                    font.setWeight(weight)
                item.setFont(font)

            elif key == "alineacion" and isinstance(widget, QComboBox):
                _apply_alignment(item, widget.currentText())

            elif key in ("espaciado", "tracking") and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                font = item.font()
                font.setLetterSpacing(QFont.AbsoluteSpacing, float(widget.value()))
                item.setFont(font)

            elif key == "interlineado" and isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                _apply_line_height(item, widget.value())

            item.update()
            if item.scene() is not None:
                item.scene().update(item.sceneBoundingRect())
            controller = getattr(self.window, "_v55_transform_controller", None)
            if controller is not None:
                controller.refresh_geometry(force=True)
            _schedule(self.window)
        finally:
            self._syncing = False


# ---------------------------------------------------------------------------
# Line library
# ---------------------------------------------------------------------------

LINE_STYLES = [
    ("Línea", "solid"),
    ("Línea fina", "thin"),
    ("Línea gruesa", "thick"),
    ("Discontinua", "dash"),
    ("Punteada", "dot"),
    ("Doble", "double"),
    ("Flecha derecha", "arrow-r"),
    ("Flecha izquierda", "arrow-l"),
    ("Flecha doble", "arrow-both"),
]


def _line_path(kind: str) -> QPainterPath:
    p = QPainterPath()
    if kind == "double":
        p.moveTo(5, 43)
        p.lineTo(195, 43)
        p.moveTo(5, 57)
        p.lineTo(195, 57)
        return p

    p.moveTo(5, 50)
    p.lineTo(195, 50)

    if kind in ("arrow-r", "arrow-both"):
        p.moveTo(195, 50)
        p.lineTo(178, 38)
        p.moveTo(195, 50)
        p.lineTo(178, 62)
    if kind in ("arrow-l", "arrow-both"):
        p.moveTo(5, 50)
        p.lineTo(22, 38)
        p.moveTo(5, 50)
        p.lineTo(22, 62)
    return p


def _line_pen(kind: str) -> QPen:
    width = 2.0
    if kind == "thin":
        width = 1.0
    elif kind == "thick":
        width = 6.0
    pen = QPen(QColor("#111827"), width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    if kind == "dash":
        pen.setStyle(Qt.DashLine)
    elif kind == "dot":
        pen.setStyle(Qt.DotLine)
    return pen


def _line_icon(kind: str) -> QIcon:
    pm = QPixmap(84, 48)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    path = _line_path(kind)
    pen = _line_pen(kind)
    painter.setPen(pen)
    painter.scale(0.39, 0.39)
    painter.translate(5, 10)
    painter.drawPath(path)
    painter.end()
    return QIcon(pm)


def insert_line(window, label: str, kind: str):
    view = _find_canvas(window)
    if view is None or view.scene() is None:
        return None
    item = QGraphicsPathItem(_line_path(kind))
    item.setPen(_line_pen(kind))
    item.setBrush(Qt.NoBrush)
    item.setFlags(
        QGraphicsItem.ItemIsMovable
        | QGraphicsItem.ItemIsSelectable
        | QGraphicsItem.ItemIsFocusable
    )
    item.setData(ROLE_KIND, "studio-line")
    item.setData(ROLE_NAME, label)
    center = view.mapToScene(view.viewport().rect().center())
    br = item.boundingRect()
    item.setPos(center.x() - br.width() / 2, center.y() - br.height() / 2)
    view.scene().clearSelection()
    view.scene().addItem(item)
    item.setSelected(True)
    _schedule(window)
    return item


def _build_lines_page(window):
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(10)

    info = QLabel("Líneas básicas para divisores, subrayados, señalización y flechas.")
    info.setWordWrap(True)
    info.setProperty("muted", True)
    outer.addWidget(info)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    host = QWidget()
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 4, 6, 12)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)

    for i, (label, kind) in enumerate(LINE_STYLES):
        button = QToolButton()
        button.setText(label)
        button.setIcon(_line_icon(kind))
        button.setIconSize(QSize(74, 38))
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setProperty("shapeTile", True)
        button.setFixedSize(104, 78)
        button.clicked.connect(partial(insert_line, window, label, kind))
        grid.addWidget(button, i // 2, i % 2)

    scroll.setWidget(host)
    outer.addWidget(scroll, 1)
    return page


def _install_lines_library(window):
    tabs = window.findChild(QTabWidget, "v52OpenLibraryTabs")
    if tabs is None:
        return
    for i in range(tabs.count()):
        if _norm(tabs.tabText(i)) == "lineas":
            return
    tabs.addTab(_build_lines_page(window), "Líneas")


# ---------------------------------------------------------------------------
# Illustrator-style free rotation outside corners
# ---------------------------------------------------------------------------

class _RotateHandle(QGraphicsEllipseItem):
    def __init__(self, controller, corner: str):
        super().__init__(QRectF(-7, -7, 14, 14))
        self.controller = controller
        self.corner = corner
        self.setData(OVERLAY_ROLE, True)
        self.setZValue(1_000_002)
        pen = QPen(QColor("#2563EB"), 1.2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(QColor("#EFF6FF")))
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setCursor(Qt.CrossCursor)
        self.setToolTip("Arrastrar para rotar · Shift encaja a 45°")

    def mousePressEvent(self, event):
        self.controller.begin_rotate(event.scenePos())
        event.accept()

    def mouseMoveEvent(self, event):
        self.controller.rotate_to(event.scenePos(), event.modifiers())
        event.accept()

    def mouseReleaseEvent(self, event):
        self.controller.rotate_to(event.scenePos(), event.modifiers())
        self.controller.end_rotate()
        event.accept()


def _angle(center: QPointF, point: QPointF) -> float:
    return math.degrees(math.atan2(point.y() - center.y(), point.x() - center.x()))


def _install_rotation(window):
    controller = getattr(window, "_v55_transform_controller", None)
    if controller is None or getattr(controller, "_v56_rotation_installed", False):
        return
    controller._v56_rotation_installed = True
    controller.rotate_handles = {}
    controller._v56_rotating = False
    controller._v56_rotate_center = QPointF()
    controller._v56_rotate_start_mouse_angle = 0.0
    controller._v56_rotate_start_item_angle = 0.0

    for corner in ("tl", "tr", "br", "bl"):
        handle = _RotateHandle(controller, corner)
        controller.scene.addItem(handle)
        controller.rotate_handles[corner] = handle

    original_refresh = controller.refresh_geometry
    original_set_all_visible = controller._set_all_visible
    original_dispose = controller.dispose

    def set_all_visible(visible):
        original_set_all_visible(visible)
        for h in controller.rotate_handles.values():
            h.setVisible(bool(visible))

    def refresh_geometry(force=False):
        original_refresh(force=force)
        target = controller.target
        if not controller._overlay_enabled or target is None or not controller.outline.isVisible():
            for h in controller.rotate_handles.values():
                h.setVisible(False)
            return
        points = getattr(controller, "_last_points", {})
        if not all(k in points for k in ("tl", "tr", "br", "bl")):
            return
        center = target.mapToScene(target.boundingRect().center())
        distance = 20.0
        for corner, h in controller.rotate_handles.items():
            p = points[corner]
            vx, vy = p.x() - center.x(), p.y() - center.y()
            length = max(1e-6, math.hypot(vx, vy))
            h.setPos(QPointF(p.x() + vx / length * distance, p.y() + vy / length * distance))
            h.setVisible(True)

    def begin_rotate(scene_pos):
        target = controller.target
        if target is None:
            return
        controller._v56_rotating = True
        controller._v56_rotate_center = target.mapToScene(target.boundingRect().center())
        controller._v56_rotate_start_mouse_angle = _angle(controller._v56_rotate_center, scene_pos)
        controller._v56_rotate_start_item_angle = float(target.rotation())

    def rotate_to(scene_pos, modifiers):
        target = controller.target
        if target is None or not controller._v56_rotating:
            return
        now = _angle(controller._v56_rotate_center, scene_pos)
        value = controller._v56_rotate_start_item_angle + (now - controller._v56_rotate_start_mouse_angle)
        if modifiers & Qt.ShiftModifier:
            value = round(value / 45.0) * 45.0
        target.setRotation(value)
        refresh_geometry(True)

    def end_rotate():
        controller._v56_rotating = False
        _schedule(window)
        refresh_geometry(True)

    def dispose():
        for h in list(controller.rotate_handles.values()):
            try:
                if h.scene() is controller.scene:
                    controller.scene.removeItem(h)
            except Exception:
                pass
        original_dispose()

    controller._set_all_visible = set_all_visible
    controller.refresh_geometry = refresh_geometry
    # The V5.5 timer was connected to the old bound refresh method. Rebind it
    # so external-corner rotation controls follow items while they are moved.
    try:
        controller.timer.timeout.disconnect(original_refresh)
    except Exception:
        pass
    try:
        controller.timer.timeout.connect(refresh_geometry)
    except Exception:
        pass
    controller.begin_rotate = begin_rotate
    controller.rotate_to = rotate_to
    controller.end_rotate = end_rotate
    controller.dispose = dispose
    refresh_geometry(True)


def enhance(window):
    _install_native_text_card(window)
    window._v56_text_binder = TextInspectorBinder(window)
    _install_lines_library(window)
    _install_rotation(window)
    window.statusBar().showMessage(
        "V5.6 · texto en vivo · biblioteca de líneas · rotación libre desde las esquinas",
        6500,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v56_installed", False):
        return
    MainWindow._v56_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
