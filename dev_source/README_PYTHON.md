# Phomemo Studio 4 — Python native

Runtime completamente migrado a Python 3.12 + PySide6, sin WebView2 ni JavaScript/C# en ejecución.

- UI nativa de Windows con barra de título estándar.
- Editor de etiquetas basado en QGraphicsScene.
- Plantillas, grupos/cafeterías, cola y estado de rollo persistidos en JSON.
- Bluetooth LE con bleak y bucle asyncio dedicado.
- Protocolo D30 preservado: densidad, gap/continuo, GS v 0, chunks de 128 bytes y feed.
- Actualizador a GitHub Releases con progreso, SHA-256 e instalación Inno Setup.
- Logo Sr Gato con transparencia alpha.
- Tests de persistencia, dimensiones 203 dpi, raster/protocolo y smoke test de UI.

El test físico Bluetooth/impresión real requiere una D30 conectada y no puede ser simulado por CI.
