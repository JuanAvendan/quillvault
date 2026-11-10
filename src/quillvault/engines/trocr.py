"""TrOCR handwriting recogniser with RapidOCR line detection.

Pipeline: RapidOCR finds text lines → each line is rectified and cropped →
TrOCR (a vision encoder + text decoder trained on handwriting) reads it.
Confidence is the geometric mean of the decoder's token probabilities.

The stock model is trained on English handwriting; accuracy on Spanish improves
a lot after fine-tuning on the writer's own (non-sensitive) practice sheets.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from quillvault import models
from quillvault.engines.rapid import Device, RapidOCREngine
from quillvault.imaging.crop import crop_polygon
from quillvault.types import TextLine

log = logging.getLogger(__name__)


class TrOCREngine:
    name = "trocr"

    def __init__(
        self,
        model: str | Path = models.DEFAULT_TROCR,
        device: Device = "auto",
        batch_size: int = 8,
        num_beams: int = 1,
        max_new_tokens: int = 96,
    ) -> None:
        try:
            import torch  # noqa: PLC0415
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel  # noqa: PLC0415
            from transformers.utils import logging as hf_logging  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on extras
            raise RuntimeError("TrOCR needs: uv sync --extra trocr") from exc

        # The unused encoder pooler is reported as "missing"; it is not used by TrOCR.
        hf_logging.set_verbosity_error()
        hf_logging.disable_progress_bar()

        path = Path(model) if Path(model).is_dir() else models.model_path(str(model))
        if not (path / "config.json").is_file():
            raise RuntimeError(
                f"TrOCR model not found at {path}. Download it once with:\n"
                f"  quillvault models download {model}"
            )

        self._torch = torch
        self._processor: Any = TrOCRProcessor.from_pretrained(path, local_files_only=True)
        self._model: Any = VisionEncoderDecoderModel.from_pretrained(
            path, local_files_only=True, use_safetensors=True
        )
        self._model.eval()
        self._detector = RapidOCREngine(device=device)
        self.batch_size = batch_size
        self.num_beams = num_beams
        self.max_new_tokens = max_new_tokens

    def _read_batch(self, crops: list[NDArray[np.uint8]]) -> list[tuple[str, float]]:
        torch = self._torch
        pixel_values = self._processor(images=crops, return_tensors="pt").pixel_values
        with torch.inference_mode():
            out = self._model.generate(
                pixel_values,
                max_new_tokens=self.max_new_tokens,
                num_beams=self.num_beams,
                output_scores=True,
                return_dict_in_generate=True,
            )
            scores = self._model.compute_transition_scores(
                out.sequences,
                out.scores,
                getattr(out, "beam_indices", None),
                normalize_logits=self.num_beams == 1,
            )
        texts = self._processor.batch_decode(out.sequences, skip_special_tokens=True)

        pad_id = self._processor.tokenizer.pad_token_id
        generated = out.sequences[:, -scores.shape[1] :]
        mask = generated != pad_id
        mean_logprob = (scores * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
        confidences = mean_logprob.exp().clamp(0, 1).tolist()
        return [(t.strip(), float(c)) for t, c in zip(texts, confidences, strict=True)]

    def recognize(self, image: NDArray[np.uint8]) -> list[TextLine]:
        polygons = self._detector.detect(image)
        crops = [crop_polygon(image, poly) for poly in polygons]
        lines: list[TextLine] = []
        for start in range(0, len(crops), self.batch_size):
            batch = crops[start : start + self.batch_size]
            for offset, (text, conf) in enumerate(self._read_batch(batch)):
                lines.append(
                    TextLine(
                        text=text,
                        confidence=conf,
                        polygon=polygons[start + offset],
                        engine=self.name,
                    )
                )
        return lines
