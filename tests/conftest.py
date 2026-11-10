"""Shared fixtures. Every test image is synthetic and generated at runtime."""

from __future__ import annotations

import io
from collections.abc import Callable

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont

from quillvault.types import TextLine


def render_text(lines: list[str], size: int = 44, ruled: bool = False) -> NDArray[np.uint8]:
    font = ImageFont.load_default(size=size)
    width, line_h = 1400, int(size * 2.2)
    image = Image.new("RGB", (width, line_h * len(lines) + 120), "white")
    draw = ImageDraw.Draw(image)
    for i, text in enumerate(lines):
        y = 60 + i * line_h
        if ruled:
            draw.line([(0, y + size + 8), (width, y + size + 8)], fill=(150, 170, 220), width=3)
        draw.text((60, y), text, fill="black", font=font)
    return np.asarray(image, dtype=np.uint8).copy()


def png_bytes(array: NDArray[np.uint8]) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def text_image() -> NDArray[np.uint8]:
    return render_text(["Paciente Ana Ruiz", "Control en 15 dias"])


@pytest.fixture
def make_png() -> Callable[[NDArray[np.uint8]], bytes]:
    return png_bytes


class FakeEngine:
    """Deterministic engine for pipeline/benchmark tests."""

    name = "fake"

    def __init__(self, texts: list[str], confidence: float | None = 0.95) -> None:
        self.texts = texts
        self.confidence = confidence

    def recognize(self, image: NDArray[np.uint8]) -> list[TextLine]:
        return [
            TextLine(
                text=t,
                confidence=self.confidence,
                polygon=(
                    (10, 10 + 50 * i),
                    (300, 10 + 50 * i),
                    (300, 50 + 50 * i),
                    (10, 50 + 50 * i),
                ),
                engine=self.name,
            )
            for i, t in enumerate(self.texts)
        ]


@pytest.fixture
def fake_engine() -> Callable[..., FakeEngine]:
    return FakeEngine
