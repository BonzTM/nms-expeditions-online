"""Tests for the DNS resolution module."""

import struct

from nms_expeditions_online.dns_resolve import (
    FALLBACK_IPS,
    NMS_HOSTNAMES,
    _build_dns_query,
    _parse_dns_response,
    resolve_all,
)


def test_nms_hostnames_match_fallback_keys():
    assert NMS_HOSTNAMES == list(FALLBACK_IPS.keys())


def test_build_dns_query_structure():
    query = _build_dns_query("example.com")
    # Header is 12 bytes
    assert len(query) > 12
    # Standard query with recursion desired
    flags = struct.unpack("!H", query[2:4])[0]
    assert flags == 0x0100
    # QDCOUNT = 1
    qdcount = struct.unpack("!H", query[4:6])[0]
    assert qdcount == 1


def test_build_dns_query_labels():
    query = _build_dns_query("merged-nms-auth.nomanssky.com")
    # After the 12-byte header, the question section should encode
    # "merged-nms-auth" (15), "nomanssky" (9), "com" (3)
    pos = 12
    label_len = query[pos]
    assert label_len == 15
    assert query[pos + 1 : pos + 1 + 15] == b"merged-nms-auth"


def test_parse_dns_response_empty():
    assert _parse_dns_response(b"") is None
    assert _parse_dns_response(b"\x00" * 8) is None


def test_parse_dns_response_no_answers():
    # Valid header with ANCOUNT=0
    header = struct.pack("!HHHHHH", 0x1234, 0x8180, 1, 0, 0, 0)
    # Minimal question section: single label "a", null, QTYPE=A, QCLASS=IN
    question = b"\x01a\x00" + struct.pack("!HH", 1, 1)
    assert _parse_dns_response(header + question) is None


def test_parse_dns_response_valid_a_record():
    # Build a minimal response with one A record
    header = struct.pack("!HHHHHH", 0x1234, 0x8180, 1, 1, 0, 0)
    # Question: "a.com" -> \x01a\x03com\x00, QTYPE=A, QCLASS=IN
    question = b"\x01a\x03com\x00" + struct.pack("!HH", 1, 1)
    # Answer: pointer to name at offset 12 (0xC00C), then TYPE=A, CLASS=IN, TTL=300, RDLENGTH=4, RDATA=1.2.3.4
    answer = struct.pack("!H", 0xC00C) + struct.pack("!HHIH", 1, 1, 300, 4) + bytes([1, 2, 3, 4])
    result = _parse_dns_response(header + question + answer)
    assert result == "1.2.3.4"


def test_resolve_all_uses_fallbacks(monkeypatch):
    """When DNS resolution fails, resolve_all should fall back to hardcoded IPs."""
    monkeypatch.setattr(
        "nms_expeditions_online.dns_resolve.resolve_bypass_hosts",
        lambda *args, **kwargs: None,
    )
    result = resolve_all()
    assert result == FALLBACK_IPS
