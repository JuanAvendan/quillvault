"""RapidOCR (PaddleOCR PP-OCR models on ONNX Runtime).

The detection and recognition models ship inside the ``rapidocr`` wheel, so this
engine works fully offline. On Windows it uses DirectML when
``onnxruntime-directml`` is installed, which runs on AMD, Intel and NVIDIA GPUs.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import cv2
import numpy as np
from numpy.typing import NDArray

from quillvault.engines.base import sort_reading_order
from quillvault.types import Polygon, TextLine

log = logging.getLogger(__name__)

Device = Literal["auto", "gpu", "cpu"]


def directml_available() -> bool:
    try:
        import onnxruntime as ort  # noqa: PLC0415
    except ImportError:
        return False
    return "DmlExecutionProvider" in ort.get_available_providers()


def _to_polygon(box: Any) -> Polygon:
    return tuple((float(x), float(y)) for x, y in np.asarray(box).reshape(-1, 2))


class RapidOCREngine:
    name = "rapidocr"

    def __init__(self, device: Device = "auto", text_score: float = 0.3) -> None:
        from rapidocr import RapidOCR  # noqa: PLC0415

        use_dml = device == "gpu" or (device == "auto" and directml_available())
        if device == "gpu" and not directml_available():
            raise RuntimeError(
                "GPU requested but DirectML is unavailable. "
                "Install with: uv sync --extra directml (Windows only)."
            )
        self.device = "gpu-directml" if use_dml else "cpu"
        params: dict[str, Any] = {
            "Global.log_level": "warning",
            "Global.text_score": text_score,
            "EngineConfig.onnxruntime.use_dml": use_dml,
        }
        self._ocr = RapidOCR(params=params)
        log.info("RapidOCR ready on %s", self.device)

    @staticmethod
    def _bgr(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
        # RapidOCR follows OpenCV's BGR convention for ndarray input.
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    def recognize(self, image: NDArray[np.uint8]) -> list[TextLine]:
        result = self._ocr(self._bgr(image))
        if result.boxes is None or result.txts is None or result.scores is None:
            return []
        lines = [
            TextLine(text=txt, confidence=float(score), polygon=_to_polygon(box), engine=self.name)
            for box, txt, score in zip(result.boxes, result.txts, result.scores, strict=True)
        ]
        return sort_reading_order(lines)

    def detect(self, image: NDArray[np.uint8]) -> list[Polygon]:
        """Text-line detection only (used by recognisers that bring their own model)."""
        result = self._ocr(self._bgr(image), use_det=True, use_cls=False, use_rec=False)
        if result.boxes is None:
            return []
        placeholders = [
            TextLine(text="", confidence=None, polygon=_to_polygon(b)) for b in result.boxes
        ]
        return [line.polygon for line in sort_reading_order(placeholders)]
