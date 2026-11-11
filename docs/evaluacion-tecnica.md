# Evaluación técnica — OCR de manuscritos con datos de salud

> Estado: **evaluación cerrada**; solo faltan las imágenes de muestra de la letra.
> Fecha: 2026-11-10

---

## 1. Requisitos confirmados

| Requisito | Detalle | Consecuencia en el diseño |
|---|---|---|
| Tipo de texto | **Manuscrito** de una persona concreta | Es reconocimiento de escritura a mano (HTR), no OCR de imprenta. Cambia la elección de motores. |
| Datos | **Información de salud de pacientes** (dato sensible) | Procesamiento 100 % local y offline. Ninguna imagen ni texto sale del equipo. |
| Licencias | Todo **gratis y open source** | Solo licencias permisivas (Apache-2.0, MIT, BSD). Sin APIs en la nube ni licencias restrictivas. |
| Hardware | AMD RX 6650 XT (8 GB), Ryzen 7 5700X, 24 GB RAM, Windows 11 | Sin CUDA. Inferencia por ONNX Runtime + DirectML o Vulkan. Ver §3. |
| Uso | Herramienta propia primero; integración con el sistema RIPS más adelante | Fase 1 sin API. El núcleo se diseña para exponerlo como API después. |
| Publicación | Repositorio público en GitHub | Sin datos reales en el repo. Tests y demo con datos sintéticos. |

### Marco legal (Colombia) — referencia, no asesoría legal
- **Ley 1581 de 2012** y **Decreto 1377 de 2013**: los datos de salud son *datos sensibles* y requieren protección reforzada.
- **Resolución 1995 de 1999**: la historia clínica es reservada.
- **Ley 2015 de 2020**: historia clínica electrónica interoperable.
- **Resolución 2275 de 2023**: RIPS en JSON como soporte de la factura electrónica, validados en el MUV.

El diseño local y offline es la forma más sencilla de cumplir: los datos nunca salen del equipo de quien ya los custodia.

---

## 2. Entorno detectado en el equipo

| Herramienta | Estado | Nota |
|---|---|---|
| Python | 3.15.1 | **Demasiado nuevo**: muchas librerías de ML (onnxruntime, torch) aún no publican paquetes para 3.15. El proyecto fijará **Python 3.12** con `uv`, sin tocar la instalación global. |
| uv | 0.13.7 | ✅ Gestor de entornos y dependencias |
| git / gh | 2.56 / instalado | ✅ |
| .NET SDK | 10.0.403 | ✅ Disponible para una futura API en C# |
| Docker Desktop | instalado | ⚠️ Docker Desktop **no es open source**: es gratis solo para personas y empresas pequeñas (<250 empleados y <10 M USD de ingresos). Alternativa libre: **Podman Desktop** (Apache-2.0) o Docker Engine dentro de WSL. |
| WSL | instalado | Útil si se decide entrenar con ROCm en Linux |
| Tesseract | no instalado | No hace falta: no sirve para manuscritos |
| GPU | RX 6650 XT, 8 GB (Windows reporta 4 GB por un límite del campo de 32 bits) | RDNA2 (gfx1032) |

---

## 3. GPU AMD en Windows: qué funciona y qué no

| Uso | Ruta recomendada | Licencia | Comentario |
|---|---|---|---|
| Inferencia de modelos OCR (detección y reconocimiento) | **ONNX Runtime + DirectML** | MIT | Funciona con cualquier GPU DirectX 12, incluida la RX 6650 XT. DirectML está en modo mantenimiento, pero estable. Con el Ryzen 7 la CPU queda como respaldo razonable. |
| Modelo de visión y lenguaje (VLM) local | **llama.cpp con backend Vulkan** | MIT | Un modelo de ~7B cuantizado en Q4 (~5–6 GB incluido el proyector de visión) cabe en 8 GB. |
| Entrenamiento / fine-tuning con PyTorch | ❌ No hay soporte oficial de ROCm para RDNA2 en Windows | — | Ver opciones abajo. |

**Opciones para entrenar**, si hiciera falta ajustar un modelo:
1. **Linux nativo o arranque dual con ROCm** y `HSA_OVERRIDE_GFX_VERSION=10.3.0`. Funciona en la práctica, pero sin soporte oficial.
2. **Kaggle o Google Colab gratuitos**. Solo son aceptables porque el dataset de entrenamiento **no contiene datos reales** (ver §5). Nunca se suben imágenes de pacientes.
3. **CPU**: lento (horas o días), pero viable para modelos pequeños.

