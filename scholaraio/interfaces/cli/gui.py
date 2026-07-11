"""Local read-only WebUI for browsing ScholarAIO libraries."""

from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
import secrets
import shutil
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, quote, unquote, urlparse

if TYPE_CHECKING:
    from scholaraio.core.config import Config

_MAX_JSON_BODY_BYTES = 64 * 1024
_NATIVE_PDF_OPEN_PATHS = frozenset({"/api/main/open-pdf", "/api/proceedings/open-pdf"})
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'"
)
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _ui(msg: str = "") -> None:
    try:
        from scholaraio.interfaces.cli import compat as cli_mod
    except ImportError:
        from scholaraio.core.log import ui as log_ui

        log_ui(msg)
        return
    cli_mod.ui(msg)


def _static_dir() -> Path:
    return Path(__file__).resolve().parent / "library-view"


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _pdf_content_disposition(filename: str, *, attachment: bool = False) -> str:
    safe_name = filename.replace("\\", "_").replace('"', "_").replace("\r", "_").replace("\n", "_").strip()
    if not safe_name:
        safe_name = "paper.pdf"
    try:
        fallback = safe_name.encode("ascii").decode("ascii")
    except UnicodeEncodeError:
        fallback = "paper.pdf"
    fallback = (
        fallback.replace("\\", "_").replace('"', "_").replace("\r", "_").replace("\n", "_").strip() or "paper.pdf"
    )
    encoded = quote(safe_name, safe="")
    disposition = "attachment" if attachment else "inline"
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def _browser_url(host: str, port: int) -> str:
    browser_host = (host or "127.0.0.1").strip() or "127.0.0.1"
    if browser_host in {"0.0.0.0", "::", "[::]"}:
        browser_host = "127.0.0.1"
    elif ":" in browser_host and not browser_host.startswith("["):
        browser_host = f"[{browser_host}]"
    return f"http://{browser_host}:{port}"


def _is_loopback_host(host: str) -> bool:
    candidate = str(host or "").strip().strip("[]")
    if candidate.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


