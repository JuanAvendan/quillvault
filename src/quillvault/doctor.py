"""Environment report: what is installed, what runs on the GPU, what is still missing."""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from dataclasses import dataclass

from quillvault import models
from quillvault.engines.rapid import directml_available
from quillvault.security.offline import is_offline


@dataclass(slots=True)
class Check:
    name: str
    ok: bool
    detail: str
    hint: str = ""


def _has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def run_checks(vlm_url: str | None = None) -> list[Check]:
    checks = [
        Check("Python", sys.version_info >= (3, 12), platform.python_version()),
        Check(
            "ONNX Runtime",
            _has("onnxruntime"),
            "installed" if _has("onnxruntime") else "missing",
            "uv sync --extra directml  (Windows GPU)  or  --extra cpu",
        ),
        Check(
            "GPU (DirectML)",
            directml_available(),
            "DmlExecutionProvider available" if directml_available() else "CPU only",
            "Windows + onnxruntime-directml uses AMD/Intel/NVIDIA GPUs",
        ),
        Check(
            "TrOCR libraries", _has("transformers") and _has("torch"), "", "uv sync --extra trocr"
        ),
        Check(
            f"TrOCR model ({models.DEFAULT_TROCR})",
            models.is_downloaded(models.DEFAULT_TROCR),
            str(models.model_path(models.DEFAULT_TROCR)),
            f"quillvault models download {models.DEFAULT_TROCR}",
        ),
        Check("Review UI (Gradio)", _has("gradio"), "", "uv sync --extra ui"),
        Check("PDF input", _has("pypdfium2"), "", "uv sync --extra pdf"),
        Check(
            "Practice sheets", _has("reportlab") and _has("faker"), "", "uv sync --extra templates"
        ),
        Check("Offline mode", is_offline(), "HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE"),
        Check(
            "Telemetry disabled",
            os.environ.get("GRADIO_ANALYTICS_ENABLED") == "False"
            and os.environ.get("HF_HUB_DISABLE_TELEMETRY") == "1",
            "Gradio analytics + HF telemetry off",
        ),
    ]
    if vlm_url:
        from quillvault.engines.vlm import VLMEngine  # noqa: PLC0415

        try:
            up = VLMEngine(url=vlm_url).health()
            checks.append(Check("Local VLM server", up, vlm_url, "see docs/vlm-setup.md"))
        except ValueError as exc:
            checks.append(Check("Local VLM server", False, str(exc)))
    return checks
