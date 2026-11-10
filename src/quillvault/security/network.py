"""Guards that keep sensitive data on this machine."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class NonLocalEndpointError(ValueError):
    """Raised when a URL would send data off this machine."""


def ensure_loopback_url(url: str) -> str:
    """Return ``url`` unchanged if, and only if, every address it resolves to is loopback.

    Used for the local vision-language model server: an accidental
    ``--vlm-url https://some-cloud`` must never upload a patient's document.
    """
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise NonLocalEndpointError(f"Not an http(s) URL: {url!r}")

    host = parts.hostname
    try:
        infos = socket.getaddrinfo(host, parts.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise NonLocalEndpointError(f"Cannot resolve {host!r}") from exc

    addresses = {str(info[4][0]) for info in infos}
    for address in addresses:
        if not ipaddress.ip_address(address.split("%", 1)[0]).is_loopback:
            raise NonLocalEndpointError(
                f"{host!r} resolves to {address}, which is not a loopback address. "
                "QuillVault only talks to model servers running on this machine."
            )
    return url
