from pathlib import Path
import shutil

pkg = Path("python_app/phomemo_studio")
pkg.mkdir(parents=True, exist_ok=True)
target = pkg / "v53_fonts_library.py"
shutil.copy2("python_hotfix_native/v53_fonts_library.py", target)

# QtAwesome charmaps are already loaded by _instance(); avoid probing via qta.icon
# because that unnecessarily requires a running QApplication during validation.
mod = target.read_text(encoding="utf-8")
old_ensure = '''def _ensure_prefix(prefix: str):\n    if qta is None:\n        return\n    probe = PROBES.get(prefix)\n    if not probe:\n        return\n    try:\n        qta.icon(f"{prefix}.{probe}")\n    except Exception:\n        pass\n'''
new_ensure = '''def _ensure_prefix(prefix: str):\n    # QtAwesome loads its bundled charmaps through _instance(); no paint probe needed.\n    return\n'''
if old_ensure in mod:
    mod = mod.replace(old_ensure, new_ensure)

# Keep an explicit QAction owned by the main window. This avoids a PySide lifecycle
# issue seen after rebuilding the menu bar where addAction(text) could leave a dead wrapper.
old_action = '''    target.addSeparator()\n    action = target.addAction("Actualizar fuentes ahora")\n    action.triggered.connect(lambda: (_poll_fonts(window), refresh_fonts(window, announce=True)))\n'''
new_action = '''    target.addSeparator()\n    from PySide6.QtGui import QAction\n    refresh_action = QAction("Actualizar fuentes ahora", window)\n    refresh_action.triggered.connect(lambda: (_poll_fonts(window), refresh_fonts(window, announce=True)))\n    target.addAction(refresh_action)\n    window._v53_refresh_fonts_action = refresh_action\n'''
if old_action in mod:
    mod = mod.replace(old_action, new_action)

target.write_text(mod, encoding="utf-8")

ui = pkg / "ui.py"
s = ui.read_text(encoding="utf-8")
marker = "# PHOMEMO_V53_FONTS_LIBRARY_INSTALL"
if marker not in s:
    s += '''\n\n# PHOMEMO_V53_FONTS_LIBRARY_INSTALL\nfrom .v53_fonts_library import install as _install_v53_fonts_library\n_install_v53_fonts_library(MainWindow)\n'''
    ui.write_text(s, encoding="utf-8")

print("Applied Phomemo Studio 5.3 live searchable fonts + massive objects/decor library + runtime fixes")
