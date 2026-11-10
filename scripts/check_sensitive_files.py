"""Refuse to commit scans or documents that could contain patient data.

Used by pre-commit and CI. Images/PDFs are only allowed in folders that hold
synthetic or illustrative material.
"""

from __future__ import annotations

import sys
from pathlib import PurePosixPath

BLOCKED = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
    ".heic",
    ".gif",
    ".pdf",
    ".dcm",
    ".docx",
    ".xlsx",
    ".csv",
}
ALLOWED_PREFIXES = ("docs/assets/", "tests/fixtures/synthetic/")


def main(paths: list[str]) -> int:
    offenders = []
    for raw in paths:
        path = PurePosixPath(raw.replace("\\", "/"))
        if path.suffix.lower() in BLOCKED and not str(path).startswith(ALLOWED_PREFIXES):
            offenders.append(str(path))
    if offenders:
        print("Blocked: these files may contain sensitive data and must not be committed:")
        for name in offenders:
            print(f"  - {name}")
        print(f"Only synthetic material is allowed, under: {', '.join(ALLOWED_PREFIXES)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
