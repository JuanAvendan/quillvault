from __future__ import annotations

import pytest
from typer.testing import CliRunner

from quillvault import __version__
from quillvault.cli import app
from tests.conftest import png_bytes, render_text

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_doctor_runs():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Offline mode" in result.stdout


def test_models_list():
    result = runner.invoke(app, ["models", "list"])
    assert result.exit_code == 0
    assert "trocr-base-handwritten" in result.stdout


def test_extract_writes_files_and_never_overwrites(tmp_path):
    pytest.importorskip("onnxruntime")
    scan = tmp_path / "scan.png"
    scan.write_bytes(png_bytes(render_text(["Control en 15 dias"], size=48)))
    out = tmp_path / "out"

    args = ["extract", str(scan), "--out", str(out), "--format", "json", "--device", "cpu"]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert (out / "scan.json").is_file()
    assert "control" in (out / "scan.json").read_text(encoding="utf-8").lower()

    second = runner.invoke(app, args)
    assert second.exit_code == 1


def test_templates_command(tmp_path):
    pytest.importorskip("reportlab")
    result = runner.invoke(app, ["templates", str(tmp_path), "--pages", "1", "--lines", "3"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "practice_sheets.pdf").is_file()
    assert (tmp_path / "pagina_001.txt").is_file()