class LibraryViewRequestHandler(BaseHTTPRequestHandler):
    """Request handler configured by :func:`create_library_view_server`."""

    cfg: Config
    static_dir: Path
    csrf_token: str
    native_pdf_open_enabled: bool
    native_pdf_open_reason: str
    pdf_delivery: dict[str, str]

    server_version = "ScholarAIOLibraryGUI/2.0"

    def log_message(self, _format: str, *_args) -> None:
        return

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        """Keep protocol/parser failures on the same secure JSON surface."""
        del explain
        try:
            status = HTTPStatus(code)
        except ValueError:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
        self._send_error_json(status, message or status.phrase, code="http_error")

    def _send_security_headers(self, *, allow_same_origin_frame: bool = False) -> None:
        frame_ancestors = "'self'" if allow_same_origin_frame else "'none'"
        self.send_header(
            "Content-Security-Policy",
            f"{_CONTENT_SECURITY_POLICY}; frame-ancestors {frame_ancestors}",
        )
        self.send_header("X-Frame-Options", "SAMEORIGIN" if allow_same_origin_frame else "DENY")
        for name, value in _SECURITY_HEADERS.items():
            self.send_header(name, value)

    def _send_bytes(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._send_security_headers()
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, payload: object, *, headers: dict[str, str] | None = None) -> None:
        self._send_bytes(status, _json_bytes(payload), "application/json; charset=utf-8", headers=headers)

    def _send_error_json(
        self,
        status: HTTPStatus,
        message: str,
        *,
        code: str = "request_failed",
        headers: dict[str, str] | None = None,
    ) -> None:
        self._send_json(
            status,
            {"error": message, "code": code, "status": status.value},
            headers=headers,
        )

    def _query_value(self, name: str) -> str:
        parsed = urlparse(self.path)
        values = parse_qs(parsed.query).get(name) or [""]
        return values[0]

    def _query_id(self) -> str:
        return self._query_value("id")

    def _required_query_id(self) -> str | None:
        paper_id = self._query_id()
        if paper_id:
            return paper_id
        self._send_error_json(
            HTTPStatus.BAD_REQUEST,
            "missing id query parameter",
            code="missing_paper_id",
        )
        return None

    def _origin_is_same_loopback_server(self) -> bool:
        origin = str(self.headers.get("Origin") or "").strip()
        if not origin:
            return False
        try:
            parsed = urlparse(origin)
            port = parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme == "http"
            and bool(parsed.hostname)
            and _is_loopback_host(parsed.hostname or "")
            and port == getattr(self.server, "server_port", None)
        )

    def _read_json_object(self) -> dict | None:
        content_type = str(self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._send_error_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "Content-Type must be application/json",
                code="unsupported_media_type",
            )
            return None
        try:
            content_length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Invalid Content-Length",
                code="invalid_content_length",
            )
            return None
        if content_length <= 0:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "A JSON request body is required",
                code="invalid_request_body",
            )
            return None
        if content_length > _MAX_JSON_BODY_BYTES:
            self.close_connection = True
            self._send_error_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "JSON request body is too large",
                code="request_too_large",
                headers={"Connection": "close"},
            )
            return None
        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Request body must be valid UTF-8 JSON",
                code="invalid_json",
            )
            return None
        if not isinstance(payload, dict):
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Request body must be a JSON object",
                code="invalid_request_body",
            )
            return None
        return payload

    def _send_pdf(self, pdf_path: Path, *, attachment: bool = False) -> None:
        try:
            size = pdf_path.stat().st_size
            stream = pdf_path.open("rb")
        except FileNotFoundError:
            self._send_error_json(HTTPStatus.NOT_FOUND, "PDF file not found")
            return
        except OSError as exc:
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Disposition",
            _pdf_content_disposition(pdf_path.name, attachment=attachment),
        )
        self._send_security_headers(allow_same_origin_frame=True)
        self.end_headers()
        if self.command == "HEAD":
            stream.close()
            return
        with stream:
            try:
                shutil.copyfileobj(stream, self.wfile, length=1024 * 1024)
            except OSError:
                return

    def _handle_api(self, path: str) -> None:
        from scholaraio.services.library_search import (
            DEFAULT_LIBRARY_SEARCH_RESULTS,
            LibrarySearchFilters,
            LibrarySearchRequestError,
            search_main_library,
        )
        from scholaraio.services.library_view import (
            build_main_library_view,
            build_proceedings_library_view,
            get_main_paper_bibtex,
            get_main_paper_detail,
            get_main_paper_pdf,
            get_proceedings_paper_bibtex,
            get_proceedings_paper_detail,
            get_proceedings_paper_pdf,
        )

        try:
            if path == "/api/health":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "readonly": True,
                        "native_pdf_open": self.native_pdf_open_enabled,
                    },
                )
                return
            if path == "/api/capabilities":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "csrf_token": self.csrf_token,
                        "native_pdf_open": {
                            "enabled": self.native_pdf_open_enabled,
                            "reason": self.native_pdf_open_reason,
                        },
                        "pdf_delivery": self.pdf_delivery,
                        "search_modes": {
                            "main": ["metadata", "keyword", "semantic", "unified"],
                            "proceedings": ["metadata"],
                        },
                    },
                )
                return
            if path == "/api/main/papers":
                self._send_json(HTTPStatus.OK, build_main_library_view(self.cfg))
                return
            if path == "/api/main/search":
                try:
                    raw_limit = self._query_value("limit")
                    limit = int(raw_limit) if raw_limit else DEFAULT_LIBRARY_SEARCH_RESULTS
                except ValueError:
                    raise LibrarySearchRequestError(
                        "Search limit must be a positive integer",
                        code="invalid_search_limit",
                    )
                filters = LibrarySearchFilters.from_strings(
                    title=self._query_value("title"),
                    author=self._query_value("author"),
                    year_from=self._query_value("year_from"),
                    year_to=self._query_value("year_to"),
                    journal=self._query_value("journal"),
                    paper_type=self._query_value("paper_type"),
                    doi=self._query_value("doi"),
                )
                payload = search_main_library(
                    self.cfg,
                    query=self._query_value("q"),
                    mode=self._query_value("mode"),
                    filters=filters,
                    limit=limit,
                )
                self._send_json(HTTPStatus.OK, payload)
                return
            if path == "/api/main/detail":
                paper_id = self._required_query_id()
                if paper_id is None:
                    return
                self._send_json(HTTPStatus.OK, get_main_paper_detail(self.cfg, paper_id))
                return
            if path == "/api/main/bibtex":
                paper_id = self._required_query_id()
                if paper_id is None:
                    return
                self._send_json(
                    HTTPStatus.OK,
                    {"paper_id": paper_id, "bibtex": get_main_paper_bibtex(self.cfg, paper_id)},
                )
                return
            if path == "/api/main/pdf":
                paper_id = self._required_query_id()
                if paper_id is None:
                    return
                self._send_pdf(
                    get_main_paper_pdf(self.cfg, paper_id),
                    attachment=self._query_value("download") == "1",
                )
                return
            if path == "/api/proceedings/papers":
                self._send_json(HTTPStatus.OK, build_proceedings_library_view(self.cfg))
                return
            if path == "/api/proceedings/detail":
                paper_id = self._required_query_id()
                if paper_id is None:
                    return
                self._send_json(HTTPStatus.OK, get_proceedings_paper_detail(self.cfg, paper_id))
                return
            if path == "/api/proceedings/bibtex":
                paper_id = self._required_query_id()
                if paper_id is None:
                    return
                self._send_json(
                    HTTPStatus.OK,
                    {"paper_id": paper_id, "bibtex": get_proceedings_paper_bibtex(self.cfg, paper_id)},
                )
                return
            if path == "/api/proceedings/pdf":
                paper_id = self._required_query_id()
                if paper_id is None:
                    return
                self._send_pdf(
                    get_proceedings_paper_pdf(self.cfg, paper_id),
                    attachment=self._query_value("download") == "1",
                )
                return
        except LibrarySearchRequestError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc), code=exc.code)
            return
        except KeyError as exc:
            self._send_error_json(
                HTTPStatus.NOT_FOUND,
                f"paper not found: {exc.args[0]}",
                code="paper_not_found",
            )
            return
        except Exception as exc:
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc), code="internal_error")
            return
        self._send_error_json(HTTPStatus.NOT_FOUND, "unknown API route", code="unknown_route")

    def _serve_static(self, path: str) -> None:
        if path == "/":
            rel = "index.html"
        else:
            rel = unquote(path.lstrip("/"))
        candidate = (self.static_dir / rel).resolve()
        root = self.static_dir.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            self._send_error_json(HTTPStatus.FORBIDDEN, "forbidden path")
            return
        if not candidate.is_file():
            self._send_error_json(HTTPStatus.NOT_FOUND, "file not found")
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif candidate.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif candidate.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        self._send_bytes(HTTPStatus.OK, candidate.read_bytes(), content_type)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in _NATIVE_PDF_OPEN_PATHS:
            self._reject_write(allowed="POST")
            return
        if path.startswith("/api/"):
            self._handle_api(path)
            return
        self._serve_static(path)

    def do_HEAD(self) -> None:
        self.do_GET()

    def _reject_write(self, *, allowed: str | None = None) -> None:
        path = urlparse(getattr(self, "path", "")).path
        allowed = allowed or ("POST" if path in _NATIVE_PDF_OPEN_PATHS else "GET, HEAD")
        self.close_connection = True
        self._send_error_json(
            HTTPStatus.METHOD_NOT_ALLOWED,
            "this library WebUI is read-only for library data and does not allow that method on this route",
            headers={"Allow": allowed, "Connection": "close"},
        )

    def _handle_native_pdf_open(self, source: str) -> None:
        from scholaraio.services.library_view import (
            LibraryPaperNotFoundError,
            LibraryPdfNotFoundError,
            get_main_paper_pdf,
            get_proceedings_paper_pdf,
        )
        from scholaraio.services.system_open import (
            DefaultApplicationOpenError,
            open_with_default_application,
        )

        if not self.native_pdf_open_enabled:
            self._send_error_json(
                HTTPStatus.FORBIDDEN,
                self.native_pdf_open_reason or "Native PDF launch is unavailable",
                code="native_open_disabled",
            )
            return
        if not self._origin_is_same_loopback_server():
            self._send_error_json(
                HTTPStatus.FORBIDDEN,
                "Request Origin must match this loopback GUI server",
                code="origin_rejected",
            )
            return
        supplied_token = str(self.headers.get("X-ScholarAIO-CSRF") or "")
        if not supplied_token or not secrets.compare_digest(supplied_token, self.csrf_token):
            self._send_error_json(
                HTTPStatus.FORBIDDEN,
                "CSRF token is missing or invalid",
                code="csrf_rejected",
            )
            return
        payload = self._read_json_object()
        if payload is None:
            return
        paper_id = payload.get("id")
        if set(payload) != {"id"} or not isinstance(paper_id, str) or not paper_id.strip():
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Request body must contain only a non-empty string `id`",
                code="invalid_request_body",
            )
            return

        try:
            if source == "main":
                pdf_path = get_main_paper_pdf(self.cfg, paper_id)
            else:
                pdf_path = get_proceedings_paper_pdf(self.cfg, paper_id)
            open_with_default_application(pdf_path.resolve())
        except LibraryPaperNotFoundError:
            self._send_error_json(
                HTTPStatus.NOT_FOUND,
                f"paper not found: {paper_id}",
                code="paper_not_found",
            )
            return
        except LibraryPdfNotFoundError:
            self._send_error_json(
                HTTPStatus.NOT_FOUND,
                f"PDF not found for paper: {paper_id}",
                code="pdf_not_found",
            )
            return
        except DefaultApplicationOpenError as exc:
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                str(exc),
                code="native_open_failed",
            )
            return
        self._send_json(HTTPStatus.OK, {"status": "opened", "paper_id": paper_id})

    def do_POST(self) -> None:
        path = urlparse(getattr(self, "path", "")).path
        if path == "/api/main/open-pdf":
            self._handle_native_pdf_open("main")
            return
        if path == "/api/proceedings/open-pdf":
            self._handle_native_pdf_open("proceedings")
            return
        self._reject_write()

    def do_PUT(self) -> None:
        self._reject_write()

    def do_PATCH(self) -> None:
        self._reject_write()

    def do_DELETE(self) -> None:
        self._reject_write()

    def do_OPTIONS(self) -> None:
        self._reject_write()

    def do_TRACE(self) -> None:
        self._reject_write()

    def do_CONNECT(self) -> None:
        self._reject_write()


