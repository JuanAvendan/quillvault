"""Decide which lines a human must look at."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from quillvault.postprocess.lexicon import Lexicon
from quillvault.postprocess.validators import validate_text
from quillvault.types import TextLine


@dataclass(slots=True, frozen=True)
class ReviewPolicy:
    min_confidence: float = 0.85
    lexicon: Lexicon | None = None


def normalize(text: str) -> str:
    """Unicode NFC and collapsed whitespace (keeps accents and line content intact)."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def apply_review(lines: list[TextLine], policy: ReviewPolicy) -> list[TextLine]:
    for line in lines:
        line.text = normalize(line.text)
        line.issues.extend(validate_text(line.text))
        if policy.lexicon is not None:
            line.suggestions = policy.lexicon.suggest(line.text)
        if line.confidence is not None and line.confidence < policy.min_confidence:
            line.issues.append(f"confianza baja ({line.confidence:.0%})")
        line.needs_review = (
            line.needs_review
            or line.confidence is None
            or bool(line.issues)
            or bool(line.suggestions)
        )
    return lines
