"""HTTPS reverse proxy that intercepts NMS season data and auth responses."""

import asyncio
import datetime
import json
import os
import ssl
import tempfile
import threading
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from nms_expeditions_online.dns_resolve import resolve_all

_ca_key = None
_ca_cert = None
_ssl_ctx_cache: dict[str, ssl.SSLContext] = {}
_sni_map: dict[int, str] = {}

REAL_IPS: dict[str, str] = {}


def init_ca():
    """Generate an ephemeral CA certificate (in-memory only)."""
    global _ca_key, _ca_cert
    _ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "NMS Expedition Proxy CA")])
    _ca_cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(_ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(_ca_key, hashes.SHA256())
    )


def _make_host_cert(hostname: str) -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)]))
        .issuer_name(_ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
        .sign(_ca_key, hashes.SHA256())
    )
    cf = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    cf.write(cert.public_bytes(serialization.Encoding.PEM)); cf.close()
    kf = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    kf.write(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())); kf.close()
    return cf.name, kf.name


def get_server_ssl_ctx(hostname: str) -> ssl.SSLContext:
    if hostname not in _ssl_ctx_cache:
        cert_path, key_path = _make_host_cert(hostname)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_path, key_path)
        os.unlink(cert_path)
        os.unlink(key_path)
        _ssl_ctx_cache[hostname] = ctx
    return _ssl_ctx_cache[hostname]


def sni_callback(ssl_socket, hostname, _ctx):
    if hostname:
        ssl_socket.context = get_server_ssl_ctx(hostname)
        _sni_map[id(ssl_socket)] = hostname


async def read_http(reader: asyncio.StreamReader) -> bytes:
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = await reader.read(8192)
        if not chunk:
            return buf
        buf += chunk

    hdr_end = buf.index(b"\r\n\r\n") + 4
    headers = buf[:hdr_end]
    body = buf[hdr_end:]
    hdrs_lower = headers.decode("utf-8", errors="replace").lower()

    for line in hdrs_lower.split("\r\n"):
        if line.startswith("content-length:"):
            cl = int(line.split(":", 1)[1].strip())
            while len(body) < cl:
                chunk = await reader.read(min(65536, cl - len(body)))
                if not chunk:
                    break
                body += chunk
            return headers + body

    if "transfer-encoding: chunked" in hdrs_lower:
        while not body.endswith(b"0\r\n\r\n"):
            chunk = await reader.read(8192)
            if not chunk:
                break
            body += chunk
        return headers + body

    return headers + body


def decode_chunked(data: bytes) -> bytes:
    result, pos = b"", 0
    while pos < len(data):
        end = data.find(b"\r\n", pos)
        if end < 0: break
        size_str = data[pos:end].decode("ascii", errors="replace").split(";")[0].strip()
        size = int(size_str, 16)
        if size == 0: break
        pos = end + 2
        result += data[pos:pos + size]
        pos += size + 2
    return result


def rebuild_response(headers: bytes, body: bytes, force_200: bool = False) -> bytes:
    lines = headers.decode("utf-8", errors="replace").rstrip("\r\n").split("\r\n")
    if force_200 and lines:
        # Replace status line (e.g. "HTTP/1.1 204 No Content" -> "HTTP/1.1 200 OK")
        parts = lines[0].split(" ", 2)
        if len(parts) >= 2:
            lines[0] = f"{parts[0]} 200 OK"
    out = [l for l in lines if not l.lower().startswith(("content-length:", "transfer-encoding:"))]
    out.append(f"Content-Length: {len(body)}")
    # Ensure Content-Type is present when we're injecting a body into a 204
    if force_200 and not any(l.lower().startswith("content-type:") for l in out):
        out.insert(1, "Content-Type: application/json; charset=utf-8")
    return "\r\n".join(out).encode() + b"\r\n\r\n" + body


