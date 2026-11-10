"""Core data structures shared by every engine and exporter."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

Point = tuple[float, float]
Polygon = tuple[Point, ...]


@dataclass(slots=True)
class TextLine:
    """One recognised line of text.

    ``confidence`` is in ``[0, 1]`` or ``None`` when the engine cannot provide one
    (for example a vision-language model). Lines without a confidence are always
    flagged for human review.
    """

    text: str
    confidence: float | None
    polygon: Polygon = ()
    engine: str = ""
    needs_review: bool = False
    issues: list[str] = field(default_factory=list)
    suggestions: dict[str, list[str]] = field(default_factory=dict)

    @property
    def top(self) -> float:
        return min((p[1] for p in self.polygon), default=0.0)

    @property
    def left(self) -> float:
        return min((p[0] for p in self.polygon), default=0.0)


@dataclass(slots=True)
class PageResult:
    """Result for one page.

    ``page_id`` is a content hash, never the original filename: filenames of
    clinical scans often contain patient names or document numbers.
    """

    page_id: str
    engine: str
    width: int
    height: int
    lines: list[TextLine] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)
    preprocessing: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def review_count(self) -> int:
        return sum(1 for line in self.lines if line.needs_review)

    @property
    def mean_confidence(self) -> float | None:
        values = [line.confidence for line in self.lines if line.confidence is not None]
        return sum(values) / len(values) if values else None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["text"] = self.text
        data["review_count"] = self.review_count
        data["mean_confidence"] = self.mean_confidence
        return data
