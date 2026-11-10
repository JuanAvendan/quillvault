<div align="center">

# 🪶 QuillVault

**OCR de manuscritos privado y sin conexión para documentos sensibles.**
Tus imágenes nunca salen de tu equipo.

[English](README.md) · [Seguridad](SECURITY.md) · [Evaluación técnica](docs/evaluacion-tecnica.md) · [Guía de prueba](docs/guia-de-prueba.md)

</div>

---

QuillVault convierte fotos y escaneos de documentos **escritos a mano** en texto editable y
copiable, todo en tu propio computador. Nació para documentación clínica (historias que
alimentan los RIPS en Colombia), donde enviar imágenes a un OCR en la nube no es una opción.

* **Inferencia 100 % local.** Sin APIs en la nube ni telemetría. Solo se usa internet para descargar modelos una vez, y únicamente cuando tú lo pides.
* **Pensado para manuscritos.** Detección de líneas, reconocimiento de escritura a mano (TrOCR) y un modelo de visión local opcional para letra difícil.
* **Revisión humana.** Toda línea dudosa se marca; nada se corrige en silencio.
* **Funciona con cualquier GPU.** Con ONNX Runtime + DirectML funciona en AMD, Intel y NVIDIA sobre Windows, y en CPU en cualquier sistema.
* **Medible.** Benchmark de CER/WER y generador de hojas de práctica con datos **ficticios**.

## Inicio rápido (Windows)

```powershell
uv sync --extra directml --extra ui --extra trocr --extra pdf --extra templates
uv run quillvault doctor
uv run quillvault ui
```

La interfaz se abre en `http://127.0.0.1:7860`, accesible solo desde este equipo.
La guía paso a paso para probarla con tus imágenes está en [docs/guia-de-prueba.md](docs/guia-de-prueba.md).

## Comandos

| Comando | Para qué sirve |
|---|---|
| `quillvault ui` | Interfaz de revisión local |
| `quillvault extract RUTA` | Extrae texto (imágenes, PDF o carpetas) |
| `quillvault extract RUTA --copy` | Copia al portapapeles sin dejar rastro en el historial (Win+V) |
| `quillvault templates CARPETA` | Genera hojas de práctica con datos ficticios |
| `quillvault benchmark CARPETA -e rapidocr -e trocr` | Compara motores (solo métricas, nunca texto) |
| `quillvault models download trocr-base-handwritten` | Descarga el modelo de manuscrito (una vez) |
| `quillvault doctor` | Revisa la instalación, la GPU y la privacidad |

## Privacidad

Resumen del modelo de amenazas (detalle en [SECURITY.md](SECURITY.md)):

- No hay motores en la nube. El modelo de visión solo acepta servidores en `127.0.0.1`.
- Los modelos están fijados por hash y se cargan en formato `safetensors`.
- Los archivos se validan por su contenido real, con límites de tamaño y de píxeles.
- Los temporales se borran al cerrar la aplicación.
- Los logs nunca contienen texto ni nombres de archivo.
- El portapapeles queda excluido del historial de Windows y se limpia a los 45 s.
- Un hook de Git impide subir imágenes o documentos al repositorio.

> QuillVault es una herramienta, no una certificación de cumplimiento. Activa BitLocker
> y sigue los procedimientos de protección de datos de tu organización.

## Licencia

[Apache-2.0](LICENSE) © 2026 Juan Avendaño
