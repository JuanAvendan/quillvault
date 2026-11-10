"""End-to-end orchestration: load → preprocess → recognise → review."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from quillvault.engines.base import OCREngine, create_engine
from quillvault.imaging.loader import LoadedPage, iter_input_files, load_bytes, load_path
from quillvault.imaging.preprocess import PreprocessConfig, RGBImage, preprocess
from quillvault.postprocess.review import ReviewPolicy, apply_review
from quillvault.types import PageResult

log = logging.getLogger(__name__)


class Pipeline:
    """Reusable OCR pipeline. Create once; models stay loaded between pages.

    Example::

        from quillvault import Pipeline
        pipe = Pipeline("rapidocr")
        for page in pipe.process_paths([Path("scan.jpg")]):
            print(page.text)
    """

    def __init__(
        self,
        engine: str | OCREngine = "rapidocr",
        preprocessing: PreprocessConfig | None = None,
        review: ReviewPolicy | None = None,
        **engine_options: Any,
    ) -> None:
        self.engine = create_engine(engine, **engine_options) if isinstance(engine, str) else engine
        self.preprocessing = preprocessing or PreprocessConfig()
        self.review = review or ReviewPolicy()

    def process_page(self, page: LoadedPage) -> PageResult:
        return self.process_page_with_image(page)[0]

    def process_page_with_image(self, page: LoadedPage) -> tuple[PageResult, RGBImage]:
        """Like :meth:`process_page`, also returning the preprocessed image (for display)."""
        t0 = time.perf_counter()
        image, steps = preprocess(page.image, self.preprocessing)
        t1 = time.perf_counter()
        lines = self.engine.recognize(image)
        t2 = time.perf_counter()
        apply_review(lines, self.review)
        t3 = time.perf_counter()

        result = PageResult(
            page_id=page.page_id,
            engine=self.engine.name,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            lines=lines,
            preprocessing=steps,
            timings_ms={
                "preprocess": round((t1 - t0) * 1000, 1),
                "recognize": round((t2 - t1) * 1000, 1),
                "review": round((t3 - t2) * 1000, 1),
            },
        )
        # Metadata only: never the text or the original filename.
        log.info(
            "page=%s lines=%d review=%d ms=%s",
            page.page_id,
            len(lines),
            result.review_count,
            result.timings_ms,
        )
        return result, image

    def process_bytes(self, data: bytes) -> list[PageResult]:
        return [self.process_page(page) for page in load_bytes(data)]

    def process_paths(self, paths: list[Path]) -> Iterator[tuple[Path, PageResult]]:
        for path in iter_input_files(paths):
            for page in load_path(path):
                yield path, self.process_page(page)
