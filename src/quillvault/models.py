"""Pinned model registry and explicit, one-time downloads.

Models are pinned to an exact commit so a compromised or changed upstream repo
cannot silently swap the weights. Only ``safetensors`` weights are fetched
(no pickle). After downloading, every engine loads with ``local_files_only``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ModelSpec:
    key: str
    repo_id: str
    revision: str
    license: str
    size_hint: str
    description: str
    allow_patterns: tuple[str, ...]


REGISTRY: dict[str, ModelSpec] = {
    spec.key: spec
    for spec in (
        ModelSpec(
            key="trocr-base-handwritten",
            repo_id="microsoft/trocr-base-handwritten",
            revision="eaacaf452b06415df8f10bb6fad3a4c11e609406",
            license="MIT",
            size_hint="1.3 GB",
            description="TrOCR base, trained on handwritten English (IAM). Fine-tune for Spanish.",
            allow_patterns=("*.json", "*.txt", "model.safetensors"),
        ),
    )
}
DEFAULT_TROCR = "trocr-base-handwritten"


def home() -> Path:
    """Root folder for QuillVault data (override with ``QUILLVAULT_HOME``)."""
    if custom := os.environ.get("QUILLVAULT_HOME"):
        return Path(custom)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "QuillVault"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "quillvault"


def models_dir() -> Path:
    return home() / "models"


def model_path(key: str) -> Path:
    return models_dir() / key


def is_downloaded(key: str) -> bool:
    return (model_path(key) / "config.json").is_file()


def download(key: str) -> Path:
    """Fetch a registered model. This is the ONLY code path that uses the network."""
    spec = REGISTRY[key]
    from huggingface_hub import snapshot_download  # noqa: PLC0415

    target = model_path(key)
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=spec.repo_id,
        revision=spec.revision,
        local_dir=target,
        allow_patterns=list(spec.allow_patterns),
    )
    return target
