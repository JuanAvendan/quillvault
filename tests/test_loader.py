from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from quillvault.imaging import loader
from quillvault.imaging.loader import UnsupportedFileError, load_bytes, load_path, sniff_type


def test_sniff_detects_real_type_not_extension(make_png, text_image):
    assert sniff_type(make_png(text_image)[:16]) == "png"
    assert sniff_type(b"%PDF-1.7\n") == "pdf"
    assert sniff_type(b"MZ\x90\x00 not an image") is None


def test_load_png_returns_rgb_page_with_hash_id(make_png, text_image):
    pages = load_bytes(make_png(text_image))
    assert len(pages) == 1
    assert pages[0].image.shape == text_image.shape
    assert pages[0].image.dtype == np.uint8
    assert pages[0].page_id.endswith("-p001")
    assert len(pages[0].page_id) == len("0123456789ab-p001")


def test_disguised_executable_is_rejected(tmp_path):
    fake = tmp_path / "paciente_juan_perez.png"
    fake.write_bytes(b"MZ\x90\x00" + b"\x00" * 100)
    with pytest.raises(UnsupportedFileError):
        load_path(fake)


def test_unsupported_extension_is_rejected(tmp_path):
    other = tmp_path / "notes.exe"
    other.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(UnsupportedFileError):
        load_path(other)


def test_pixel_limit_blocks_decompression_bombs(monkeypatch, make_png, text_image):
    monkeypatch.setattr(loader, "MAX_PIXELS", 1000)
    with pytest.raises(UnsupportedFileError, match="pixel"):
        load_bytes(make_png(text_image))


def test_file_size_limit(monkeypatch, make_png, text_image):
    monkeypatch.setattr(loader, "MAX_FILE_BYTES", 10)
    with pytest.raises(UnsupportedFileError, match="larger"):
        load_bytes(make_png(text_image))


def test_corrupt_image_is_rejected():
    with pytest.raises(UnsupportedFileError):
        load_bytes(b"\x89PNG\r\n\x1a\n" + b"garbage" * 10)


def test_exif_orientation_is_applied():
    image = Image.new("RGB", (40, 20), "white")
    exif = image.getexif()
    exif[0x0112] = 6  # rotate 90° on display
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    page = load_bytes(buffer.getvalue())[0]
    assert page.image.shape[:2] == (40, 20)


def test_pdf_pages_are_rendered(tmp_path):
    pytest.importorskip("pypdfium2")
    canvas_mod = pytest.importorskip("reportlab.pdfgen.canvas")
    pdf_path = tmp_path / "doc.pdf"
    pdf = canvas_mod.Canvas(str(pdf_path))
    for text in ("uno", "dos"):
        pdf.drawString(100, 700, text)
        pdf.showPage()
    pdf.save()
    pages = load_path(pdf_path)
    assert [p.page_id[-4:] for p in pages] == ["p001", "p002"]
    assert pages[0].image.shape[2] == 3


def test_iter_input_files_expands_directories(tmp_path, make_png, text_image):
    (tmp_path / "b.png").write_bytes(make_png(text_image))
    (tmp_path / "a.png").write_bytes(make_png(text_image))
    (tmp_path / "ignore.txt").write_text("x")
    names = [p.name for p in loader.iter_input_files([tmp_path])]
    assert names == ["a.png", "b.png"]
