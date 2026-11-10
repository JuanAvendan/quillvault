from __future__ import annotations

import numpy as np
import pytest

from quillvault.imaging.crop import crop_polygon
from quillvault.imaging.preprocess import (
    PreprocessConfig,
    estimate_skew,
    preprocess,
    remove_ruled_lines,
    rotate,
    to_gray,
)
from tests.conftest import render_text

LINES = ["Paciente con dolor abdominal", "Control en ocho dias", "Acetaminofen 500 mg", "Firma"]


@pytest.mark.parametrize("angle", [-6.0, -2.5, 3.0, 7.0])
def test_deskew_recovers_rotation(angle):
    gray = to_gray(render_text(LINES))
    tilted = rotate(gray, angle)
    estimated = estimate_skew(tilted)
    assert estimated == pytest.approx(-angle, abs=1.0)


def test_blank_page_has_no_skew():
    assert estimate_skew(np.full((500, 500), 255, dtype=np.uint8)) == 0.0


def test_remove_rules_erases_horizontal_lines():
    ruled = to_gray(render_text(LINES, ruled=True))
    plain = to_gray(render_text(LINES, ruled=False))
    cleaned = remove_ruled_lines(ruled)

    def marks(img: np.ndarray) -> int:
        return int(np.count_nonzero(img < 230))

    # Almost all rule pixels are gone, while handwriting-sized strokes survive.
    assert marks(cleaned) < marks(plain) + (marks(ruled) - marks(plain)) * 0.1
    assert marks(cleaned) > marks(plain) * 0.7


def test_preprocess_returns_rgb_and_step_names(text_image):
    out, steps = preprocess(text_image, PreprocessConfig(binarize=True))
    assert out.ndim == 3
    assert out.shape[2] == 3
    assert "flatten_illumination" in steps
    assert "binarize" in steps
    assert any(s.startswith("deskew") for s in steps)


def test_disabled_config_is_identity(text_image):
    out, steps = preprocess(text_image, PreprocessConfig.disabled())
    assert steps == []
    np.testing.assert_array_equal(to_gray(out), to_gray(text_image))


def test_small_images_are_upscaled():
    small = render_text(["hola"], size=12)[:80, :300]
    out, steps = preprocess(small, PreprocessConfig(upscale_below_px=1000))
    assert max(out.shape[:2]) == 1000
    assert steps[0].startswith("upscale")


def test_crop_polygon_rectifies_quadrilateral(text_image):
    polygon = ((50.0, 50.0), (450.0, 50.0), (450.0, 110.0), (50.0, 110.0))
    crop = crop_polygon(text_image, polygon)
    assert crop.shape[1] == 400
    assert crop.shape[0] == 60


def test_crop_polygon_handles_degenerate_boxes(text_image):
    assert crop_polygon(text_image, ((1.0, 1.0), (1.0, 1.0), (1.0, 1.0), (1.0, 1.0))).size > 0
