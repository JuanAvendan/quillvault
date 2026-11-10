"""Command-line interface: ``quillvault --help``."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from quillvault import __version__, export, models
from quillvault.engines.base import ENGINE_NAMES
from quillvault.imaging.preprocess import PreprocessConfig
from quillvault.postprocess.lexicon import Lexicon
from quillvault.postprocess.review import ReviewPolicy
from quillvault.security.offline import allow_model_downloads, enforce_offline
from quillvault.security.redaction import configure_logging
from quillvault.types import PageResult

app = typer.Typer(
    name="quillvault",
    help="Private, offline handwriting OCR. Your documents never leave this machine.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,  # locals could contain document text
)
models_app = typer.Typer(help="Manage local model files (the only command that uses the network).")
app.add_typer(models_app, name="models")

console = Console(stderr=True)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"quillvault {__version__}")
        raise typer.Exit


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show progress logs.")] = False,
    _version_flag: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")
    ] = False,
) -> None:
    configure_logging(logging.INFO if verbose else logging.WARNING)
    enforce_offline()


def _engine_options(engine: str, device: str, vlm_url: str, vlm_mode: str) -> dict[str, Any]:
    if engine in {"rapidocr", "trocr"}:
        return {"device": device}
    return {"url": vlm_url, "mode": vlm_mode}


EngineOpt = Annotated[
    str, typer.Option("--engine", "-e", help=f"OCR engine: {', '.join(ENGINE_NAMES)}.")
]
DeviceOpt = Annotated[str, typer.Option(help="auto | gpu | cpu (RapidOCR/TrOCR detector).")]
VlmUrlOpt = Annotated[str, typer.Option(help="Local llama.cpp server (loopback only).")]
VlmModeOpt = Annotated[str, typer.Option(help="VLM mode: page (fast) | lines (with boxes).")]


@app.command()
def extract(
    inputs: Annotated[list[Path], typer.Argument(help="Images, PDFs or folders.", exists=True)],
    engine: EngineOpt = "rapidocr",
    fmt: Annotated[export.Format, typer.Option("--format", "-f")] = export.Format.TXT,
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Output folder (default: print).")
    ] = None,
    copy: Annotated[
        bool, typer.Option(help="Copy text to the clipboard (excluded from Win+V history).")
    ] = False,
    clear_after: Annotated[int, typer.Option(help="Wipe the clipboard after N seconds.")] = 45,
    preprocess: Annotated[bool, typer.Option(help="Image clean-up before OCR.")] = True,
    remove_rules: Annotated[bool, typer.Option(help="Erase notebook ruling lines.")] = False,
    binarize: Annotated[bool, typer.Option(help="Force black/white.")] = False,
    min_confidence: Annotated[float, typer.Option(min=0, max=1)] = 0.85,
    lexicon: Annotated[
        list[Path] | None, typer.Option(help="Extra vocabulary file(s), one term per line.")
    ] = None,
    device: DeviceOpt = "auto",
    vlm_url: VlmUrlOpt = "http://127.0.0.1:8080",
    vlm_mode: VlmModeOpt = "page",
    overwrite: Annotated[bool, typer.Option(help="Overwrite existing output files.")] = False,
) -> None:
    """Extract text from images/PDFs. Lines that need human review are flagged."""
    from quillvault.pipeline import Pipeline  # noqa: PLC0415
    from quillvault.security.clipboard import copy_private  # noqa: PLC0415

    config = (
        PreprocessConfig(remove_rules=remove_rules, binarize=binarize)
        if preprocess
        else PreprocessConfig.disabled()
    )
    vocab = Lexicon.builtin()
    if lexicon:
        vocab = Lexicon.from_files(*lexicon)
    policy = ReviewPolicy(min_confidence=min_confidence, lexicon=vocab)

    with console.status(f"Loading {engine}…"):
        pipeline = Pipeline(
            engine, config, policy, **_engine_options(engine, device, vlm_url, vlm_mode)
        )

    all_pages = []
    by_file: dict[Path, list[PageResult]] = {}
    with console.status("Reading…"):
        for path, page in pipeline.process_paths(inputs):
            by_file.setdefault(path, []).append(page)
            all_pages.append(page)

    if not all_pages:
        console.print("[yellow]No supported files found.[/]")
        raise typer.Exit(1)

    if out:
        for path, pages in by_file.items():
            target = out / f"{path.stem}.{fmt.value}"
            try:
                export.write(target, export.render(pages, fmt), overwrite=overwrite)
            except FileExistsError:
                console.print(f"[red]Exists[/] {target.name} (use --overwrite)")
                raise typer.Exit(1) from None
        console.print(f"[green]✓[/] {len(by_file)} file(s) written to {out}")
    else:
        typer.echo(export.render(all_pages, fmt))

    flagged = sum(p.review_count for p in all_pages)
    total = sum(len(p.lines) for p in all_pages)
    console.print(f"[bold]{total}[/] lines · [yellow]{flagged} need review[/]")

    if copy:
        copy_private(export.to_txt(all_pages), clear_after=clear_after or None)
        console.print(f"📋 Copied (not stored in clipboard history; wiped in {clear_after}s)")


@app.command()
def ui(
    port: Annotated[int, typer.Option(help="Port on 127.0.0.1.")] = 7860,
    browser: Annotated[bool, typer.Option(help="Open the browser automatically.")] = True,
) -> None:
    """Open the local review interface (bound to 127.0.0.1 only)."""
    from quillvault.ui.app import launch  # noqa: PLC0415

    launch(port=port, open_browser=browser)


@app.command()
def benchmark(
    dataset: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, help="image + .txt pairs")
    ],
    engine: Annotated[list[str] | None, typer.Option("--engine", "-e")] = None,
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Write report .md/.json")] = None,
    preprocess: bool = True,
    remove_rules: bool = False,
    device: DeviceOpt = "auto",
    vlm_url: VlmUrlOpt = "http://127.0.0.1:8080",
    vlm_mode: VlmModeOpt = "page",
) -> None:
    """Score engines (CER/WER/speed). The report never includes recognised text."""
    from quillvault import benchmark as bench  # noqa: PLC0415
    from quillvault.pipeline import Pipeline  # noqa: PLC0415

    samples = bench.load_dataset(dataset)
    config = (
        PreprocessConfig(remove_rules=remove_rules) if preprocess else PreprocessConfig.disabled()
    )
    scores = []
    for name in engine or ["rapidocr"]:
        try:
            pipe = Pipeline(name, config, **_engine_options(name, device, vlm_url, vlm_mode))
        except (RuntimeError, ValueError) as exc:
            console.print(f"[red]Skipping {name}:[/] {exc}")
            continue
        with console.status(f"{name}…") as status:
            scores.append(bench.score_engine(name, pipe, samples, status.update))

    report = bench.to_markdown(scores)
    typer.echo(report)
    if out:
        content = bench.to_json(scores) if out.suffix == ".json" else report
        out.write_text(content, encoding="utf-8")
        console.print(f"[green]✓[/] Report written to {out}")


@app.command()
def templates(
    out: Annotated[Path, typer.Argument(help="Folder for the PDF and ground-truth files.")],
    pages: Annotated[int, typer.Option(min=1, max=200)] = 10,
    lines: Annotated[int, typer.Option(min=1, max=16)] = 12,
    seed: int = 7,
) -> None:
    """Generate practice sheets with FAKE clinical data for a safe training/benchmark set."""
    from quillvault.templates import generate  # noqa: PLC0415

    result = generate(out, pages=pages, lines_per_page=lines, seed=seed)
    console.print(
        f"[green]✓[/] {result.pdf}  +  {len(result.ground_truth)} ground-truth .txt files"
    )
    console.print("Print the PDF, have the writer copy each page by hand, scan as pagina_NNN.jpg")


@app.command()
def doctor(
    vlm_url: Annotated[str | None, typer.Option(help="Also check a local VLM server.")] = None,
) -> None:
    """Check installation, GPU, models and privacy settings."""
    from quillvault.doctor import run_checks  # noqa: PLC0415

    table = Table(title=f"QuillVault {__version__}")
    for column in ("Check", "Status", "Detail", "How to fix"):
        table.add_column(column)
    for check in run_checks(vlm_url):
        table.add_row(
            check.name,
            "[green]OK[/]" if check.ok else "[yellow]—[/]",
            check.detail,
            "" if check.ok else check.hint,
        )
    Console().print(table)


@models_app.command("list")
def models_list() -> None:
    """Show pinned models and whether they are downloaded."""
    table = Table()
    for column in ("Key", "Repo @ revision", "License", "Size", "Local"):
        table.add_column(column)
    for spec in models.REGISTRY.values():
        table.add_row(
            spec.key,
            f"{spec.repo_id} @ {spec.revision[:10]}",
            spec.license,
            spec.size_hint,
            "✅" if models.is_downloaded(spec.key) else "—",
        )
    Console().print(table)


@models_app.command("download")
def models_download(
    key: Annotated[str, typer.Argument(help="Model key from `quillvault models list`.")],
) -> None:
    """Download a pinned model once. Only public model weights travel; no documents."""
    if key not in models.REGISTRY:
        console.print(f"[red]Unknown model[/] {key}. Options: {', '.join(models.REGISTRY)}")
        raise typer.Exit(1)
    spec = models.REGISTRY[key]
    allow_model_downloads()
    console.print(f"Downloading {spec.repo_id} ({spec.size_hint}, {spec.license})…")
    path = models.download(key)
    console.print(f"[green]✓[/] Saved to {path}")


if __name__ == "__main__":
    app()
