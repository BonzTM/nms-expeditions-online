"""HTTPS reverse proxy that intercepts NMS season data and auth responses."""

import datetime
import http.server
import json
import os
import platform
import socket
import ssl
import subprocess
import tempfile
import threading

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from nms_expeditions_online.dns_resolve import resolve_all
from nms_expeditions_online.platform_utils import _system32_path

_ca_key = None
_ca_cert = None
_ca_crl_der: bytes = b""
_sni_map: dict[int, str] = {}

CRL_PORT = 18625
REAL_IPS: dict[str, str] = {}

# Safety limits to prevent resource exhaustion
MAX_HEADER_SIZE = 64 * 1024       # 64 KB max for HTTP headers
MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB max for HTTP body
MAX_CONNECTIONS = 32               # max concurrent client connections


def init_ca() -> None:
    """Generate an ephemeral CA certificate and CRL (in-memory only)."""
    global _ca_key, _ca_cert, _ca_crl_der
    _ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "NMS Expedition Proxy CA")])
    _ca_cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(_ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(_ca_key, hashes.SHA256())
    )

    # Generate an empty CRL so SChannel revocation checks pass
    now = datetime.datetime.now(datetime.timezone.utc)
    _ca_crl_der = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(_ca_cert.subject)
        .last_update(now)
        .next_update(now + datetime.timedelta(days=2))
        .sign(_ca_key, hashes.SHA256())
    ).public_bytes(serialization.Encoding.DER)


CA_CERT_NAME = "NMS Expedition Proxy CA"


def install_ca_cert() -> bool:
    """Install the ephemeral CA cert into the OS trust store. Returns True on success."""
    if _ca_cert is None:
        return False

    if platform.system() == "Windows":
        # Remove any stale cert from a previous run first
        uninstall_ca_cert()

        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".cer")
        tf.write(_ca_cert.public_bytes(serialization.Encoding.DER))
        tf.close()
        try:
            result = subprocess.run(
                [_system32_path("certutil.exe"), "-addstore", "-f", "Root", tf.name],
                capture_output=True, text=True,
            )
            return result.returncode == 0
        finally:
            os.unlink(tf.name)
    else:
        # Linux/macOS: not needed (game typically runs via Proton which
        # doesn't validate against the system store)
        return True


def uninstall_ca_cert() -> None:
    """Remove the CA cert from the OS trust store."""
    if platform.system() == "Windows":
        subprocess.run(
            [_system32_path("certutil.exe"), "-delstore", "Root", CA_CERT_NAME],
            capture_output=True, text=True,
        )


def _make_server_cert() -> tuple[str, str]:
    """Create a single server cert covering all NMS hostnames."""
    from nms_expeditions_online.dns_resolve import NMS_HOSTNAMES
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    san_names = [x509.DNSName(h) for h in NMS_HOSTNAMES]
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "nomanssky.com")]))
        .issuer_name(_ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2))
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .add_extension(
            x509.CRLDistributionPoints([
                x509.DistributionPoint(
                    full_name=[x509.UniformResourceIdentifier(f"http://127.0.0.1:{CRL_PORT}/crl")],
                    relative_name=None, reasons=None, crl_issuer=None,
                )
            ]),
            critical=False,
        )
        .sign(_ca_key, hashes.SHA256())
    )
    cf = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    cf.write(cert.public_bytes(serialization.Encoding.PEM))
    cf.close()
    kf = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    kf.write(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption(),
    ))
    kf.close()
    return cf.name, kf.name


def _sni_hostname_callback(ssl_socket: ssl.SSLSocket, hostname: str | None, _ctx: ssl.SSLContext) -> None:
    """Extract the SNI hostname without switching contexts."""
    if hostname:
        _sni_map[id(ssl_socket)] = hostname


class _CRLHandler(http.server.BaseHTTPRequestHandler):
    """Serves the CA's CRL for SChannel revocation checks."""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/pkix-crl")
        self.send_header("Content-Length", str(len(_ca_crl_der)))
        self.end_headers()
        self.wfile.write(_ca_crl_der)

    def log_message(self, format: str, *args: object) -> None:
        pass  # suppress request logging


