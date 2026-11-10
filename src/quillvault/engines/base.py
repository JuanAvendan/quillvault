"""Engine interface and factory (strategy pattern)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from quillvault.types import TextLine

ENGINE_NAMES = ("rapidocr", "trocr", "vlm")


@runtime_checkable
class OCREngine(Protocol):
    """Anything that turns an RGB page into ordered text lines."""

    name: str

    def recognize(self, image: NDArray[np.uint8]) -> list[TextLine]: ...


def sort_reading_order(lines: list[TextLine], tolerance: float = 0.5) -> list[TextLine]:
    """Sort top-to-bottom, then left-to-right for boxes sharing a text row."""
    if not lines:
        return []
    heights = [max(p[1] for p in ln.polygon) - ln.top for ln in lines if ln.polygon]
    row_gap = (float(np.median(heights)) if heights else 20.0) * tolerance

    ordered = sorted(lines, key=lambda ln: ln.top)
    rows: list[list[TextLine]] = []
    for line in ordered:
        if rows and abs(line.top - rows[-1][0].top) <= row_gap:
            rows[-1].append(line)
        else:
            rows.append([line])
    return [line for row in rows for line in sorted(row, key=lambda ln: ln.left)]


def create_engine(name: str, **options: Any) -> OCREngine:
    """Instantiate an engine by name. Heavy dependencies are imported lazily."""
    match name:
        case "rapidocr":
            from quillvault.engines.rapid import RapidOCREngine  # noqa: PLC0415

            return RapidOCREngine(**options)
        case "trocr":
            from quillvault.engines.trocr import TrOCREngine  # noqa: PLC0415

            return TrOCREngine(**options)
        case "vlm":
            from quillvault.engines.vlm import VLMEngine  # noqa: PLC0415

            return VLMEngine(**options)
        case _:
            raise ValueError(f"Unknown engine {name!r}. Choose one of: {', '.join(ENGINE_NAMES)}")
