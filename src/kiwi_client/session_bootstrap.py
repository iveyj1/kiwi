"""Browser-compatible KiwiSDR HTTP/WebSocket session bootstrap."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Callable
from urllib.request import Request, urlopen

DEFAULT_BOOTSTRAP_TIMEOUT_SECONDS = 5.0


class KiwiBootstrapError(RuntimeError):
    """Raised when the browser-compatible HTTP bootstrap fails."""


def browser_websocket_uri(host: str, port: int, timestamp: int, stream: str) -> str:
    """Build the WebSocket path used by the KiwiSDR browser client."""
    return f"ws://{host}:{port}/ws/kiwi/{timestamp}/{stream}"


def fallback_connection_timestamp() -> int:
    """Return the browser's millisecond timestamp fallback."""
    return int(time.time() * 1000)


def fetch_connection_timestamp(
    host: str,
    port: int,
    *,
    opener=urlopen,
    timeout: float = DEFAULT_BOOTSTRAP_TIMEOUT_SECONDS,
) -> int:
    """Fetch the server-issued connection timestamp from the browser /VER endpoint."""
    url = f"http://{host}:{port}/VER"
    request = Request(url, headers={"User-Agent": "kiwi-client"})
    try:
        with opener(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
        timestamp = value.get("ts")
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            raise ValueError("missing integer ts")
        return timestamp
    except Exception as exc:
        raise KiwiBootstrapError(f"invalid /VER response from {host}:{port}: {exc}") from exc


async def resolve_connection_timestamp(
    host: str,
    port: int,
    *,
    fetcher: Callable[[str, int], int] = fetch_connection_timestamp,
) -> int:
    """Resolve /VER without blocking the asyncio event loop."""
    return await asyncio.to_thread(fetcher, host, port)
