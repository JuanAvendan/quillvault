"""Image clean-up tuned for handwriting on scanned or photographed paper.

Each step is optional and cheap enough to run on a CPU. The defaults favour
phone photos (uneven lighting, slight rotation); neural recognisers generally
prefer clean greyscale over hard black/white binarisation, so that is opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

GrayImage = NDArray[np.uint8]
RGBImage = NDArray[np.uint8]


@dataclass(slots=True, frozen=True)
class PreprocessConfig:
    flatten_illumination: bool = True
    deskew: bool = True
    remove_rules: bool = False
    contrast: bool = True
    denoise: bool = False
    binarize: bool = False
    upscale_below_px: int = 1000
    max_skew_degrees: float = 10.0

    @classmethod
    def disabled(cls) -> PreprocessConfig:
        return cls(
            flatten_illumination=False,
            deskew=False,
            remove_rules=False,
            contrast=False,
            denoise=False,
            binarize=False,
            upscale_below_px=0,
        )


def to_gray(image: RGBImage) -> GrayImage:
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)


def flatten_illumination(gray: GrayImage) -> GrayImage:
    """Divide by a blurred background estimate to remove shadows and gradients."""
    kernel = max(15, (min(gray.shape) // 20) | 1)
    background = cv2.medianBlur(cv2.dilate(gray, np.ones((7, 7), np.uint8)), kernel)
    return cv2.divide(gray, background, scale=255)


def estimate_skew(gray: GrayImage, max_degrees: float = 10.0) -> float:
    """Return the rotation (degrees) that makes text lines horizontal.

    Projection-profile method: the correct angle maximises the variance of the
    row sums of the ink mask (sharp peaks on lines, valleys between them).
    """
    scale = 800 / max(gray.shape)
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    _, ink = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    if cv2.countNonZero(ink) < 50:
        return 0.0
    h, w = ink.shape
    center = (w / 2, h / 2)

    def score(angle: float) -> float:
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(ink, matrix, (w, h), flags=cv2.INTER_NEAREST)
        return float(np.var(rotated.sum(axis=1, dtype=np.float64)))

    coarse = np.arange(-max_degrees, max_degrees + 1e-9, 1.0)
    best = max(coarse, key=score)
    fine = np.arange(best - 1.0, best + 1.0 + 1e-9, 0.1)
    return round(float(max(fine, key=score)), 2)


def rotate(image: GrayImage, angle: float) -> GrayImage:
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def remove_ruled_lines(gray: GrayImage) -> GrayImage:
    """Erase long horizontal rules (notebook paper) and inpaint the gap.

    Rules are usually faint (light blue/grey), so a local adaptive threshold is
    used instead of Otsu, which would classify them as paper.
    """
    ink = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 12
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, gray.shape[1] // 12), 1))
    rules = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel, iterations=1)
    if cv2.countNonZero(rules) == 0:
        return gray
    rules = cv2.dilate(rules, np.ones((3, 3), np.uint8), iterations=1)
    return cv2.inpaint(gray, rules, 3, cv2.INPAINT_TELEA)


def preprocess(image: RGBImage, config: PreprocessConfig) -> tuple[RGBImage, list[str]]:
    """Apply the configured steps. Returns the RGB result and the names of applied steps."""
    gray = to_gray(image)
    applied: list[str] = []

    if config.upscale_below_px and max(gray.shape) < config.upscale_below_px:
        factor = config.upscale_below_px / max(gray.shape)
        gray = cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        applied.append(f"upscale x{factor:.2f}")
    if config.flatten_illumination:
        gray = flatten_illumination(gray)
        applied.append("flatten_illumination")
    if config.deskew:
        angle = estimate_skew(gray, config.max_skew_degrees)
        if abs(angle) >= 0.2:
            gray = rotate(gray, angle)
        applied.append(f"deskew {angle:+.1f}°")
    if config.remove_rules:
        gray = remove_ruled_lines(gray)
        applied.append("remove_rules")
    if config.denoise:
        gray = cv2.medianBlur(gray, 3)
        applied.append("denoise")
    if config.contrast:
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        applied.append("contrast")
    if config.binarize:
        gray = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
        )
        applied.append("binarize")

    return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB), applied