def _start_crl_server() -> http.server.HTTPServer | None:
    """Start a tiny HTTP server that serves the CRL. Windows only."""
    if platform.system() != "Windows":
        return None
    server = http.server.HTTPServer(("127.0.0.1", CRL_PORT), _CRLHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def _recv_all(sock, n: int) -> bytes:
    """Receive exactly n bytes from a socket."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(min(65536, n - len(buf)))
        if not chunk:
            return buf
        buf += chunk
    return buf


def read_http_sync(sock) -> bytes:
    """Read a complete HTTP request or response from a socket."""
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(8192)
        if not chunk:
            return buf
        buf += chunk
        if len(buf) > MAX_HEADER_SIZE:
            raise ValueError(f"HTTP headers exceed {MAX_HEADER_SIZE} bytes")

    hdr_end = buf.index(b"\r\n\r\n") + 4
    headers = buf[:hdr_end]
    body = buf[hdr_end:]
    hdrs_lower = headers.decode("utf-8", errors="replace").lower()

    for line in hdrs_lower.split("\r\n"):
        if line.startswith("content-length:"):
            cl = int(line.split(":", 1)[1].strip())
            if cl > MAX_BODY_SIZE:
                raise ValueError(f"Content-Length {cl} exceeds {MAX_BODY_SIZE} bytes")
            remaining = cl - len(body)
            if remaining > 0:
                body += _recv_all(sock, remaining)
            return headers + body

    if "transfer-encoding: chunked" in hdrs_lower:
        while b"\r\n0\r\n" not in body and not body.startswith(b"0\r\n"):
            chunk = sock.recv(8192)
            if not chunk:
                break
            body += chunk
            if len(body) > MAX_BODY_SIZE:
                raise ValueError(f"Chunked body exceeds {MAX_BODY_SIZE} bytes")
        while not body.endswith(b"\r\n\r\n"):
            chunk = sock.recv(8192)
            if not chunk:
                break
            body += chunk
        return headers + body

    return headers + body


def decode_chunked(data: bytes) -> bytes:
    result, pos = b"", 0
    while pos < len(data):
        end = data.find(b"\r\n", pos)
        if end < 0:
            break
        size_str = data[pos:end].decode("ascii", errors="replace").split(";")[0].strip()
        size = int(size_str, 16)
        if size == 0:
            break
        pos = end + 2
        result += data[pos:pos + size]
        pos += size + 2
    return result


def rebuild_response(headers: bytes, body: bytes, force_200: bool = False) -> bytes:
    lines = headers.decode("utf-8", errors="replace").rstrip("\r\n").split("\r\n")
    if force_200 and lines:
        parts = lines[0].split(" ", 2)
        if len(parts) >= 2:
            lines[0] = f"{parts[0]} 200 OK"
    out = [ln for ln in lines if not ln.lower().startswith(("content-length:", "transfer-encoding:"))]
    out.append(f"Content-Length: {len(body)}")
    if force_200 and not any(ln.lower().startswith("content-type:") for ln in out):
        out.insert(1, "Content-Type: application/json; charset=utf-8")
    return "\r\n".join(out).encode() + b"\r\n\r\n" + body


class NMSProxy:
    def __init__(self, expedition_path: str):
        with open(expedition_path, encoding="utf-8") as f:
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

    def handle(self, client_ssl: ssl.SSLSocket, hostname: str) -> None:
        """Handle a single client connection (blocking, runs in its own thread)."""
        real_ip = REAL_IPS[hostname]

        try:
            while True:
                req = read_http_sync(client_ssl)
                if not req:
                    return

                first_line = req.split(b"\r\n")[0].decode("utf-8", errors="replace")
                parts = first_line.split(" ", 2)
                path = parts[1] if len(parts) > 1 else "/"
                print(f"  {parts[0]} https://{hostname}{path}")

                # Connect to real upstream server
                up_ctx = ssl.create_default_context()
                up_sock = socket.create_connection((real_ip, 443), timeout=15)
                up_ssl = up_ctx.wrap_socket(up_sock, server_hostname=hostname)

                up_ssl.sendall(req)
                resp = read_http_sync(up_ssl)
                up_ssl.close()

                # Process response
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

                client_ssl.sendall(resp)

                # Check if client wants to close
                hdrs_lower = req.split(b"\r\n\r\n")[0].lower()
                if b"connection: close" in hdrs_lower:
                    return

        except (socket.timeout, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
        finally:
            try:
                client_ssl.close()
            except Exception:
                pass


_conn_semaphore = threading.Semaphore(MAX_CONNECTIONS)


def _accept_loop(proxy: NMSProxy, srv_sock: socket.socket, ctx: ssl.SSLContext,
                 stop_event: threading.Event) -> None:
    """Accept loop: each connection gets its own thread for blocking I/O."""
    while not stop_event.is_set():
        try:
            client_sock, addr = srv_sock.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        if not _conn_semaphore.acquire(blocking=False):
            print(f"  [WARN] Max connections ({MAX_CONNECTIONS}) reached, rejecting {addr}")
            client_sock.close()
            continue

        t = threading.Thread(target=_handle_client, args=(proxy, client_sock, addr, ctx),
                             daemon=True)
        t.start()


def _handle_client(proxy: NMSProxy, client_sock: socket.socket, addr: tuple, ctx: ssl.SSLContext) -> None:
    """TLS handshake + proxy, all blocking in a dedicated thread."""
    try:
        client_sock.settimeout(30)
        try:
            client_ssl = ctx.wrap_socket(client_sock, server_side=True)
        except ssl.SSLError as e:
            print(f"  [TLS ERROR] {e} (from {addr})")
            client_sock.close()
            return
        except Exception as e:
            print(f"  [CONN ERROR] {type(e).__name__}: {e} (from {addr})")
            client_sock.close()
            return

        hostname = _sni_map.pop(id(client_ssl), None)
        if not hostname or hostname not in REAL_IPS:
            if not hostname:
                print("  [WARN] Connection with no SNI hostname, closing")
            else:
                print(f"  [WARN] Unknown hostname '{hostname}', closing")
            client_ssl.close()
            return

        proxy.handle(client_ssl, hostname)
    finally:
        _conn_semaphore.release()


def verify_proxy(port: int = 443) -> list[str]:
    """Run diagnostics on the proxy. Returns a list of problems found."""
    problems = []

    from nms_expeditions_online.dns_resolve import NMS_HOSTNAMES
    for hostname in NMS_HOSTNAMES:
        try:
            results = socket.getaddrinfo(hostname, port, socket.AF_INET, socket.SOCK_STREAM)
            ips = {r[4][0] for r in results}
            if "127.0.0.1" not in ips:
                problems.append(
                    f"DNS: {hostname} resolves to {ips} instead of 127.0.0.1\n"
                    f"    The hosts file redirect is not working.\n"
                    f"    Try restarting the DNS Client service or rebooting."
                )
        except socket.gaierror as e:
            problems.append(f"DNS: Cannot resolve {hostname}: {e}")

    test_hostname = "merged-nms-static.nomanssky.com"

    # On Windows, validate against the OS cert store (same as SChannel/game).
    # On Linux, skip validation — the game runs via Proton which doesn't
    # validate against the system store.
    if platform.system() == "Windows":
        test_ctx = ssl.create_default_context()
    else:
        test_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        test_ctx.check_hostname = False
        test_ctx.verify_mode = ssl.CERT_NONE

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
            with test_ctx.wrap_socket(raw, server_hostname=test_hostname) as tls:
                # Handshake succeeded — send a valid request to avoid
                # server-side errors from a bare disconnect.
                tls.sendall(
                    f"GET /selftest HTTP/1.1\r\nHost: {test_hostname}\r\nConnection: close\r\n\r\n".encode()
                )
                try:
                    tls.recv(4096)
                except OSError:
                    pass  # upstream may reject; handshake already proved TLS works
    except ssl.SSLCertVerificationError as e:
        problems.append(f"CERT VALIDATION FAILED: {e}\n"
                        f"    The CA cert is not trusted by the OS cert store.\n"
                        f"    The game will reject connections for the same reason.")
    except ssl.SSLError as e:
        problems.append(f"TLS: Handshake failed: {e}")
    except OSError as e:
        problems.append(f"TLS: Connection to proxy failed: {e}")

    return problems


def start_proxy(
    expedition_path: str, port: int = 443,
) -> tuple[threading.Thread, threading.Event, http.server.HTTPServer | None]:
    """Start the proxy in a background thread. Returns (thread, stop_event, crl_server)."""
    global REAL_IPS

    print("Resolving NMS server IPs...")
    REAL_IPS = resolve_all()
    for hostname, ip in REAL_IPS.items():
        print(f"  {hostname} -> {ip}")

    init_ca()
    crl_server = _start_crl_server()
    proxy = NMSProxy(expedition_path)
    print(f"Loaded expedition: SeasonId={proxy.meta['SeasonId']}")

    cert_path, key_path = _make_server_cert()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_path, key_path)
    os.unlink(cert_path)
    os.unlink(key_path)
    ctx.sni_callback = _sni_hostname_callback

    srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv_sock.bind(("127.0.0.1", port))
    except OSError as e:
        if e.errno in (98, 10048) or "address already in use" in str(e).lower():
            print(f"\nERROR: Port {port} is already in use.")
            print("Close any web servers, VPNs, or other software using port 443 and try again.")
        else:
            print(f"\nERROR: {e}")
        raise
    srv_sock.listen(128)
    srv_sock.settimeout(1.0)

    stop_event = threading.Event()

    thread = threading.Thread(target=_accept_loop, args=(proxy, srv_sock, ctx, stop_event),
                              daemon=True)
    thread.start()
    return thread, stop_event, crl_server
