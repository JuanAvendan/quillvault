"""OCR engines. Every engine implements :class:`quillvault.engines.base.OCREngine`."""

from quillvault.engines.base import ENGINE_NAMES, OCREngine, create_engine

__all__ = ["ENGINE_NAMES", "OCREngine", "create_engine"]
