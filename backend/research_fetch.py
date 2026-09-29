"""Explicit public HTTPS fetch, pinned DNS/TLS, no browser/session/proxy access."""

import http.client
from html.parser import HTMLParser
import ipaddress
import queue
import re
import socket
import ssl
import threading
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

MAX_BYTES = 256 * 1024
FETCH_TIMEOUT = 10
FETCH_SLOTS = threading.BoundedSemaphore(2)
DNS_SLOTS = threading.BoundedSemaphore(2)
BLOCKED_V6 = tuple(
    ipaddress.ip_network(n)
    for n in ("64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "2001::/32")
)


def public_address(value):
    ip = ipaddress.ip_address(value)
    return (
        ip.is_global
        and not ip.is_multicast
        and not ip.is_reserved
        and not (ip.version == 6 and any(ip in net for net in BLOCKED_V6))
    )


def canonical_url(value):
    if not value:
        return ""
    if (
        len(value) > 2000
        or any(ord(c) < 33 or ord(c) == 127 for c in value)
        or "\\" in value
    ):
        raise ValueError(
            "URL harus HTTPS publik tanpa spasi, kredensial, atau karakter kontrol."
        )
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
        if (
            parts.scheme != "https"
            or parts.username is not None
            or parts.password is not None
            or parts.port not in (None, 443)
        ):
            raise ValueError
        if (
            not host
            or len(host) > 253
            or "%" in host
            or host.endswith(
                (
                    ".local",
                    ".localhost",
                    ".internal",
                    ".lan",
                    ".home",
                    ".onion",
                    ".test",
                    ".invalid",
                )
            )
        ):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if (
                "." not in host
                or re.fullmatch(r"[0-9.]+", host)
                or not re.fullmatch(r"[a-z0-9.-]+", host)
                or any(
                    not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                    for label in host.split(".")
                )
            ):
                raise ValueError
        else:
            if not public_address(str(address)):
                raise ValueError
        netloc = f"[{host}]" if ":" in host else host
        result = urlunsplit(
            (
                "https",
                netloc,
                quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~"),
                quote(parts.query, safe="%=&?/:@!$'()*+,;~-._"),
                "",
            )
        )
        if len(result) > 2000 or re.search(r"%(?![0-9a-fA-F]{2})", result):
            raise ValueError
        return result
    except (ValueError, UnicodeError):
        raise ValueError(
            "Gunakan URL HTTPS publik port 443; alamat lokal/privat dan URL berkredensial ditolak."
        )


def resolve_public(host, timeout):
    if not DNS_SLOTS.acquire(blocking=False):
        raise ValueError(
            "Pemeriksaan DNS masih sibuk. Coba lagi nanti atau gunakan catatan manual."
        )
    result = queue.Queue(maxsize=1)

    def resolve():
        try:
            result.put(socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
        except OSError as error:
            result.put(error)
        finally:
            DNS_SLOTS.release()

    # A stalled system resolver cannot block application shutdown or spawn unbounded workers.
    threading.Thread(target=resolve, daemon=True).start()
    try:
        addresses = result.get(timeout=timeout)
    except queue.Empty:
        raise ValueError(
            "DNS melewati batas waktu. Catatan manual tetap tersedia offline."
        )
    if isinstance(addresses, Exception):
        raise ValueError(
            "Alamat sumber tidak dapat ditemukan. Periksa jaringan atau gunakan catatan manual."
        )
    ips = list(dict.fromkeys(item[4][0] for item in addresses))
    if not ips or any(not public_address(ip) for ip in ips):
        raise ValueError(
            "DNS sumber mengarah ke jaringan privat/lokal atau alamat yang tidak diizinkan."
        )
    return ips


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocked = []
        self.title = []
        self.in_title = False
        self.pieces = []
        self.published = ""

    def handle_starttag(self, tag, attributes):
        if tag in {
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "form",
            "noscript",
            "iframe",
            "svg",
            "template",
        }:
            self.blocked.append(tag)
        if self.blocked:
            return
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            attrs = dict(attributes)
            if attrs.get("property") == "article:published_time":
                self.published = (attrs.get("content") or "")[:10]

    def handle_endtag(self, tag):
        if tag in self.blocked:
            self.blocked = self.blocked[: self.blocked.index(tag)]
        if tag == "title":
            self.in_title = False

    def handle_data(self, value):
        if not self.blocked:
            (self.title if self.in_title else self.pieces).append(value)


def extract(body, content_type):
    charset_match = re.search(r"charset=[\"']?([\w-]+)", content_type, re.I)
    charset = charset_match.group(1).lower() if charset_match else "utf-8"
    if charset not in {"utf-8", "utf8", "iso-8859-1", "windows-1252", "us-ascii"}:
        raise ValueError("Encoding halaman belum didukung. Gunakan catatan manual.")
    text = body.decode(charset, errors="replace")
    if content_type.lower().startswith("text/html"):
        parser = PageText()
        parser.feed(text)
        return {
            "title": " ".join(" ".join(parser.title).split())[:160],
            "text": " ".join(" ".join(parser.pieces).split())[:1200],
            "published_on": parser.published,
        }
    return {"title": "", "text": " ".join(text.split())[:1200], "published_on": ""}


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Keep TLS hostname verification and interrupt even slow header/TLS reads."""

    def __init__(self, host, address, deadline):
        super().__init__(
            host,
            timeout=max(0.01, deadline - time.monotonic()),
            context=ssl.create_default_context(),
        )
        self.address = address
        self.deadline = deadline
        self.deadline_timer = None
        self.deadline_socket = None

    def connect(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        raw = socket.create_connection((self.address, 443), remaining)
        try:
            # Separate the handshake so the watchdog also covers a stalled TLS peer.
            self.sock = self._context.wrap_socket(
                raw,
                server_hostname=self.host,
                do_handshake_on_connect=False,
            )
        except Exception:
            raw.close()
            raise
        self.deadline_socket = self.sock
        self.deadline_timer = threading.Timer(
            max(0, self.deadline - time.monotonic()),
            self.expire,
        )
        self.deadline_timer.daemon = True
        self.deadline_timer.start()
        self.sock.do_handshake()

    def expire(self):
        # HTTPResponse may own the socket after Connection: close. Retain it until
        # the response has been consumed so its makefile cannot outlive the deadline.
        if self.deadline_socket:
            try:
                self.deadline_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.deadline_socket.close()

    def finish(self):
        if self.deadline_timer:
            self.deadline_timer.cancel()
        self.close()
        if self.deadline_socket:
            self.deadline_socket.close()


def fetch_public(url):
    current = canonical_url(url)
    if not current:
        raise ValueError("Isi URL sebelum mengambil halaman.")
    if not FETCH_SLOTS.acquire(blocking=False):
        raise ValueError("Dua pengambilan sumber sedang berjalan. Coba lagi sebentar.")
    deadline = time.monotonic() + FETCH_TIMEOUT
    try:
        for redirect in range(4):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            parts = urlsplit(current)
            addresses = resolve_public(parts.hostname, min(3, remaining))
            connection = PinnedHTTPSConnection(parts.hostname, addresses[0], deadline)
            response = None
            try:
                connection.request(
                    "GET",
                    urlunsplit(("", "", parts.path, parts.query, "")),
                    headers={
                        "User-Agent": "JDHShortsStudio/0.2.11 (explicit reference fetch)",
                        "Accept": "text/html,text/plain",
                        "Accept-Encoding": "identity",
                    },
                )
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    target = response.getheader("Location")
                    if not target or redirect == 3:
                        raise ValueError(
                            "Redirect sumber terlalu banyak atau tidak valid."
                        )
                    current = canonical_url(urljoin(current, target))
                    continue
                if response.status != 200:
                    raise ValueError(
                        f"Sumber mengembalikan HTTP {response.status}. Tidak ada isi yang disimpan; gunakan catatan manual."
                    )
                content_type = response.getheader("Content-Type", "")
                if content_type.split(";")[0].strip().lower() not in {
                    "text/html",
                    "text/plain",
                }:
                    raise ValueError(
                        "Hanya halaman HTML/teks didukung; PDF, media, dan file tidak diambil."
                    )
                if response.getheader("Content-Encoding", "identity").lower() not in {
                    "",
                    "identity",
                }:
                    raise ValueError(
                        "Halaman mengabaikan permintaan teks tanpa kompresi. Gunakan catatan manual."
                    )
                size = response.getheader("Content-Length")
                if size and (not size.isdigit() or int(size) > MAX_BYTES):
                    raise ValueError(
                        "Halaman melebihi batas 256 KB atau ukuran tidak valid."
                    )
                chunks, total = [], 0
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    if connection.sock:
                        connection.sock.settimeout(remaining)
                    chunk = response.read1(min(16384, MAX_BYTES + 1 - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError("Halaman melebihi batas 256 KB.")
                    chunks.append(chunk)
                result = extract(b"".join(chunks), content_type)
                if time.monotonic() >= deadline:
                    raise TimeoutError
                if len(result["text"]) < 20:
                    raise ValueError(
                        "Teks sumber tidak cukup terbaca (mungkin halaman dinamis/login). Tempel ringkasan manual; akses tidak diterobos."
                    )
                return {
                    **result,
                    "url": current,
                    "notice": "Cuplikan awal halaman, belum ringkasan terverifikasi. Periksa judul, tanggal, dan isi sebelum menyimpan. Script, cookie dan sesi browser tidak digunakan.",
                }
            finally:
                if response:
                    response.close()
                connection.finish()
        raise ValueError("Pengambilan tidak selesai.")
    except (OSError, http.client.HTTPException, TimeoutError):
        raise ValueError(
            "Sumber tidak dapat diambil dalam batas waktu/jaringan/TLS. Tidak ada fakta yang dibuat; gunakan catatan manual offline."
        )
    finally:
        FETCH_SLOTS.release()
