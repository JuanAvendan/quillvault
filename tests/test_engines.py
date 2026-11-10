from __future__ import annotations

import json

import httpx
import pytest

from quillvault.engines.vlm import VLMEngine
from quillvault.security.network import NonLocalEndpointError
from tests.conftest import render_text


# --------------------------------------------------------------------------- RapidOCR
@pytest.fixture(scope="module")
def rapid():
    pytest.importorskip("onnxruntime")
    from quillvault.engines.rapid import RapidOCREngine

    return RapidOCREngine(device="cpu")


def test_rapidocr_reads_printed_text_offline(rapid):
    image = render_text(["Control en 15 dias", "Paciente Ana Ruiz"], size=48)
    lines = rapid.recognize(image)
    text = " ".join(ln.text for ln in lines).lower()
    assert "control" in text
    assert "paciente" in text
    assert lines[0].top < lines[-1].top  # reading order
    assert all(0 <= ln.confidence <= 1 for ln in lines)
    assert all(len(ln.polygon) == 4 for ln in lines)


def test_rapidocr_detect_only(rapid):
    polygons = rapid.detect(render_text(["uno dos tres", "cuatro cinco"], size=48))
    assert len(polygons) >= 2


def test_rapidocr_blank_page(rapid):
    import numpy as np

    assert rapid.recognize(np.full((300, 300, 3), 255, dtype=np.uint8)) == []


# --------------------------------------------------------------------------- VLM
def _mock_server(reply: str, seen: list[dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    return httpx.MockTransport(handler)


def test_vlm_page_mode_marks_every_line_for_review(text_image):
    seen: list[dict] = []
    engine = VLMEngine(transport=_mock_server("Paciente Ana\nControl en [?] días\n", seen))
    lines = engine.recognize(text_image)

    assert [ln.text for ln in lines] == ["Paciente Ana", "Control en [?] días"]
    assert all(ln.needs_review and ln.confidence is None for ln in lines)
    assert lines[1].issues == ["illegible"]

    content = seen[0]["messages"][0]["content"]
    assert seen[0]["temperature"] == 0
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_vlm_refuses_remote_endpoints():
    with pytest.raises(NonLocalEndpointError):
        VLMEngine(url="http://8.8.8.8:8080")


def test_vlm_explains_missing_server(text_image):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    engine = VLMEngine(transport=httpx.MockTransport(refuse))
    with pytest.raises(RuntimeError, match="vlm-setup"):
        engine.recognize(text_image)


def test_vlm_ignores_proxy_environment(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://evil.example:3128")
    monkeypatch.setenv("HTTP_PROXY", "http://evil.example:3128")
    engine = VLMEngine()
    assert engine._client._trust_env is False
