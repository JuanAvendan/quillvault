from __future__ import annotations

import pytest

from quillvault import Pipeline
from quillvault.engines.base import create_engine, sort_reading_order
from quillvault.imaging.preprocess import PreprocessConfig
from quillvault.postprocess.review import ReviewPolicy
from quillvault.types import TextLine


def test_pipeline_runs_end_to_end_with_any_engine(fake_engine, make_png, text_image):
    pipe = Pipeline(fake_engine(["Paciente Ana", "TA 120/80"]), PreprocessConfig.disabled())
    [page] = pipe.process_bytes(make_png(text_image))
    assert page.text == "Paciente Ana\nTA 120/80"
    assert page.engine == "fake"
    assert set(page.timings_ms) == {"preprocess", "recognize", "review"}
    assert page.review_count == 0
    assert page.mean_confidence == pytest.approx(0.95)


def test_pipeline_applies_review_policy(fake_engine, make_png, text_image):
    pipe = Pipeline(fake_engine(["x"], confidence=0.5), review=ReviewPolicy(min_confidence=0.9))
    [page] = pipe.process_bytes(make_png(text_image))
    assert page.lines[0].needs_review


def test_process_paths_yields_source_and_result(tmp_path, fake_engine, make_png, text_image):
    (tmp_path / "a.png").write_bytes(make_png(text_image))
    results = list(Pipeline(fake_engine(["hola"])).process_paths([tmp_path]))
    assert [(p.name, r.text) for p, r in results] == [("a.png", "hola")]


def test_page_result_serialises_without_filename(fake_engine, make_png, text_image):
    pipe = Pipeline(fake_engine(["hola"]))
    data = pipe.process_bytes(make_png(text_image))[0].to_dict()
    assert data["text"] == "hola"
    assert "path" not in data
    assert "filename" not in data


def test_reading_order_groups_rows_then_left_to_right():
    def box(x: float, y: float) -> tuple[tuple[float, float], ...]:
        return ((x, y), (x + 50, y), (x + 50, y + 30), (x, y + 30))

    lines = [
        TextLine("C", 1, box(10, 100)),
        TextLine("B", 1, box(300, 12)),
        TextLine("A", 1, box(10, 10)),
    ]
    assert [ln.text for ln in sort_reading_order(lines)] == ["A", "B", "C"]


def test_unknown_engine_name():
    with pytest.raises(ValueError, match="Unknown engine"):
        create_engine("tesseract")
