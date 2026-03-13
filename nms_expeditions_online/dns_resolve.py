"""Cross-platform DNS resolution that bypasses /etc/hosts and system resolver."""

import socket
import struct

FALLBACK_IPS = {
    "merged-nms-auth.nomanssky.com": "20.49.104.38",
    "merged-nms-static.nomanssky.com": "51.8.48.186",
    "merged-nms-discovery.nomanssky.com": "20.49.104.38",
    "merged-nms-contentreport.nomanssky.com": "20.49.104.38",
}

NMS_HOSTNAMES = list(FALLBACK_IPS.keys())


def _build_dns_query(hostname: str) -> bytes:
    """Build a minimal DNS A record query."""
    # Header: ID=0x1234, flags=0x0100 (standard query, recursion desired),
    # QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=0
    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)

    # Question section
    question = b""
    for label in hostname.split("."):
        question += struct.pack("!B", len(label)) + label.encode("ascii")
    question += b"\x00"  # root label
    question += struct.pack("!HH", 1, 1)  # QTYPE=A, QCLASS=IN

    return header + question


def _parse_dns_response(data: bytes) -> str | None:
    """Parse a DNS response and return the first A record IP."""
    if len(data) < 12:
        return None

    ancount = struct.unpack("!H", data[6:8])[0]
    if ancount == 0:
        return None

    # Skip header (12 bytes) and question section
    pos = 12
    while pos < len(data):
        if data[pos] == 0:
            pos += 1 + 4  # null label + QTYPE + QCLASS
            break
        elif data[pos] & 0xC0 == 0xC0:
            pos += 2 + 4
            break
        else:
            pos += 1 + data[pos]

    # Parse answer records
    for _ in range(ancount):
        if pos >= len(data):
            break
        # Name (could be pointer or labels)
        if data[pos] & 0xC0 == 0xC0:
            pos += 2
        else:
            while pos < len(data) and data[pos] != 0:
                pos += 1 + data[pos]
            pos += 1

        if pos + 10 > len(data):
            break

        rtype, rclass, _, rdlength = struct.unpack("!HHIH", data[pos:pos + 10])
        pos += 10

        if rtype == 1 and rclass == 1 and rdlength == 4:
            return socket.inet_ntoa(data[pos:pos + 4])

        pos += rdlength

    return None


def resolve_bypass_hosts(hostname: str, nameserver: str = "8.8.8.8", timeout: float = 5.0) -> str | None:
    """Resolve a hostname by directly querying a DNS server, bypassing the system resolver."""
    try:
        query = _build_dns_query(hostname)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(query, (nameserver, 53))
        data, _ = sock.recvfrom(4096)
        sock.close()

        ip = _parse_dns_response(data)
        if ip:
            return ip
    except Exception:
        pass
    return None


def resolve_all() -> dict[str, str]:
    """Resolve all NMS hostnames, falling back to hardcoded IPs."""
    result = {}
    for hostname in NMS_HOSTNAMES:
        ip = resolve_bypass_hosts(hostname)
        if ip:
            result[hostname] = ip
        else:
            result[hostname] = FALLBACK_IPS[hostname]
    return result
