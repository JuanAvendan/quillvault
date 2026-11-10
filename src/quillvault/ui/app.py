"""Local review UI.

Privacy measures:

* bound to ``127.0.0.1`` only; no share links, no MCP server, no SSR node server;
* Gradio analytics/telemetry off and system fonts (no Google Fonts requests);
* every upload, preview and export lives in a private temporary folder that is
  purged periodically and deleted when the app closes;
* the "copy" action uses the private clipboard (excluded from Win+V history).
"""

from __future__ import annotations

import atexit
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from quillvault import export
from quillvault.engines.base import OCREngine, create_engine
from quillvault.imaging.loader import UnsupportedFileError, load_bytes
from quillvault.imaging.preprocess import PreprocessConfig
from quillvault.pipeline import Pipeline
from quillvault.postprocess.lexicon import Lexicon
from quillvault.postprocess.review import ReviewPolicy
from quillvault.security.offline import enforce_offline
from quillvault.security.tempfiles import make_private_dir, purge_stale_dirs, remove_tree
from quillvault.types import PageResult

HEADERS = ["Pág.", "#", "Texto (editable)", "Confianza", "Revisar", "Observaciones"]
ENGINE_LABELS = {
    "RapidOCR — rápido, GPU (texto claro)": "rapidocr",
    "TrOCR — manuscrito (requiere modelo)": "trocr",
    "VLM local — manuscrito difícil (requiere llama.cpp)": "vlm",
}
CSS = """
.privacy {border-left: 4px solid #4f46e5; padding: 6px 12px; border-radius: 6px;}
footer {display: none !important;}
"""

# --------------------------------------------------------------------------- pure helpers