Recomendación: empezar por la opción 2, ya que el dataset será ficticio por diseño.

---

## 4. Motores candidatos (todos locales y open source)

Al ser letra manuscrita, el panorama cambia respecto al OCR de imprenta:

| Motor | Rol | Licencia | Fortalezas | Riesgos |
|---|---|---|---|---|
| **RapidOCR** (modelos PaddleOCR PP-OCR en ONNX) | Detección de líneas y reconocimiento base | Apache-2.0 | Rápido. Funciona con DirectML. Buen detector de líneas incluso en manuscrito. | El reconocedor está entrenado sobre todo con texto impreso; con cursiva puede fallar. |
| **TrOCR** (`microsoft/trocr-*-handwritten`) | Reconocedor de manuscrito por línea | MIT (verificar en la tarjeta del modelo) | Diseñado para manuscrito. **Se puede ajustar a una sola persona** con pocos cientos de líneas. Exportable a ONNX. | El modelo base está entrenado en inglés; en español necesita fine-tuning. |
| **docTR** | Alternativa de detección y reconocimiento | Apache-2.0 | Pipeline completo y bien mantenido | Mismo problema con manuscrito |
| **VLM local** (p. ej. Qwen2.5-VL-7B vía llama.cpp) | Respaldo para líneas difíciles | Apache-2.0 en la variante 7B; **verificar la licencia de cada tamaño y versión** (algunas variantes tienen licencias restrictivas) | El mejor en manuscrito sin entrenamiento | **Puede inventar texto plausible** (alucinación): en datos de salud es peligroso. Más lento (segundos por línea). |

### Descartados

| Opción | Motivo |
|---|---|
| APIs en la nube (Google, Azure, AWS, Claude…) | Los datos de pacientes saldrían del equipo |
| Surya | Restricciones comerciales en los pesos del modelo |
| PyMuPDF | Licencia AGPL. Para PDF se usará `pypdfium2` (Apache/BSD). |
| Ultralytics YOLO | Licencia AGPL |
| Tesseract | No sirve para manuscrito |
| OCR integrado de Windows / PowerToys | No es open source ni portable |

### Hipótesis de partida (a confirmar con el benchmark)

```
Detector RapidOCR (líneas)
  → TrOCR ajustado a la letra de la persona (reconocedor principal)
  → si la confianza es baja: VLM local como segunda opinión
  → validación de dominio + revisión humana
```

---

## 5. Estrategia clave: dataset ficticio de la misma persona

Como siempre escribe la misma persona, la mejor ganancia de precisión es **ajustar el reconocedor a su letra**, sin usar ningún dato real:

1. El proyecto genera **plantillas imprimibles** (PDF) con texto ficticio pero realista:
   - nombres y apellidos colombianos inventados;
   - números de documento falsos;
   - fechas;
   - descripciones de diagnósticos CIE-10, procedimientos CUPS y medicamentos (tablas públicas del MinSalud);
   - números, abreviaturas médicas habituales y frases de texto libre.
2. La persona **copia a mano** ese texto en hojas con renglones y las escanea a 300 dpi.
3. Como el texto escrito es conocido, el etiquetado es automático: se obtienen pares imagen–texto sin transcribir nada a mano.
4. Volumen orientativo:
   - **50 líneas** para el benchmark inicial;
   - **300–1000 líneas** para el fine-tuning.
5. División de los datos por **página** (no por línea) en entrenamiento, validación y prueba, para no inflar las métricas.

Ventaja adicional: este dataset no es sensible, así que se puede entrenar en Colab o Kaggle y, si la persona lo autoriza, publicar el modelo.

---

## 6. Métricas del benchmark

| Métrica | Qué mide |
|---|---|
| **CER** (Character Error Rate) | Errores por carácter. Es la principal en manuscrito. |
| **WER** (Word Error Rate) | Errores por palabra |
| **Exactitud por campo crítico** | Documento, fechas y códigos: exacto o no exacto |
| **Tasa de alucinación** | Texto inventado que no aparece en la imagen (sobre todo en el VLM) |
| **Tiempo por página** | En la RX 6650 XT y en CPU |

Herramientas: `jiwer` (Apache-2.0) y un script propio de reportes que genera una tabla Markdown para el README.

---

## 7. Postprocesado con conocimiento del dominio

