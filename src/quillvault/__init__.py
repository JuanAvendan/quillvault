"""QuillVault — private, offline handwriting OCR for sensitive documents.

Every image is processed on the local machine. Nothing is uploaded, nothing is
logged in clear text, and no telemetry is sent by QuillVault or (as far as we can
switch it off) by the libraries it uses.
"""

from quillvault.security.offline import disable_telemetry

# Telemetry switches must be set before third-party libraries are imported.
disable_telemetry()

from quillvault.pipeline import Pipeline  # noqa: E402
from quillvault.types import PageResult, TextLine  # noqa: E402

__version__ = "0.1.0"
__all__ = ["PageResult", "Pipeline", "TextLine", "__version__"]
