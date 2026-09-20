from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QPushButton

from .studio_pro import _call_first, _find_legacy_button


def _remove_header_actions(window):
    header = window.findChild(type(getattr(window, "_v51_header", None)) if getattr(window, "_v51_header", None) else object, "v51Header")
    # Use the concrete header attribute/name when the generic lookup above is not useful.
    if header is None:
        from PySide6.QtWidgets import QFrame
        header = window.findChild(QFrame, "v51Header")
    if header is None:
        return

    for button in list(header.findChildren(QPushButton, options=None)):
        text = button.text().replace("&", "").strip().casefold()
        if text in {"guardar", "duplicar", "png"}:
            button.hide()
            button.setParent(None)
            button.deleteLater()


def _connect_action(window, action, tokens, methods):
    old = _find_legacy_button(window, *tokens)
    fn = _call_first(window, methods)
    if old is not None:
        action.triggered.connect(old.click)
        return True
    if fn is not None:
        action.triggered.connect(fn)
        return True
    action.setEnabled(False)
    return False


def _rebuild_file_menu(window):
    menubar = window.menuBar()
    archivo = None
    for menu_action in menubar.actions():
        menu = menu_action.menu()
        if menu is not None and menu_action.text().replace("&", "").strip().casefold() == "archivo":
            archivo = menu
            break

    if archivo is None:
        archivo = menubar.addMenu("Archivo")
    else:
        archivo.clear()

    guardar_como = archivo.addMenu("Guardar como")

    png = QAction("PNG…", window)
    png.setObjectName("v602SaveAsPng")
    _connect_action(window, png, ("png",), ("export_png",))
    guardar_como.addAction(png)

    # Keep document/design saving exclusively in the Designs library as asked.
    # File only exposes export/save-as destinations.
    window._v602_save_as_menu = guardar_como
    window._v602_png_action = png


def _remove_png_from_images_page(window):
    pages = getattr(window, "_v51_drawer_pages", {})
    page = pages.get("Imágenes")
    if page is None:
        return
    for button in page.findChildren(QPushButton):
        text = button.text().replace("&", "").strip().casefold()
        if text in {"exportar png", "png"}:
            button.hide()
            button.setParent(None)
            button.deleteLater()


def enhance(window):
    _remove_header_actions(window)
    _remove_png_from_images_page(window)
    _rebuild_file_menu(window)
    window.statusBar().showMessage(
        "V6.0.2 · barra limpia · PNG en Archivo → Guardar como",
        5500,
    )


def install(MainWindow):
    if getattr(MainWindow, "_v602_installed", False):
        return
    MainWindow._v602_installed = True
    original = MainWindow.__init__

    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        enhance(self)

    MainWindow.__init__ = wrapped
