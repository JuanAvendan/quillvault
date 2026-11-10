# Guía de prueba con tus imágenes

Esta guía es para probar QuillVault con tus propias imágenes **en tu equipo**.
Nada de lo que hagas aquí se sube a internet ni al repositorio.

## 0. Antes de empezar (una sola vez)

1. Abre una terminal en la carpeta del proyecto.
2. Instala todo:

   ```powershell
   uv sync --extra directml --extra ui --extra trocr --extra pdf --extra templates
   ```

3. Revisa que todo esté bien:

   ```powershell
   uv run quillvault doctor
   ```

   Deben salir en **OK**: ONNX Runtime, GPU (DirectML), TrOCR model, Review UI,
   Offline mode y Telemetry disabled.
4. Si el modelo TrOCR aparece pendiente:

   ```powershell
   uv run quillvault models download trocr-base-handwritten
   ```

5. **Recomendado:**
   - Activa BitLocker en el disco.
   - Desactiva *Historial del portapapeles* y *Sincronizar entre dispositivos* en Configuración → Sistema → Portapapeles.

## 1. Dónde guardar tus imágenes

Crea una carpeta **fuera del proyecto**, por ejemplo `C:\Users\<tú>\Documents\QuillVault-privado\`.
Si las dejas dentro del proyecto, usa la carpeta `data/`: está en `.gitignore` y un hook
de Git bloquea imágenes. Aun así, fuera del proyecto es más seguro.

## 2. Probar con la interfaz

```powershell
uv run quillvault ui
```

1. Sube una imagen o un PDF.
2. Elige el motor:
   - **RapidOCR**: el más rápido, en GPU. Bueno para letra clara o de molde.
   - **TrOCR**: entrenado para manuscrito (en inglés por ahora). Más lento, en CPU.
   - **VLM local**: el mejor para letra difícil; requiere [configurar llama.cpp](vlm-setup.md).
3. En *Opciones*:
   - Si la hoja es de cuaderno, activa **Quitar renglones de cuaderno**.
   - Si la foto es de baja calidad, prueba **Blanco y negro forzado**.
4. Pulsa **Transcribir**:
   - Las líneas en **naranja** son las que hay que revisar.
   - Corrige el texto directamente en la tabla.
5. Termina con alguna de estas acciones:
   - **Copiar (privado)**: no queda en el historial y se borra a los 45 s.
   - **Exportar TXT o JSON**.
   - **Limpiar sesión** al terminar.

Al cerrar la terminal (Ctrl+C) se borran todos los archivos temporales.

## 3. Probar desde la terminal

```powershell
uv run quillvault extract "C:\ruta\imagen.jpg"
uv run quillvault extract "C:\ruta\imagen.jpg" --engine trocr --remove-rules
uv run quillvault extract "C:\ruta\carpeta" --engine trocr --format json --out "C:\ruta\resultados"
```

## 4. Qué esperar (honestamente)

- Los modelos que vienen por defecto **no están entrenados con la letra de esta persona
  ni en español manuscrito**. En letra cursiva difícil pueden fallar bastante. Es normal.
- Esta prueba sirve para saber **qué tan lejos estamos**:
  - si RapidOCR o TrOCR ya leen bien, perfecto;
  - si no, el siguiente paso es la Fase 1 y 2: hojas de práctica y ajuste del modelo a esta letra.
- El modelo de visión local suele ser el que mejor lee letra difícil sin entrenamiento, pero
  **puede inventar palabras**. Por eso todas sus líneas salen marcadas para revisión.

## 5. Cómo compartir resultados sin compartir datos

Si quieres que analicemos qué tal funcionó, **no compartas imágenes ni texto**. Comparte:

- qué motor y qué opciones usaste;
- una estimación: "lee bien 7 de 10 líneas", "falla con los números", etc.;
- o, mejor, las **métricas del benchmark** con hojas de práctica ficticias:

  ```powershell
  uv run quillvault templates practica --pages 5
  # imprime practica\practice_sheets.pdf, que la persona lo copie a mano y escanea
  # cada hoja como practica\pagina_001.jpg, pagina_002.jpg, ...
  uv run quillvault benchmark practica -e rapidocr -e trocr --out practica\benchmark.md
  ```

  El reporte solo contiene porcentajes de error y tiempos, nunca texto.
