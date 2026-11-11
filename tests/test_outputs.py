"""Exporters, benchmark, practice sheets and UI helpers."""

from __future__ import annotations

import json

import pytest

from quillvault import benchmark, export
from quillvault.pipeline import Pipeline
from quillvault.types import PageResult, TextLine
from quillvault.ui.app import apply_edits, rows_from_pages, text_from_rows


@pytest.fixture
def pages() -> list[PageResult]:
    return [
        PageResult(
            "abc123-p001",
            "fake",
            800,
            600,
            [
                TextLine("Paciente | Ana", 0.97, ((0, 0), (10, 0), (10, 5), (0, 5))),
                TextLine("CC 1O23456", 0.6, needs_review=True, issues=["confianza baja (60%)"]),
            ],
        )
    ]


def test_txt_json_markdown(pages):
    assert export.to_txt(pages) == "Paciente | Ana\nCC 1O23456\n"
    data = json.loads(export.to_json(pages))
    assert data[0]["review_count"] == 1
    assert data[0]["lines"][0]["text"] == "Paciente | Ana"
    md = export.to_markdown(pages)
    assert "Paciente \\| Ana" in md
    assert "⚠️" in md


def test_write_refuses_to_overwrite(tmp_path):
    target = tmp_path / "out" / "a.txt"
    export.write(target, "1")
    with pytest.raises(FileExistsError):
        export.write(target, "2")
    export.write(target, "3", overwrite=True)
    assert target.read_text(encoding="utf-8") == "3"


def test_annotate_keeps_shape(pages, text_image):
    out = export.annotate(text_image, pages[0])
    assert out.shape == text_image.shape
    assert (out != text_image).any()


# --------------------------------------------------------------------------- benchmark
def test_benchmark_scores_without_leaking_text(tmp_path, fake_engine, make_png, text_image):
    for i in (1, 2):
        (tmp_path / f"pagina_00{i}.png").write_bytes(make_png(text_image))
        (tmp_path / f"pagina_00{i}.txt").write_text("Paciente Ana\nControl", encoding="utf-8")
    samples = benchmark.load_dataset(tmp_path)

    perfect = benchmark.score_engine(
        "perfect", Pipeline(fake_engine(["Paciente Ana", "Control"])), samples
    )
    sloppy = benchmark.score_engine(
        "sloppy", Pipeline(fake_engine(["paciente Aná", "Contro1"])), samples
    )

    assert perfect.cer == 0
    assert perfect.wer == 0
    assert sloppy.cer > 0
    assert sloppy.cer_relaxed < sloppy.cer  # case/accent errors are discounted
    report = benchmark.to_markdown([sloppy, perfect]) + benchmark.to_json([sloppy, perfect])
    assert "Paciente" not in report
    assert report.index("| perfect") < report.index("| sloppy")


def test_benchmark_requires_pairs(tmp_path):
    with pytest.raises(FileNotFoundError):
        benchmark.load_dataset(tmp_path)


# --------------------------------------------------------------------------- templates
def test_practice_sheets_are_reproducible(tmp_path):
    pytest.importorskip("reportlab")
    pytest.importorskip("faker")
    from quillvault.templates import generate, generate_lines

    result = generate(tmp_path, pages=2, lines_per_page=5, seed=3)
    assert result.pdf.read_bytes().startswith(b"%PDF")
    assert [p.name for p in result.ground_truth] == ["pagina_001.txt", "pagina_002.txt"]
    assert len(result.ground_truth[0].read_text(encoding="utf-8").splitlines()) == 5
    assert generate_lines(2, 5, seed=3) == generate_lines(2, 5, seed=3)
    assert generate_lines(2, 5, seed=3) != generate_lines(2, 5, seed=4)


def test_note_sheets_read_like_one_consistent_note():
    from quillvault.postprocess.lexicon import Lexicon
    from quillvault.templates import _section_plan, generate_lines

    for n in (1, 5, 12, 16):
        plan = _section_plan(n)
        assert len(plan) == n
        assert plan == sorted(plan)  # reason → history → exam → dx → plan
    assert _section_plan(12).count(3) == 1  # a single diagnosis line

    lexicon = Lexicon.builtin()
    for page in generate_lines(50, 12, seed=1):
        assert len(page) == len(set(page)) == 12
        assert sum(line.startswith(("Dx:", "Impresión dx:")) for line in page) == 1
        # Correct clinical words must not be flagged as misspellings.
        assert not any(lexicon.suggest(line) for line in page)


def test_form_style_and_unknown_style():
    pytest.importorskip("faker")
    from quillvault.templates import generate_lines

    (page,) = generate_lines(1, 16, seed=2, style="form")
    assert len(page) == 16
    with pytest.raises(ValueError, match="Unknown style"):
        generate_lines(1, 3, seed=2, style="poema")


# --------------------------------------------------------------------------- UI helpers
def test_review_table_round_trip(pages):
    rows = rows_from_pages(pages)
    assert rows[0][:5] == [1, 1, "Paciente | Ana", "97%", "✅"]
    assert rows[1][4] == "⚠️"

    rows[1][2] = "CC 1023456"
    assert text_from_rows(rows) == "Paciente | Ana\nCC 1023456"

    edited = apply_edits(pages, rows)
    assert edited[0].lines[1].text == "CC 1023456"
    assert "corregido manualmente" in edited[0].lines[1].issues
    assert pages[0].lines[1].text == "CC 1O23456"  # original untouched
