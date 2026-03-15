"""Tests for proxy HTTP parsing and response modification."""

import json
import os
import tempfile

from nms_expeditions_online.proxy import (
    NMSProxy,
    decode_chunked,
    rebuild_response,
)

# --- decode_chunked ---


def test_decode_chunked_single_chunk():
    data = b"5\r\nhello\r\n0\r\n\r\n"
    assert decode_chunked(data) == b"hello"


def test_decode_chunked_multiple_chunks():
    data = b"5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n"
    assert decode_chunked(data) == b"hello world"


def test_decode_chunked_empty():
    data = b"0\r\n\r\n"
    assert decode_chunked(data) == b""


def test_decode_chunked_hex_sizes():
    # 0xa = 10 bytes
    data = b"a\r\n0123456789\r\n0\r\n\r\n"
    assert decode_chunked(data) == b"0123456789"


# --- rebuild_response ---


def test_rebuild_response_basic():
    headers = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 3\r\n\r\n"
    body = b"hello world"
    result = rebuild_response(headers, body)
    assert b"Content-Length: 11" in result
    assert result.endswith(b"hello world")


def test_rebuild_response_removes_chunked():
    headers = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
    body = b"test"
    result = rebuild_response(headers, body)
    assert b"Transfer-Encoding" not in result
    assert b"Content-Length: 4" in result


def test_rebuild_response_force_200():
    headers = b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n"
    body = b'{"ok": true}'
    result = rebuild_response(headers, body, force_200=True)
    assert b"HTTP/1.1 200 OK" in result
    assert b"Content-Length: 12" in result


def test_rebuild_response_force_200_adds_content_type():
    headers = b"HTTP/1.1 403 Forbidden\r\n\r\n"
    body = b'{"ok": true}'
    result = rebuild_response(headers, body, force_200=True)
    assert b"Content-Type: application/json" in result


# --- NMSProxy.maybe_modify ---


def _make_proxy(season_id=1, hash_val=12345, start=1000, end=2000):
    """Create an NMSProxy from a temporary expedition JSON."""
    data = {
        "SeasonId": season_id,
        "Hash": hash_val,
        "StartTimeUTC": start,
        "EndTimeUTC": end,
        "Description": "Test Expedition",
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    try:
        return NMSProxy(path)
    finally:
        os.unlink(path)


def test_maybe_modify_season_endpoint():
    proxy = _make_proxy(season_id=42)
    result = proxy.maybe_modify("merged-nms-static.nomanssky.com", "/season", b"")
    assert result is not None
    data = json.loads(result)
    assert data["SeasonId"] == 42


def test_maybe_modify_auth_endpoint():
    proxy = _make_proxy(season_id=7, hash_val=99999)
    auth_response = {
        "settings": {
            "seasonData": {
                "currentSeason": 1,
                "Hash": 11111,
                "StartDate": 0,
                "EndDate": 0,
                "nextSeason": 2,
                "nextStartDate": 9999,
            }
        }
    }
    body = json.dumps(auth_response).encode()
    result = proxy.maybe_modify("merged-nms-auth.nomanssky.com", "/Steam", body)
    assert result is not None
    patched = json.loads(result)
    sd = patched["settings"]["seasonData"]
    assert sd["currentSeason"] == 7
    assert sd["Hash"] == 99999
    assert sd["nextSeason"] == 0


def test_maybe_modify_passthrough():
    proxy = _make_proxy()
    # Discovery endpoint should not be modified
    result = proxy.maybe_modify(
        "merged-nms-discovery.nomanssky.com", "/some-endpoint", b'{"data": 1}'
    )
    assert result is None


def test_maybe_modify_auth_no_season_data():
    proxy = _make_proxy()
    # Auth response without seasonData should not crash
    body = json.dumps({"settings": {}}).encode()
    result = proxy.maybe_modify("merged-nms-auth.nomanssky.com", "/Steam", body)
    assert result is None


def test_maybe_modify_auth_invalid_json():
    proxy = _make_proxy()
    result = proxy.maybe_modify(
        "merged-nms-auth.nomanssky.com", "/Steam", b"not json"
    )
    assert result is None