class NMSProxy:
    def __init__(self, expedition_path: str):
        with open(expedition_path) as f:
            data = json.load(f)
        self.meta = {
            "SeasonId": data.get("SeasonId", 0),
            "Hash": data.get("Hash", 99999999),
            "StartTimeUTC": data.get("StartTimeUTC", 0),
            "EndTimeUTC": data.get("EndTimeUTC", 0),
        }
        self.expedition_body = json.dumps(data, separators=(",", ":")).encode("utf-8")

    def maybe_modify(self, host: str, path: str, body: bytes) -> bytes | None:
        if "nms-static" in host and path == "/season":
            print(f"  [INTERCEPTED] /season -> custom expedition (SeasonId={self.meta['SeasonId']})")
            return self.expedition_body

        if "nms-auth" in host and path == "/Steam":
            try:
                auth = json.loads(body)
                sd = auth.get("settings", {}).get("seasonData")
                if sd:
                    old = sd.get("currentSeason")
                    sd.update({
                        "currentSeason": self.meta["SeasonId"],
                        "Hash": self.meta["Hash"],
                        "StartDate": self.meta["StartTimeUTC"],
                        "EndDate": self.meta["EndTimeUTC"],
                        "nextSeason": 0, "nextStartDate": 0,
                    })
                    print(f"  [INTERCEPTED] Auth (currentSeason: {old} -> {self.meta['SeasonId']})")
                    return json.dumps(auth, separators=(",", ":")).encode("utf-8")
            except Exception as e:
                print(f"  [ERROR] Auth patch: {e}")
        return None

    async def handle(self, client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter):
        peer = client_w.get_extra_info("peername")
        hostname = getattr(client_w, "_nms_hostname", None)
        if not hostname:
            ssl_obj = client_w.get_extra_info("ssl_object")
            hostname = _sni_map.pop(id(ssl_obj), None) if ssl_obj else None

        if not hostname or hostname not in REAL_IPS:
            try:
                client_w.close()
            except Exception:
                pass
            return

        real_ip = REAL_IPS[hostname]

        try:
            req = await asyncio.wait_for(read_http(client_r), timeout=30)
            if not req:
                return

            first_line = req.split(b"\r\n")[0].decode("utf-8", errors="replace")
            parts = first_line.split(" ", 2)
            path = parts[1] if len(parts) > 1 else "/"
            print(f"  {parts[0]} https://{hostname}{path}")

            up_ctx = ssl.create_default_context()
            up_r, up_w = await asyncio.wait_for(
                asyncio.open_connection(real_ip, 443, ssl=up_ctx, server_hostname=hostname),
                timeout=15,
            )

            up_w.write(req)
            await up_w.drain()

            resp = await asyncio.wait_for(read_http(up_r), timeout=30)

            hdr_end = resp.find(b"\r\n\r\n")
            if hdr_end >= 0:
                hdrs = resp[:hdr_end + 4]
                body = resp[hdr_end + 4:]
                was_chunked = b"transfer-encoding: chunked" in hdrs.lower()
                if was_chunked:
                    body = decode_chunked(body)
                modified = self.maybe_modify(hostname, path, body)
                if modified is not None:
                    resp = rebuild_response(hdrs, modified, force_200=True)
                elif was_chunked:
                    resp = rebuild_response(hdrs, body)

            client_w.write(resp)
            await client_w.drain()

            up_w.close()
            await up_w.wait_closed()

        except asyncio.TimeoutError:
            pass
        except ConnectionResetError:
            pass
        except Exception as e:
            print(f"  [ERROR] {e}")
        finally:
            try:
                client_w.close()
                await client_w.wait_closed()
            except Exception:
                pass


async def _run_server(proxy: NMSProxy, port: int, stop_event: threading.Event):
    default_cert, default_key = _make_host_cert("nomanssky.com")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(default_cert, default_key)
    os.unlink(default_cert)
    os.unlink(default_key)
    ctx.sni_callback = sni_callback

    async def raw_handler(reader, writer):
        peer = writer.get_extra_info("peername")
        try:
            transport = writer.transport
            loop = asyncio.get_event_loop()

            new_transport = await loop.start_tls(
                transport, transport.get_protocol(), ctx, server_side=True,
            )

            ssl_obj = new_transport.get_extra_info("ssl_object")
            hostname = _sni_map.pop(id(ssl_obj), None)
            if not hostname:
                for sid, sname in list(_sni_map.items()):
                    hostname = sname
                    del _sni_map[sid]
                    break

            reader._transport = new_transport
            writer._transport = new_transport
            writer._nms_hostname = hostname

            await proxy.handle(reader, writer)

        except ssl.SSLError:
            pass
        except Exception:
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass

    server = await asyncio.start_server(raw_handler, "0.0.0.0", port)

    # Check for stop event periodically
    async def watch_stop():
        while not stop_event.is_set():
            await asyncio.sleep(0.5)
        server.close()
        await server.wait_closed()

    await asyncio.gather(server.serve_forever(), watch_stop(), return_exceptions=True)


def start_proxy(expedition_path: str, port: int = 443) -> tuple[threading.Thread, threading.Event]:
    """Start the proxy in a background thread. Returns (thread, stop_event)."""
    global REAL_IPS

    print("Resolving NMS server IPs...")
    REAL_IPS = resolve_all()
    for hostname, ip in REAL_IPS.items():
        print(f"  {hostname} -> {ip}")

    init_ca()
    proxy = NMSProxy(expedition_path)
    print(f"Loaded expedition: SeasonId={proxy.meta['SeasonId']}")

    stop_event = threading.Event()

    def run():
        try:
            asyncio.run(_run_server(proxy, port, stop_event))
        except OSError as e:
            if "address already in use" in str(e).lower() or e.errno == 98 or e.errno == 10048:
                print(f"\nERROR: Port {port} is already in use.")
                print("Close any web servers, VPNs, or other software using port 443 and try again.")
            else:
                print(f"\nERROR: {e}")
        except Exception as e:
            print(f"\nERROR: {e}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, stop_event
