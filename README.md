# Phomemo Studio D30

Aplicación de escritorio para Windows orientada a la Phomemo D30.

## V3 Desktop

- Ventana propia de Windows: no abre Edge ni Chrome.
- Bluetooth BLE/GATT a través de las APIs nativas de Windows.
- Autoconexión y reconexión al encender o despertar la D30.
- Lectura de batería/estado cuando el firmware lo expone.
- Calibración con página blanca 12×40.
- Editor 12×40, PNG/SVG, biblioteca y grupos por cafetería.
- Cola de impresión que se pausa cuando se termina el rollo y continúa después del cambio.
- Rollos de 80 etiquetas por defecto.
- Instalador de Windows generado con Inno Setup.
- Actualizaciones desde GitHub Releases con verificación SHA-256.

## Compilación

El workflow `.github/workflows/build-release.yml` compila en `windows-latest`, genera `PhomemoStudioSetup.exe` y publica/actualiza una release cuyo número sale de `version.txt`.

Para una actualización futura, cambiar `version.txt` y la versión del proyecto si corresponde, hacer commit a `main` y el instalador se publica automáticamente. La aplicación consulta la última release al iniciar.

## Firma de código

El instalador generado actualmente no tiene una firma Authenticode de una CA pública. Windows SmartScreen puede mostrar una advertencia de reputación aunque el archivo sea legítimo. Para eliminarla de forma consistente, hay que incorporar un certificado de firma de código al workflow.