- **Diccionarios públicos del MinSalud**: CIE-10, CUPS, CUM (medicamentos) y DIVIPOLA (municipios). Sirven para corregir palabras cercanas y para validar códigos.
- **Validadores**:
  - tipos de documento (CC, TI, RC, CE, PA, etc.) y formato del número;
  - fechas válidas y coherentes;
  - códigos que existan en las tablas oficiales.
- **Confianza por campo**: todo lo que baje de un umbral se marca para revisión.
- **Nunca corregir en silencio**: cada corrección automática se muestra y el usuario la confirma.

## 8. Revisión humana obligatoria

En datos clínicos que terminan en RIPS enviados al Ministerio, **ningún texto pasa sin revisión**. La herramienta incluirá una interfaz local de revisión:

- muestra el recorte de la imagen junto al texto reconocido, con los campos dudosos resaltados;
- se hace con **Gradio** (Apache-2.0), ligado solo a `127.0.0.1`, con `share=False` y la telemetría desactivada (`GRADIO_ANALYTICS_ENABLED=False`);
- exporta a **JSON validado** (y TXT o CSV) solo después de la confirmación.

---

## 9. Seguridad

### Procesamiento
- 100 % offline una vez descargados los modelos.
  - Modelos con versión fija y verificación por hash SHA-256.
  - `HF_HUB_OFFLINE=1` y `HF_HUB_DISABLE_TELEMETRY=1`.
  - Cero telemetría en todas las librerías.
- Carga segura de modelos: formatos ONNX o `safetensors`; nada de *pickle* sin `weights_only=True`.
- Las imágenes se procesan en memoria. Si se usa un directorio temporal, se borra al terminar, también ante errores.
- **Los logs nunca contienen texto extraído ni nombres de archivo con datos**, solo hash, duración, confianza y errores.
- Enmascarado opcional de datos personales en exportaciones de prueba con **Presidio** (MIT, local).

### Equipo
- Activar **BitLocker** en el disco donde se guarden imágenes y resultados. Viene incluido en Windows 11 Pro.
- Portapapeles:
  - advertir que el historial de Windows (Win+V) y la sincronización en la nube pueden conservar lo copiado;
  - opción de limpiarlo tras N segundos;
  - copia automática desactivada por defecto.
- Política de retención: borrar las imágenes procesadas tras la revisión, si el flujo clínico lo permite.

### Repositorio público
- `data/`, `samples/` y `outputs/` van en `.gitignore`.
- Un hook de pre-commit **bloquea imágenes y PDF** fuera de `tests/fixtures/synthetic/`.
- `gitleaks` impide subir secretos.
- Tests y demo **solo con imágenes sintéticas** generadas por el propio proyecto.
- `SECURITY.md` con el modelo de amenazas y el canal para reportar vulnerabilidades.
- Seguridad de la cadena de suministro:
  - `uv.lock` con hashes;
  - Dependabot, `pip-audit` y CodeQL en GitHub Actions;
  - SBOM en cada release.

---

## 10. Integración futura con el sistema RIPS (Supabase)

### Recomendación: sin servidor expuesto a internet
```
[PC local con GPU]
  imágenes → OCR → revisión humana → JSON validado
      → la app RIPS lo importa y lo envía a Supabase
        (como ya hace hoy con los datos clínicos)
```
- Las **imágenes nunca salen del equipo**. Solo viajan datos estructurados y ya revisados, por el mismo canal autenticado que ya usa el proyecto.
- No hay endpoint público que proteger.

### Si más adelante se quiere una API
| Opción | A favor | En contra |
|---|---|---|
| **API en Python (FastAPI)** junto al núcleo | Mismo lenguaje que los modelos; menos código | Un servicio más que mantener |
| **API en C# (.NET 10)** | Encaja con tu experiencia | El ecosistema de ML está en Python. Es viable porque los modelos estarán en **ONNX**: `Microsoft.ML.OnnxRuntime.DirectML` (MIT) para inferencia y `LLamaSharp` (MIT) para el VLM. El preprocesado habría que portarlo. |

**Decisión de arquitectura ahora:** todos los modelos se exportan a **ONNX** como formato de intercambio. Así la puerta a C# queda abierta sin reescribir los modelos.

### Despliegue
- **No recomiendo hosting gratuito en la nube**, por tres motivos:
  - los datos de salud quedarían en servidores de terceros;
  - no hay GPU;
  - no hay garantías contractuales de tratamiento de datos.
