"""Domain vocabulary for *suggestions* (never automatic corrections).

Load any plain-text word list, one term per line: CIE-10 descriptions, CUPS
procedures, medicine names (CUM), municipalities (DIVIPOLA) or your own terms.
QuillVault ships a small generic list; the official MinSalud tables can be
downloaded from https://web.sispro.gov.co and converted with one term per line.
"""

from __future__ import annotations

import re
import unicodedata
from importlib import resources
from pathlib import Path

from rapidfuzz import fuzz, process

_WORD = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{4,}")


def _fold(text: str) -> str:
    """Lower-case and strip accents so 'Diagnostico' matches 'diagnóstico'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


class Lexicon:
    def __init__(self, terms: set[str]) -> None:
        self._by_fold: dict[str, str] = {}
        for term in terms:
            for word in _WORD.findall(term):
                self._by_fold.setdefault(_fold(word), word.lower())
        self._choices = list(self._by_fold)

    def __len__(self) -> int:
        return len(self._by_fold)

    def __contains__(self, word: str) -> bool:
        return _fold(word) in self._by_fold

    @classmethod
    def from_files(cls, *paths: Path) -> Lexicon:
        terms: set[str] = set()
        for path in paths:
            terms.update(
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            )
        return cls(terms)

    @classmethod
    def builtin(cls) -> Lexicon:
        data = resources.files("quillvault.postprocess").joinpath("data/medical_es.txt")
        terms = {
            line.strip()
            for line in data.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        return cls(terms)

    def suggest(self, text: str, min_score: float = 82.0, limit: int = 3) -> dict[str, list[str]]:
        """Map unknown words in ``text`` to close vocabulary words."""
        suggestions: dict[str, list[str]] = {}
        if not self._choices:
            return suggestions
        for word in _WORD.findall(text):
            folded = _fold(word)
            if folded in self._by_fold:
                continue
            matches = process.extract(
                folded, self._choices, scorer=fuzz.ratio, limit=limit, score_cutoff=min_score
            )
            if matches:
                suggestions[word] = [self._by_fold[m[0]] for m in matches]
        return suggestions
