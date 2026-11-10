"""Telemetry and network switches.

``disable_telemetry`` runs on import and is always safe.
``enforce_offline`` additionally forbids model hubs from touching the network; it is
used everywhere except the explicit ``quillvault models download`` command.
"""

from __future__ import annotations

import os

_TELEMETRY_OFF = {
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
    "GRADIO_ANALYTICS_ENABLED": "False",
    "DO_NOT_TRACK": "1",
    "DISABLE_TELEMETRY": "1",
}

_OFFLINE = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
}


def disable_telemetry() -> None:
    """Turn off every telemetry switch we know of (never overrides an explicit value)."""
    for key, value in _TELEMETRY_OFF.items():
        os.environ.setdefault(key, value)


def enforce_offline() -> None:
    """Force model libraries into offline mode for the rest of the process."""
    disable_telemetry()
    os.environ.update(_OFFLINE)


def allow_model_downloads() -> None:
    """Lift offline mode. Only for ``quillvault models download`` (no documents involved).

    Must run before ``huggingface_hub`` is imported, because it reads these
    variables once at import time.
    """
    for key in _OFFLINE:
        os.environ.pop(key, None)


def is_offline() -> bool:
    return all(os.environ.get(key) == value for key, value in _OFFLINE.items())
