"""DevOpsPilot Web Management Dashboard Server.

Provides a zero-external-dependency management console powered by
Python's standard library `http.server.ThreadingHTTPServer`.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger("devopspilot.web")


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the DevOpsPilot Management Console."""

    server: DashboardServer  # type hint for parent server reference

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard stderr request spam unless DEBUG is enabled."""
        if os.environ.get("DEVOPSPILOT_WEB_DEBUG") == "1":
            super().log_message(format, *args)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query_params = parse_qs(parsed.query)

        # Dispatch API requests
        if path.startswith("/api/"):
            self._handle_api_get(path, query_params)
            return

        # Serve Dashboard Single Page App
        if path in {"/", "/index.html"}:
            self._serve_dashboard_html()
            return

        # Fallback 404
        self._send_json_response(
            {"error": "Not Found", "path": path}, status=HTTPStatus.NOT_FOUND
        )

    def do_POST(self) -> None:
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin and urlparse(origin).netloc != host:
            self._send_json_response(
                {"error": "Cross-origin writes are forbidden"},
                status=HTTPStatus.FORBIDDEN,
            )
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query_params = parse_qs(parsed.query)

        # Read JSON body if present
        body: dict[str, Any] = {}
        content_length = self.headers.get("Content-Length")
        if content_length:
            try:
                length = int(content_length)
                if length < 0 or length > 65536:
                    raise ValueError("Payload exceeds 64 KB")
                raw_bytes = self.rfile.read(length)
                if raw_bytes:
                    body = json.loads(raw_bytes.decode("utf-8"))
                    if not isinstance(body, dict):
                        raise ValueError("Expected a JSON object")
            except Exception as exc:
                self._send_json_response(
                    {"error": f"Invalid JSON payload: {exc}"},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

        if path.startswith("/api/"):
            self._handle_api_post(path, body, query_params)
            return

        self._send_json_response(
            {"error": "Not Found", "path": path}, status=HTTPStatus.NOT_FOUND
        )

    def _send_cors_headers(self) -> None:
        self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json_response(self, data: Any, status: int = HTTPStatus.OK) -> None:
        from devopspilot.web.console import sanitize

        payload = json.dumps(sanitize(data), ensure_ascii=False, default=str).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _serve_dashboard_html(self) -> None:
        html = self.server.get_dashboard_html()
        payload = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _handle_api_get(self, path: str, query: Mapping[str, list[str]]) -> None:
        api_router = self.server.api_router
        handler = api_router.get_routes.get(path)
        if handler:
            try:
                result = handler(query)
                self._send_json_response(result)
            except Exception as exc:
                logger.exception("API error handling %s", path)
                self._send_json_response(
                    {"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR
                )
            return

        # Dynamic routes like /api/deliveries/<id>
        if path.startswith("/api/deliveries/"):
            delivery_id = path[len("/api/deliveries/") :]
            handler = api_router.get_routes.get("/api/deliveries/{id}")
            if handler:
                try:
                    result = handler(delivery_id, query)
                    if result is None:
                        self._send_json_response(
                            {"error": "Delivery not found"}, status=HTTPStatus.NOT_FOUND
                        )
                    else:
                        self._send_json_response(result)
                except Exception as exc:
                    self._send_json_response(
                        {"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR
                    )
                return

        # Dynamic routes like /api/trajectories/<id>
        if path.startswith("/api/trajectories/"):
            traj_id = path[len("/api/trajectories/") :]
            handler = api_router.get_routes.get("/api/trajectories/{id}")
            if handler:
                try:
                    result = handler(traj_id, query)
                    if result is None:
                        self._send_json_response(
                            {"error": "Trajectory not found"},
                            status=HTTPStatus.NOT_FOUND,
                        )
                    else:
                        self._send_json_response(result)
                except Exception as exc:
                    self._send_json_response(
                        {"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR
                    )
                return

        self._send_json_response(
            {"error": f"API route '{path}' not found"}, status=HTTPStatus.NOT_FOUND
        )

    def _handle_api_post(
        self, path: str, body: dict[str, Any], query: Mapping[str, list[str]]
    ) -> None:
        api_router = self.server.api_router
        handler = api_router.post_routes.get(path)
        if handler:
            try:
                result = handler(body, query)
                self._send_json_response(result)
            except ValueError as exc:
                self._send_json_response(
                    {"error": str(exc)}, status=HTTPStatus.BAD_REQUEST
                )
            except Exception as exc:
                logger.exception("API error handling POST %s", path)
                self._send_json_response(
                    {"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR
                )
            return

        self._send_json_response(
            {"error": f"API route '{path}' not found"}, status=HTTPStatus.NOT_FOUND
        )


class DashboardApiRouter:
    """Registry for REST API endpoints."""

    def __init__(self) -> None:
        self.get_routes: dict[str, Callable[..., Any]] = {}
        self.post_routes: dict[str, Callable[..., Any]] = {}

    def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.get_routes[path] = func
            return func

        return decorator

    def post(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.post_routes[path] = func
            return func

        return decorator


class DashboardServer(ThreadingHTTPServer):
    """Custom ThreadingHTTPServer bound to DevOpsPilot dashboard logic."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        db_path: Path | None = None,
        html_provider: Callable[[], str] | None = None,
    ) -> None:
        super().__init__(server_address, DashboardRequestHandler)
        self.db_path = db_path
        self._html_provider = html_provider
        self.api_router = DashboardApiRouter()
        self._thread: threading.Thread | None = None
        self.console_service = None

    def get_dashboard_html(self) -> str:
        if self._html_provider:
            return self._html_provider()
        return "<html><body><h1>DevOpsPilot Dashboard</h1></body></html>"

    def start_background(self) -> None:
        """Start listening in a background daemon thread."""
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Shutdown and close the server socket."""
        if self.console_service:
            self.console_service.close()
        if self._thread:
            self.shutdown()
        self.server_close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


def create_dashboard_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    db_path: Path | None = None,
    html_provider: Callable[[], str] | None = None,
) -> DashboardServer:
    """Factory creating and configuring the DashboardServer instance."""
    server = DashboardServer((host, port), db_path=db_path, html_provider=html_provider)
    return server


def run_dashboard(
    host: str = "127.0.0.1",
    port: int = 8080,
    db_path: Path | None = None,
) -> None:
    """Run the dashboard server in foreground until interrupted."""
    from devopspilot.web.api import register_dashboard_apis
    from devopspilot.web.ui import get_dashboard_ui_html

    from devopspilot.cli.main import load_dotenv_if_present

    load_dotenv_if_present()
    configured_db = db_path or Path(
        os.getenv("DEVOPSPILOT_DB_PATH", ".devopspilot/state.db")
    )
    server = create_dashboard_server(
        host=host,
        port=port,
        db_path=configured_db,
        html_provider=get_dashboard_ui_html,
    )
    server.console_service = register_dashboard_apis(
        server.api_router, db_path=configured_db
    )
    server.console_service.start()

    actual_host, actual_port = server.server_address
    url = f"http://{actual_host}:{actual_port}"
    print("\n=======================================================")
    print("  DevOpsPilot Management Dashboard")
    print(f"  Server listening at: {url}")
    print("  Press Ctrl+C to stop.")
    print("=======================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
    finally:
        server.stop()
