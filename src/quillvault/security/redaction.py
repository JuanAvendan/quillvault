"""Logging that cannot leak document contents.

Policy: QuillVault never logs recognised text or original filenames. This filter
is a safety net on top of that policy for anything a third-party library might
emit (numbers that look like ID documents, e-mails, phone numbers, paths).
"""

from __future__ import annotations

import logging
import re

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"(?:[A-Za-z]:)?[\\/](?:[^\\/\s]+[\\/])+[^\\/\s]+"), "[PATH]"),
    (re.compile(r"\b\d[\d.\- ]{4,}\d\b"), "[NUMBER]"),
)


def redact(message: str) -> str:
    for pattern, replacement in _PATTERNS:
        message = pattern.sub(replacement, message)
    return message


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


def configure_logging(level: int = logging.WARNING) -> None:
    """Install a redacting handler on the root logger and quieten noisy libraries."""
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("RapidOCR", "httpx", "httpcore", "transformers", "gradio", "urllib3"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))
