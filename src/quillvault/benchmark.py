"""Compare engines on a labelled dataset with CER / WER and speed.

The report contains **metrics only** — never recognised text — so it can be
shared (for example in an issue or the README) even if it was produced on
real documents.
"""

from __future__ import annotations

import json
import statistics
import time
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import jiwer

from quillvault.imaging.loader import SUPPORTED_SUFFIXES, load_path
from quillvault.pipeline import Pipeline


@dataclass(slots=True)
class Sample:
    image: Path
    reference: str


@dataclass(slots=True)
class EngineScore:
    engine: str
    pages: int
    cer: float
    cer_relaxed: float
    wer: float
    seconds_per_page: float
    lines_flagged_pct: float
    errors: int = 0
    per_page_cer: list[float] = field(default_factory=list)


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def relax(text: str) -> str:
    """Case- and accent-insensitive variant (tells you if errors are just tildes)."""
    decomposed = unicodedata.normalize("NFKD", normalize(text).lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def load_dataset(folder: Path) -> list[Sample]:
    samples = []
    for image in sorted(folder.iterdir()):
        if image.suffix.lower() not in SUPPORTED_SUFFIXES - {".pdf"}:
            continue
        truth = image.with_suffix(".txt")
        if truth.is_file():
            samples.append(Sample(image, truth.read_text(encoding="utf-8")))
    if not samples:
        raise FileNotFoundError(
            f"No image + .txt pairs found in {folder}. "
            "Expected e.g. pagina_001.jpg + pagina_001.txt"
        )
    return samples


def score_engine(
    name: str,
    pipeline: Pipeline,
    samples: Sequence[Sample],
    progress: Callable[[str], None] | None = None,
) -> EngineScore:
    refs, hyps, times, flagged, total_lines, page_cer = [], [], [], 0, 0, []
    errors = 0
    for index, sample in enumerate(samples, 1):
        if progress:
            progress(f"{name}: {index}/{len(samples)}")
        try:
            pages = load_path(sample.image)
            start = time.perf_counter()
            results = [pipeline.process_page(p) for p in pages]
            times.append(time.perf_counter() - start)
        except Exception:
            errors += 1
            results = []
        hypothesis = normalize(" ".join(r.text for r in results))
        reference = normalize(sample.reference)
        refs.append(reference)
        hyps.append(hypothesis)
        page_cer.append(round(float(jiwer.cer(reference, hypothesis)), 4))
        flagged += sum(r.review_count for r in results)
        total_lines += sum(len(r.lines) for r in results)

    return EngineScore(
        engine=name,
        pages=len(samples),
        cer=round(float(jiwer.cer(refs, hyps)), 4),
        cer_relaxed=round(float(jiwer.cer([relax(r) for r in refs], [relax(h) for h in hyps])), 4),
        wer=round(float(jiwer.wer(refs, hyps)), 4),
        seconds_per_page=round(statistics.fmean(times), 3) if times else 0.0,
        lines_flagged_pct=round(100 * flagged / total_lines, 1) if total_lines else 0.0,
        errors=errors,
        per_page_cer=page_cer,
    )


def to_markdown(scores: Sequence[EngineScore]) -> str:
    rows = [
        "| Engine | Pages | CER ↓ | CER (no case/accents) ↓ | WER ↓ | s/page "
        "| Lines flagged | Errors |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in sorted(scores, key=lambda s: s.cer):
        rows.append(
            f"| {s.engine} | {s.pages} | {s.cer:.1%} | {s.cer_relaxed:.1%} | {s.wer:.1%} "
            f"| {s.seconds_per_page:.2f} | {s.lines_flagged_pct:.0f}% | {s.errors} |"
        )
    return "\n".join(rows) + "\n"


def to_json(scores: Sequence[EngineScore]) -> str:
    return json.dumps([asdict(s) for s in scores], indent=2)
