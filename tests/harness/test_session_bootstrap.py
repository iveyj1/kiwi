import asyncio
import io

import pytest

from kiwi_client.session_bootstrap import KiwiBootstrapError, fetch_connection_timestamp, resolve_connection_timestamp


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_fetch_connection_timestamp_uses_browser_ver_endpoint():
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, request.headers, timeout))
        return Response(b'{"maj":1,"min":902,"ts":4611686286989819482,"sp":0}')

    timestamp = fetch_connection_timestamp("kiwi.example", 8073, opener=opener, timeout=2.5)

    assert timestamp == 4611686286989819482
    assert calls[0][0] == "http://kiwi.example:8073/VER"
    assert calls[0][2] == 2.5


def test_fetch_connection_timestamp_rejects_invalid_ver_response():
    with pytest.raises(KiwiBootstrapError, match="invalid /VER"):
        fetch_connection_timestamp(
            "kiwi.example",
            8073,
            opener=lambda *args, **kwargs: Response(b'{"maj":1,"min":902}'),
        )


def test_resolve_connection_timestamp_runs_http_bootstrap_off_loop():
    async def exercise():
        return await resolve_connection_timestamp(
            "kiwi.example",
            8073,
            fetcher=lambda host, port: 987654321,
        )

    assert asyncio.run(exercise()) == 987654321
