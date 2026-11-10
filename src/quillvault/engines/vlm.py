"""Local vision-language model (VLM) through a llama.cpp server on this machine.

Start the server yourself (see docs/vlm-setup.md), e.g. on an AMD GPU with the
Vulkan build of llama.cpp::

    llama-server -hf ggml-org/Qwen2.5-VL-7B-Instruct-GGUF --host 127.0.0.1 --port 8080 -ngl 99

Safety rules enforced here:

* the endpoint must resolve to a loopback address, so a typo can never upload a
  patient's document to the internet;
* proxy environment variables are ignored;
* VLMs can produce fluent text that is not on the page, so every line from this
  engine is marked as *needs review* (it has no calibrated confidence).
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Literal

import cv2
import httpx
import numpy as np
from numpy.typing import NDArray

from quillvault.engines.base import sort_reading_order
from quillvault.imaging.crop import crop_polygon
from quillvault.security.network import ensure_loopback_url
from quillvault.types import TextLine

if TYPE_CHECKING:
    from quillvault.engines.rapid import RapidOCREngine

DEFAULT_URL = "http://127.0.0.1:8080"
ILLEGIBLE = "[?]"
PROMPT_PAGE = (
    "Transcribe exactamente el texto manuscrito de la imagen, línea por línea, "
    "respetando los saltos de línea. No corrijas la ortografía, no completes palabras "
    f"y no agregues nada que no esté escrito. Si una palabra es ilegible escribe {ILLEGIBLE}. "
    "Responde únicamente con la transcripción."
)
PROMPT_LINE = (
    "Transcribe exactamente la línea manuscrita de la imagen. No corrijas ni completes "
    f"nada. Si una palabra es ilegible escribe {ILLEGIBLE}. Responde solo con el texto."
)


def encode_png(image: NDArray[np.uint8], max_side: int) -> str:
    scale = min(1.0, max_side / max(image.shape[:2]))
    if scale < 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("Could not encode image")
    return base64.b64encode(buffer.tobytes()).decode("ascii")


class VLMEngine:
    name = "vlm"

    def __init__(
        self,
        url: str = DEFAULT_URL,
        model: str = "local",
        mode: Literal["page", "lines"] = "page",
        timeout: float = 180.0,
        max_side: int = 1600,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.url = ensure_loopback_url(url).rstrip("/")
        self.model = model
        self.mode = mode
        self.max_side = max_side
        self._client = httpx.Client(timeout=timeout, trust_env=False, transport=transport)
        self._detector: RapidOCREngine | None = None

    def _ask(self, image: NDArray[np.uint8], prompt: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encode_png(image, self.max_side)}"
                            },
                        },
                    ],
                }
            ],
        }
        try:
            response = self._client.post(f"{self.url}/v1/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"No local VLM server at {self.url}. See docs/vlm-setup.md to start one."
            ) from exc
        content = response.json()["choices"][0]["message"]["content"]
        return str(content or "").strip()

    def _line(self, text: str, polygon: tuple[tuple[float, float], ...] = ()) -> TextLine:
        issues = ["illegible"] if ILLEGIBLE in text else []
        return TextLine(
            text=text,
            confidence=None,
            polygon=polygon,
            engine=self.name,
            needs_review=True,
            issues=issues,
        )

    def recognize(self, image: NDArray[np.uint8]) -> list[TextLine]:
        if self.mode == "page":
            raw = self._ask(image, PROMPT_PAGE)
            raw = raw.removeprefix("```").removesuffix("```").strip()
            return [self._line(t.strip()) for t in raw.splitlines() if t.strip()]

        if self._detector is None:
            from quillvault.engines.rapid import RapidOCREngine  # noqa: PLC0415

            self._detector = RapidOCREngine()
        lines = [
            self._line(self._ask(crop_polygon(image, poly), PROMPT_LINE), poly)
            for poly in self._detector.detect(image)
        ]
        return sort_reading_order(lines)

    def health(self) -> bool:
        try:
            return self._client.get(f"{self.url}/health", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False
