"""Exporters and visualisation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from quillvault.types import PageResult


class Format(StrEnum):
    TXT = "txt"
    JSON = "json"
    MD = "md"


def to_txt(pages: Sequence[PageResult]) -> str:
    return "\n\n".join(page.text for page in pages) + "\n"


def to_json(pages: Sequence[PageResult]) -> str:
    return json.dumps([page.to_dict() for page in pages], ensure_ascii=False, indent=2)


def to_markdown(pages: Sequence[PageResult]) -> str:
    out: list[str] = []
    for page in pages:
        out.append(f"## Página {page.page_id}\n")
        out.append("| # | Texto | Confianza | Revisar | Observaciones |")
        out.append("|---|---|---|---|---|")
        for i, line in enumerate(page.lines, 1):
            conf = "—" if line.confidence is None else f"{line.confidence:.0%}"
            text = line.text.replace("|", "\\|")
            notes = "; ".join(line.issues).replace("|", "\\|")
            out.append(
                f"| {i} | {text} | {conf} | {'⚠️' if line.needs_review else '✅'} | {notes} |"
            )
        out.append("")
    return "\n".join(out)


RENDERERS = {Format.TXT: to_txt, Format.JSON: to_json, Format.MD: to_markdown}


def render(pages: Sequence[PageResult], fmt: Format) -> str:
    return RENDERERS[fmt](pages)


def write(path: Path, content: str, overwrite: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if overwrite else "x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return path


def annotate(image: NDArray[np.uint8], page: PageResult) -> NDArray[np.uint8]:
    """Draw line boxes: green = OK, orange = needs review. Numbers match the line list."""
    canvas = image.copy()
    thickness = max(2, image.shape[1] // 600)
    for index, line in enumerate(page.lines, 1):
        if not line.polygon:
            continue
        color = (230, 140, 20) if line.needs_review else (30, 160, 60)
        pts = np.array(line.polygon, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(canvas, [pts], isClosed=True, color=color, thickness=thickness)
        x, y = int(line.left), int(line.top)
        cv2.putText(
            canvas,
            str(index),
            (max(0, x - 4), max(14, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6 * thickness / 2,
            color,
            thickness,
            cv2.LINE_AA,
        )
    return canvas