def rows_from_pages(pages: list[PageResult]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for page_no, page in enumerate(pages, 1):
        for line_no, line in enumerate(page.lines, 1):
            notes = list(line.issues)
            notes += [f"¿{w} → {', '.join(s)}?" for w, s in line.suggestions.items()]
            rows.append(
                [
                    page_no,
                    line_no,
                    line.text,
                    "—" if line.confidence is None else f"{line.confidence:.0%}",
                    "⚠️" if line.needs_review else "✅",
                    "; ".join(notes),
                ]
            )
    return rows


def _as_rows(table: Any) -> list[list[Any]]:
    if table is None:
        return []
    if hasattr(table, "values") and hasattr(table, "columns"):  # pandas DataFrame
        return [list(r) for r in table.values.tolist()]
    return [list(r) for r in table]


def text_from_rows(table: Any) -> str:
    pages: dict[int, list[str]] = {}
    for row in _as_rows(table):
        if len(row) >= 3:
            pages.setdefault(int(row[0]), []).append(str(row[2]))
    return "\n\n".join("\n".join(lines) for _, lines in sorted(pages.items()))


def apply_edits(pages: list[PageResult], table: Any) -> list[PageResult]:
    """Return copies of ``pages`` with the user's corrections from the table."""
    edited = [replace(p, lines=[replace(ln) for ln in p.lines]) for p in pages]
    for row in _as_rows(table):
        page_i, line_i, text = int(row[0]) - 1, int(row[1]) - 1, str(row[2])
        if 0 <= page_i < len(edited) and 0 <= line_i < len(edited[page_i].lines):
            line = edited[page_i].lines[line_i]
            if line.text != text:
                line.text = text
                line.issues = [*line.issues, "corregido manualmente"]
    return edited


# --------------------------------------------------------------------------- app


class ReviewApp:
    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        self.exports = workdir / "exports"
        self.exports.mkdir(parents=True, exist_ok=True)
        self._engines: dict[tuple[str, str], OCREngine] = {}
        self._lexicon = Lexicon.builtin()

    def engine(self, name: str, vlm_url: str) -> OCREngine:
        key = (name, vlm_url if name == "vlm" else "")
        if key not in self._engines:
            options: dict[str, Any] = {"url": vlm_url} if name == "vlm" else {}
            self._engines[key] = create_engine(name, **options)
        return self._engines[key]

    def run(
        self,
        data: bytes | None,
        engine_label: str,
        clean: bool,
        remove_rules: bool,
        binarize: bool,
        min_confidence: float,
        vlm_url: str,
    ) -> tuple[list[Any], list[list[Any]], str, str, list[PageResult]]:
        import gradio as gr  # noqa: PLC0415

        if not data:
            raise gr.Error("Primero sube una imagen o un PDF.")
        try:
            pages = load_bytes(data)
        except UnsupportedFileError as exc:
            raise gr.Error(f"Archivo no válido: {exc}") from exc
        try:
            engine = self.engine(ENGINE_LABELS[engine_label], vlm_url)
        except (RuntimeError, ValueError) as exc:
            raise gr.Error(str(exc)) from exc

        config = (
            PreprocessConfig(remove_rules=remove_rules, binarize=binarize)
            if clean
            else PreprocessConfig.disabled()
        )
        pipeline = Pipeline(engine, config, ReviewPolicy(min_confidence, self._lexicon))
        results: list[PageResult] = []
        gallery: list[Any] = []
        for page in pages:
            try:
                result, image = pipeline.process_page_with_image(page)
            except RuntimeError as exc:
                raise gr.Error(str(exc)) from exc
            results.append(result)
            gallery.append((export.annotate(image, result), f"Página {len(results)}"))

        rows = rows_from_pages(results)
        total = sum(len(p.lines) for p in results)
        flagged = sum(p.review_count for p in results)
        seconds = sum(sum(p.timings_ms.values()) for p in results) / 1000
        summary = (
            f"**{total}** líneas · **{flagged}** para revisar · {seconds:.1f} s · "
            f"motor `{engine.name}` · {', '.join(results[0].preprocessing) or 'sin preprocesado'}"
        )
        return gallery, rows, text_from_rows(rows), summary, results

    def export_file(self, pages: list[PageResult], table: Any, fmt: str) -> str:
        import gradio as gr  # noqa: PLC0415

        if not pages:
            raise gr.Error("No hay resultados para exportar.")
        edited = apply_edits(pages, table)
        fmt_enum = export.Format(fmt)
        content = export.render(edited, fmt_enum)
        target = self.exports / f"quillvault_{edited[0].page_id}.{fmt}"
        export.write(target, content, overwrite=True)
        return str(target)

    def clear(self) -> tuple[None, list[Any], list[list[Any]], str, str, list[PageResult], None]:
        """Forget results and delete exports, uploads and previews from disk."""
        for folder in (self.exports, self.workdir / "gradio"):
            if folder.is_dir():
                for item in folder.iterdir():
                    if item.is_dir():
                        remove_tree(item)
                    else:
                        item.unlink(missing_ok=True)
        return None, [], [], "", "", [], None


def build(app: ReviewApp) -> Any:
    import gradio as gr  # noqa: PLC0415

    from quillvault.security.clipboard import copy_private  # noqa: PLC0415

    with gr.Blocks(
        title="QuillVault",
        analytics_enabled=False,
        delete_cache=(300, 900),
    ) as demo:
        gr.Markdown("# 🪶 QuillVault\nTranscripción de manuscritos **100 % local**.")
        gr.Markdown(
            "🔒 Las imágenes se procesan en este equipo. Nada se envía a internet. "
            "Los archivos temporales se borran al cerrar la aplicación.",
            elem_classes="privacy",
        )
        pages_state = gr.State([])

        with gr.Row():
            with gr.Column(scale=1, min_width=320):
                upload = gr.File(
                    label="Imagen o PDF",
                    file_types=[".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".pdf"],
                    type="binary",
                )
                engine = gr.Dropdown(
                    list(ENGINE_LABELS), value=next(iter(ENGINE_LABELS)), label="Motor"
                )
                with gr.Accordion("Opciones", open=False):
                    clean = gr.Checkbox(
                        True, label="Limpiar imagen (sombras, inclinación, contraste)"
                    )
                    rules = gr.Checkbox(False, label="Quitar renglones de cuaderno")
                    binarize = gr.Checkbox(False, label="Blanco y negro forzado")
                    threshold = gr.Slider(0.5, 0.99, 0.85, step=0.01, label="Confianza mínima")
                    vlm_url = gr.Textbox(
                        "http://127.0.0.1:8080", label="Servidor VLM local (solo 127.0.0.1)"
                    )
                run = gr.Button("Transcribir", variant="primary")
                summary = gr.Markdown()
            with gr.Column(scale=2):
                gallery = gr.Gallery(
                    label="Líneas detectadas (naranja = revisar)",
                    height=480,
                    columns=1,
                    object_fit="contain",
                    buttons=["fullscreen"],
                )

        table = gr.Dataframe(
            headers=HEADERS,
            datatype=["number", "number", "str", "str", "str", "str"],
            interactive=True,
            static_columns=[0, 1, 3, 4, 5],
            column_widths=["6%", "5%", "45%", "10%", "8%", "26%"],
            type="array",
            wrap=True,
            buttons=[],
            label="Revisión línea por línea — corrige el texto directamente en la columna 'Texto'",
        )
        # No browser copy button: it would bypass the private clipboard.
        final_text = gr.Textbox(label="Texto final", lines=10, interactive=True, buttons=[])

        with gr.Row():
            copy_btn = gr.Button("📋 Copiar (privado)")
            txt_btn = gr.Button("Exportar TXT")
            json_btn = gr.Button("Exportar JSON")
            clear_btn = gr.Button("🧹 Limpiar sesión", variant="stop")
        download = gr.File(label="Archivo exportado", interactive=False)

        run.click(
            app.run,
            [upload, engine, clean, rules, binarize, threshold, vlm_url],
            [gallery, table, final_text, summary, pages_state],
        )
        table.input(text_from_rows, table, final_text)

        def do_copy(text: str) -> None:
            if not text.strip():
                raise gr.Error("No hay texto para copiar.")
            copy_private(text)
            gr.Info("Copiado. No queda en el historial del portapapeles y se borra en 45 s.")

        copy_btn.click(do_copy, final_text, None)
        txt_btn.click(lambda p, t: app.export_file(p, t, "txt"), [pages_state, table], download)
        json_btn.click(lambda p, t: app.export_file(p, t, "json"), [pages_state, table], download)
        clear_btn.click(
            app.clear, None, [upload, gallery, table, final_text, summary, pages_state, download]
        )
    return demo


def launch(port: int = 7860, open_browser: bool = True) -> None:
    enforce_offline()
    purge_stale_dirs("quillvault-ui-")  # leftovers from killed sessions
    workdir = make_private_dir("quillvault-ui-")
    atexit.register(remove_tree, workdir)
    # Gradio stores uploads and previews here; must be set before gradio is imported.
    os.environ["GRADIO_TEMP_DIR"] = str(workdir / "gradio")

    import gradio as gr  # noqa: PLC0415

    demo = build(ReviewApp(workdir))
    theme = gr.themes.Soft(
        primary_hue="indigo",
        font=["system-ui", "Segoe UI", "sans-serif"],
        font_mono=["Consolas", "monospace"],
    )
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        share=False,
        inbrowser=open_browser,
        ssr_mode=False,
        mcp_server=False,
        enable_monitoring=False,
        footer_links=[],
        max_file_size="50mb",
        show_error=True,
        quiet=True,
        theme=theme,
        css=CSS,
    )
