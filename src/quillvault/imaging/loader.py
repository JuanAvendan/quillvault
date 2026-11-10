"""Safe loading of untrusted images and PDFs.

Every file is treated as hostile: the real type is checked from its magic bytes
(not the extension), size and pixel count are bounded to stop decompression
bombs, and EXIF orientation is applied so phone photos come out upright.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_PIXELS = 80_000_000
MAX_PDF_PAGES = 100
PDF_DPI = 300

Image.MAX_IMAGE_PIXELS = MAX_PIXELS

_MAGIC: tuple[tuple[bytes, int, str], ...] = (
    (b"\xff\xd8\xff", 0, "jpeg"),
    (b"\x89PNG\r\n\x1a\n", 0, "png"),
    (b"II*\x00", 0, "tiff"),
    (b"MM\x00*", 0, "tiff"),
    (b"BM", 0, "bmp"),
    (b"WEBP", 8, "webp"),
    (b"%PDF-", 0, "pdf"),
)
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".pdf"}

RGBImage = NDArray[np.uint8]


class UnsupportedFileError(ValueError):
    """The file is not an accepted image/PDF or exceeds a safety limit."""


@dataclass(slots=True, frozen=True)
class LoadedPage:
    page_id: str
    image: RGBImage


def sniff_type(header: bytes) -> str | None:
    for magic, offset, kind in _MAGIC:
        if header[offset : offset + len(magic)] == magic:
            return kind
    return None


def _page_id(data: bytes, index: int) -> str:
    return f"{hashlib.sha256(data).hexdigest()[:12]}-p{index + 1:03d}"


def _to_rgb_array(image: Image.Image) -> RGBImage:
    image = ImageOps.exif_transpose(image) or image
    if image.width * image.height > MAX_PIXELS:
        raise UnsupportedFileError("Image exceeds the maximum pixel count")
    return np.asarray(image.convert("RGB"), dtype=np.uint8).copy()


def _iter_pdf(data: bytes) -> Iterator[Image.Image]:
    try:
        import pypdfium2 as pdfium  # noqa: PLC0415 - optional dependency
    except ImportError as exc:  # pragma: no cover - depends on extras
        raise UnsupportedFileError("PDF support needs: pip install 'quillvault[pdf]'") from exc

    document = pdfium.PdfDocument(data)
    try:
        if len(document) > MAX_PDF_PAGES:
            raise UnsupportedFileError(f"PDF has more than {MAX_PDF_PAGES} pages")
        for index in range(len(document)):
            page = document[index]
            try:
                yield page.render(scale=PDF_DPI / 72).to_pil()
            finally:
                page.close()
    finally:
        document.close()


def load_bytes(data: bytes) -> list[LoadedPage]:
    """Decode an in-memory image or PDF into RGB pages."""
    if len(data) > MAX_FILE_BYTES:
        raise UnsupportedFileError("File is larger than the 50 MB limit")
    kind = sniff_type(data[:16])
    if kind is None:
        raise UnsupportedFileError("Unsupported or unrecognised file type")

    if kind == "pdf":
        images = list(_iter_pdf(data))
    else:
        try:
            # Pin the decoder to the sniffed format so Pillow never falls back to
            # another plugin (e.g. the bundled JPEG 2000 decoder) on hostile input.
            with Image.open(io.BytesIO(data), formats=[kind.upper()]) as opened:
                opened.load()
                images = [opened.copy()]
        except Image.DecompressionBombError as exc:
            raise UnsupportedFileError("Image exceeds the maximum pixel count") from exc
        except OSError as exc:
            raise UnsupportedFileError("Corrupt or unreadable image") from exc

    return [LoadedPage(_page_id(data, i), _to_rgb_array(img)) for i, img in enumerate(images)]


def load_path(path: Path) -> list[LoadedPage]:
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise UnsupportedFileError(f"Unsupported extension: {path.suffix}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise UnsupportedFileError("File is larger than the 50 MB limit")
    return load_bytes(path.read_bytes())


def iter_input_files(paths: list[Path]) -> Iterator[Path]:
    """Expand directories (non-recursively) into supported files, in a stable order."""
    for path in paths:
        if path.is_dir():
            yield from sorted(p for p in path.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES)
        else:
            yield path
