# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""GET/HEAD-only HTTP layer of the read-only viewer.

The handler defines ``do_GET`` and ``do_HEAD`` and nothing else. The standard
library answers every other method - POST, PUT, PATCH, DELETE, OPTIONS, TRACE,
CONNECT - with ``501 Unsupported method`` before any code here runs, so no
request body is ever read and no route can be reached by a mutating verb.

Every route is listed in ``ROUTES`` and maps to one read method of
``ReadOnlyAdapter``. Repository content is returned as JSON strings for the
page to render as text; no repository file is served with its own content type,
so a committed HTML or SVG file cannot execute in the viewer's origin.
"""

from __future__ import annotations

import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from .adapter import ReadOnlyAdapter, json_safe
from .repo_fs import AccessDenied, NotFound, TooLarge

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}
_ID = r"(?P<id>[A-Za-z0-9][A-Za-z0-9._\-]{0,199})"

#: (pattern, adapter method, takes) - the complete route table. All are GET/HEAD.
ROUTES: tuple[tuple[re.Pattern, str, str], ...] = tuple(
    (re.compile(f"^{pattern}$"), method, takes) for pattern, method, takes in (
        ("/api/overview", "overview", ""),
        ("/api/capabilities", "capabilities", ""),
        ("/api/checkout", "checkout", ""),
        ("/api/records", "records", ""),
        (f"/api/records/{_ID}", "record", "id"),
        (f"/api/records/{_ID}/verify", "verify_record", "id"),
        ("/api/experiments", "experiments", ""),
        (f"/api/experiments/{_ID}", "experiment", "id"),
        ("/api/candidates", "candidates", ""),
        ("/api/gates", "gates", ""),
        ("/api/provenance", "provenance", ""),
        ("/api/approvals", "approvals", ""),
        ("/api/audit", "audit", ""),
        ("/api/corrections", "corrections", ""),
        ("/api/classification", "classification", ""),
        ("/api/documents", "documents", ""),
        ("/api/file", "file", "path"),
        ("/api/search", "search", "q"),
    ))

SECURITY_HEADERS = {
    "Content-Security-Policy": ("default-src 'none'; script-src 'self'; style-src 'self'; "
                                "img-src 'self' data:; connect-src 'self'; form-action 'none'; "
                                "frame-ancestors 'none'; base-uri 'none'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Allow": "GET, HEAD",
}


class ReadOnlyHandler(BaseHTTPRequestHandler):
    """Answers GET and HEAD. Every other method is rejected by the base class."""

    server_version = "QMHP-CEM-ReadOnlyViewer/0.1"
    sys_version = ""
    adapter: ReadOnlyAdapter  # set by make_server

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        self._respond(body=True)

    def do_HEAD(self) -> None:  # noqa: N802 - http.server naming
        self._respond(body=False)

    # ------------------------------------------------------------------
    def _respond(self, body: bool) -> None:
        split = urlsplit(self.path)
        path = unquote(split.path)
        query = parse_qs(split.query, keep_blank_values=True)
        try:
            if path.startswith("/api/"):
                status, payload = self._api(path, query)
                data = json.dumps(json_safe(payload), ensure_ascii=False, allow_nan=False).encode("utf-8")
                self._send(status, "application/json; charset=utf-8", data, body, cache=False)
            else:
                status, ctype, data = self._static(path)
                self._send(status, ctype, data, body, cache=False)
        except Exception as exc:  # noqa: BLE001 - never leak a traceback, never half-write
            data = json.dumps({"error": "internal error", "type": exc.__class__.__name__}).encode()
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, "application/json", data, body, cache=False)

    def _api(self, path: str, query: dict) -> tuple[int, object]:
        for pattern, method, takes in ROUTES:
            m = pattern.match(path)
            if not m:
                continue
            fn = getattr(self.adapter, method)
            try:
                if takes == "id":
                    return HTTPStatus.OK, fn(m.group("id"))
                if takes == "path":
                    return HTTPStatus.OK, fn((query.get("path") or [""])[0])
                if takes == "q":
                    return HTTPStatus.OK, fn((query.get("q") or [""])[0])
                return HTTPStatus.OK, fn()
            except NotFound as exc:
                return HTTPStatus.NOT_FOUND, {"error": "not found", "detail": str(exc)}
            except AccessDenied as exc:
                return HTTPStatus.FORBIDDEN, {"error": "refused", "detail": str(exc)}
            except TooLarge as exc:
                return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too large", "detail": str(exc)}
        return HTTPStatus.NOT_FOUND, {"error": "no such read-only endpoint",
                                      "note": "This viewer has no execution, approval or write endpoints."}

    @staticmethod
    def _static(path: str) -> tuple[int, str, bytes]:
        if path in ("", "/"):
            name = "index.html"
        elif path.startswith("/static/"):
            name = path[len("/static/"):]
        else:
            return HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found"
        if not re.fullmatch(r"[a-z0-9_\-]+\.(html|js|css|svg)", name):
            return HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found"
        full = os.path.join(STATIC_DIR, name)
        if not os.path.isfile(full):
            return HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found"
        with open(full, "rb") as fh:
            data = fh.read()
        return HTTPStatus.OK, STATIC_TYPES[os.path.splitext(name)[1]], data

    def _send(self, status: int, ctype: str, data: bytes, body: bool, cache: bool) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store" if not cache else "max-age=60")
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(data)  # the HTTP response socket, not a file

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - base-class signature
        if not getattr(self.server, "quiet", False):
            super().log_message(format, *args)


def make_server(repo_root: str, host: str = "127.0.0.1", port: int = 8765,
                quiet: bool = False) -> ThreadingHTTPServer:
    adapter = ReadOnlyAdapter(repo_root)
    handler = type("BoundReadOnlyHandler", (ReadOnlyHandler,), {"adapter": adapter})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    server.quiet = quiet
    return server
