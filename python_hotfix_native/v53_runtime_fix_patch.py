from pathlib import Path

p = Path("python_app/phomemo_studio/v53_fonts_library.py")
s = p.read_text(encoding="utf-8")

# QtAwesome's charmaps are already loaded by _instance(); probing with qta.icon
# unnecessarily required a running QApplication and broke headless validation.
old_ensure = '''def _ensure_prefix(prefix: str):\n    if qta is None:\n        return\n    probe = PROBES.get(prefix)\n    if not probe:\n        return\n    try:\n        qta.icon(f"{prefix}.{probe}")\n    except Exception:\n        pass\n'''
new_ensure = '''def _ensure_prefix(prefix: str):\n    # _instance() loads QtAwesome's bundled charmaps without needing to paint an icon.\n    # Keep this hook for compatibility, but do not require a QApplication here.\n    return\n'''
if old_ensure in s:
    s = s.replace(old_ensure, new_ensure)

# QAction returned from QMenu.addAction(text) can lose its Python wrapper in some
# PySide lifecycle combinations after the V5 menu rebuild. Keep an explicit action
# owned by the main window and then add it to the menu.
old_action = '''    target.addSeparator()\n    action = target.addAction("Actualizar fuentes ahora")\n    action.triggered.connect(lambda: (_poll_fonts(window), refresh_fonts(window, announce=True)))\n'''
new_action = '''    target.addSeparator()\n    from PySide6.QtGui import QAction\n    refresh_action = QAction("Actualizar fuentes ahora", window)\n    refresh_action.triggered.connect(lambda: (_poll_fonts(window), refresh_fonts(window, announce=True)))\n    target.addAction(refresh_action)\n    window._v53_refresh_fonts_action = refresh_action\n'''
if old_action in s:
    s = s.replace(old_action, new_action)

p.write_text(s, encoding="utf-8")
print("Applied V5.3 Qt runtime fixes")
