"""HTTP image download helper (standard library only)."""

from __future__ import annotations

import urllib.request

_DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    """Download ``url`` and return its raw bytes.

    Raises urllib's HTTPError / URLError on failure so callers can count
    failures (e.g. dead 404 source images) and continue.
    """
    request = urllib.request.Request(url, headers=_DEFAULT_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()
