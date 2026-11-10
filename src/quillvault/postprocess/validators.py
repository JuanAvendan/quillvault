"""Validators for values that commonly appear in Colombian clinical paperwork.

They never rewrite text. They return human-readable issues that the review UI
highlights, so a person decides.
"""

from __future__ import annotations

import re
from datetime import date

# Colombian identity document types used in RIPS (Res. 2275/2023 "tipoDocumentoIdentificacion").
DOCUMENT_TYPES = {
    "CC": "Cédula de ciudadanía",
    "TI": "Tarjeta de identidad",
    "RC": "Registro civil",
    "CE": "Cédula de extranjería",
    "PA": "Pasaporte",
    "PE": "Permiso especial de permanencia",
    "PT": "Permiso por protección temporal",
    "CN": "Certificado de nacido vivo",
    "AS": "Adulto sin identificación",
    "MS": "Menor sin identificación",
    "SC": "Salvoconducto",
    "CD": "Carné diplomático",
    "DE": "Documento extranjero",
}

_DATE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
_DOC = re.compile(
    r"\b(CC|TI|RC|CE|PA|PE|PT|CN)\.?\s*(?:No\.?|N°|#)?\s*([0-9][0-9.\s]{3,14}[0-9])\b"
)
_CIE10 = re.compile(r"\b([A-TV-Z])(\d{2})(?:\.?(\d{1,2}))?\b")
_CONFUSABLE_DIGITS = re.compile(r"\b(?=[\dOoIlSB]*\d)(?=[\dOoIlSB]*[OoIlSB])[\dOoIlSB]{5,}\b")

_DOC_LENGTH = {"CC": (3, 10), "TI": (10, 11), "RC": (8, 11), "CE": (3, 7)}


def _check_date(day: str, month: str, year: str) -> str | None:
    y = int(year)
    if len(year) == 2:
        y += 2000 if y < 50 else 1900
    try:
        value = date(y, int(month), int(day))
    except ValueError:
        return f"fecha inválida: {day}/{month}/{year}"
    if value > date.today():
        return f"fecha en el futuro: {day}/{month}/{year}"
    if value.year < 1900:
        return f"fecha improbable: {day}/{month}/{year}"
    return None


def validate_text(text: str) -> list[str]:
    """Return a list of issues found in one line of text."""
    issues: list[str] = []

    for match in _DATE.finditer(text):
        if problem := _check_date(*match.groups()):
            issues.append(problem)

    for match in _DOC.finditer(text):
        kind, raw = match.group(1), re.sub(r"[.\s]", "", match.group(2))
        bounds = _DOC_LENGTH.get(kind)
        if bounds and not bounds[0] <= len(raw) <= bounds[1]:
            issues.append(f"{kind} con longitud inusual ({len(raw)} dígitos)")

    issues.extend(
        f"posible confusión letra/número en '{m.group(0)}'"
        for m in _CONFUSABLE_DIGITS.finditer(text)
    )

    return issues


def find_cie10_codes(text: str) -> list[str]:
    """Extract candidate ICD-10 (CIE-10) codes such as ``I10`` or ``E11.9``."""
    codes = []
    for letter, digits, sub in _CIE10.findall(text):
        codes.append(f"{letter}{digits}{sub}" if sub else f"{letter}{digits}")
    return codes
