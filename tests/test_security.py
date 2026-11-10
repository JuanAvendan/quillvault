from __future__ import annotations

import logging
import os

import pytest

from quillvault.security import offline
from quillvault.security.network import NonLocalEndpointError, ensure_loopback_url
from quillvault.security.redaction import RedactingFilter, redact
from quillvault.security.tempfiles import (
    make_private_dir,
    private_tempdir,
    purge_stale_dirs,
    remove_tree,
)


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:8080", "http://localhost:8080/v1", "http://[::1]:9000"]
)
def test_loopback_urls_are_allowed(url):
    assert ensure_loopback_url(url) == url


@pytest.mark.parametrize(
    "url",
    ["http://8.8.8.8:8080", "https://10.0.0.5", "ftp://127.0.0.1", "127.0.0.1:8080", "http://"],
)
def test_non_local_urls_are_rejected(url):
    with pytest.raises(NonLocalEndpointError):
        ensure_loopback_url(url)


def test_redaction_masks_identifiers():
    message = "fallo leyendo C:\\Users\\ana\\pacientes\\juan_perez.jpg CC 1.023.456.789 ana@x.co"
    cleaned = redact(message)
    assert "juan_perez" not in cleaned
    assert "1.023.456.789" not in cleaned
    assert "ana@x.co" not in cleaned
    assert "[PATH]" in cleaned
    assert "[NUMBER]" in cleaned
    assert "[EMAIL]" in cleaned


def test_redacting_filter_formats_args_first():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "doc %s", ("1234567890",), None)
    RedactingFilter().filter(record)
    assert record.getMessage() == "doc [NUMBER]"


def test_offline_mode_can_be_enforced_and_lifted(monkeypatch):
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        monkeypatch.delenv(key, raising=False)
    offline.enforce_offline()
    assert offline.is_offline()
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
    offline.allow_model_downloads()
    assert not offline.is_offline()


def test_telemetry_is_disabled_on_import():
    import quillvault  # noqa: F401

    assert os.environ["GRADIO_ANALYTICS_ENABLED"] == "False"
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"


def test_stale_dirs_from_killed_sessions_are_purged():
    import subprocess
    import sys

    finished = subprocess.run([sys.executable, "-c", "pass"], check=True)
    assert finished.returncode == 0
    dead_pid = subprocess.Popen([sys.executable, "-c", "pass"])
    dead_pid.wait()

    prefix = "quillvault-test-stale-"
    stale = make_private_dir(prefix)
    (stale / ".owner-pid").write_text(str(dead_pid.pid), encoding="ascii")
    (stale / "scan.png").write_bytes(b"secret")
    alive = make_private_dir(prefix)  # owned by this test process

    try:
        assert purge_stale_dirs(prefix) == 1
        assert not stale.exists()
        assert alive.exists()
    finally:
        remove_tree(alive)
        remove_tree(stale)


def test_private_tempdir_is_always_removed():
    with pytest.raises(RuntimeError), private_tempdir() as path:
        (path / "scan.png").write_bytes(b"secret")
        (path / "nested").mkdir()
        (path / "nested" / "x.txt").write_text("secret")
        kept = path
        raise RuntimeError("boom")
    assert not kept.exists()