- Las Edge Functions de Supabase no pueden ejecutar estos modelos.
- Recomendado: **on-premise**, como servicio de Windows en el equipo con la GPU, escuchando solo en la red local. Si en el futuro hace falta acceso remoto, por VPN mesh open source (WireGuard o Headscale), nunca con un puerto abierto a internet.

---

## 11. Estructura del repositorio

```
<nombre-del-repo>/
├── src/<paquete>/
│   ├── preprocessing/   # OpenCV: enderezado, binarización, ruido, normalización
│   ├── engines/         # interfaz OCREngine + adaptadores (rapidocr, trocr, vlm)
│   ├── postprocessing/  # diccionarios MinSalud, validadores, confianza
│   ├── review/          # interfaz Gradio local
│   ├── export/          # json, txt, csv
│   ├── security/        # limpieza de temporales, logs seguros, portapapeles
│   └── cli.py           # Typer
├── tools/
│   ├── make_templates.py    # genera los PDF de copia con texto ficticio
│   ├── segment_lines.py     # corta líneas de los escaneos y las empareja con su texto
│   ├── benchmark.py         # CER/WER/campos/tiempo → reporte Markdown
│   └── finetune_trocr.ipynb # para Colab/Kaggle, solo con datos ficticios
├── tests/  (fixtures sintéticas)
├── docs/   (esta evaluación, arquitectura, seguridad)
├── .github/workflows/  (lint, tests, auditoría, CodeQL, release)
├── pyproject.toml · uv.lock · .pre-commit-config.yaml
├── README.md (inglés) · README.es.md · LICENSE (Apache-2.0) · SECURITY.md · CHANGELOG.md
```

- **Licencia del repo: Apache-2.0.** Incluye concesión de patentes y es compatible con todo el stack.
- Código y README principal en inglés para más alcance, con README en español.

### Stack completo y licencias
| Componente | Licencia |
|---|---|
| Python 3.12, uv | PSF / Apache-2.0 + MIT |
| OpenCV, NumPy, Pillow | Apache-2.0 / BSD / MIT-CMU |
| ONNX Runtime (+DirectML) | MIT |
| RapidOCR, docTR | Apache-2.0 |
| Transformers, TrOCR | Apache-2.0 / MIT |
| llama.cpp | MIT |
| Gradio, Typer, FastAPI | Apache-2.0 / MIT / MIT |
| jiwer, Presidio | Apache-2.0 / MIT |
| pypdfium2, ReportLab (plantillas) | Apache-2.0 o BSD / BSD |
| ruff, mypy, pytest, pre-commit, gitleaks | MIT / MIT / MIT / MIT / MIT |

---

## 12. Plan por fases

| Fase | Estado | Contenido | ¿Necesita imágenes? |
|---|---|---|---|
| **0. Base** | ✅ v0.1.0 | Motores, preprocesado, interfaz de revisión, validadores, exportación, benchmark, plantillas ficticias, CI, repo público | No |
| **1. Benchmark** | Pendiente | La persona copia las notas ficticias; se miden RapidOCR, TrOCR base y VLM | Sí (ficticias) |
| **2. Fine-tuning** | Pendiente | Ajustar TrOCR a la letra, exportar a ONNX y verificar con DirectML | Sí (ficticias) |
| **3. Texto libre → datos** | Pendiente | Reconstruir párrafos a partir de las líneas y extraer en local códigos CIE-10, medicamentos y fechas para los campos RIPS (validadores + VLM/LLM local opcional) | No |
| **4. Integración** (opcional) | Pendiente | Importación JSON en la app RIPS o API (Python o C#) on-premise | No |

---

## 13. Preguntas abiertas

1. **¿Siempre escribe la misma persona?** Si son varias, cambia la estrategia de fine-tuning.
2. **¿Qué tipo de documento es?** Formulario con campos fijos, historia clínica de texto libre, orden médica…
   - **Respuesta: texto libre** (notas de consulta). Se descarta la lectura por zonas; las hojas de práctica
     usan por defecto notas ficticias en texto corrido (`--style notes`) y la extracción de campos RIPS pasa a la fase 3.
3. **¿Cómo se digitalizan?** Escáner o foto con el celular. Influye en el preprocesado.
4. **¿Volumen aproximado** de hojas por día o mes?
5. **Nombre del repositorio.**