def create_library_view_server(cfg: Config, *, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Create the local, library-read-only HTTP server."""

    from scholaraio.services.system_open import default_application_open_capability

    static_dir = _static_dir()

    class ConfiguredHandler(LibraryViewRequestHandler):
        pass

    ConfiguredHandler.cfg = cfg
    ConfiguredHandler.static_dir = static_dir
    ConfiguredHandler.csrf_token = secrets.token_urlsafe(32)
    host_is_loopback = _is_loopback_host(host)
    host_capability = default_application_open_capability()
    ConfiguredHandler.native_pdf_open_enabled = host_is_loopback and host_capability.enabled
    if not host_is_loopback:
        reason = "Native PDF launch is available only when the GUI binds to a loopback host."
    elif not host_capability.enabled:
        reason = host_capability.reason
    else:
        reason = ""
    ConfiguredHandler.native_pdf_open_reason = reason
    if ConfiguredHandler.native_pdf_open_enabled:
        ConfiguredHandler.pdf_delivery = {
            "mode": "native",
            "target": host_capability.target or "host",
            "label": "Open in default viewer",
            "reason": "",
        }
    else:
        ConfiguredHandler.pdf_delivery = {
            "mode": "download",
            "target": "client",
            "label": "Download PDF",
            "reason": reason,
        }
    return ThreadingHTTPServer((host, int(port)), ConfiguredHandler)


def serve_library_view(
    cfg: Config,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Run the local read-only WebUI until interrupted."""

    server = create_library_view_server(cfg, host=host, port=port)
    url = _browser_url(host, server.server_port)
    if open_browser:
        threading.Timer(0.2, lambda: webbrowser.open(url)).start()
    _ui(f"ScholarAIO library WebUI (read-only): {url}")
    _ui("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _ui("Stopping ScholarAIO library WebUI.")
    finally:
        server.server_close()


def cmd_gui(args: argparse.Namespace, cfg: Config) -> None:
    """CLI command handler for the read-only library WebUI."""

    serve_library_view(
        cfg,
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
    )
