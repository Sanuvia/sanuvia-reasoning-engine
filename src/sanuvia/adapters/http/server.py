"""HTTP server for the review harness — standard library only.

Uses ``ThreadingHTTPServer`` so the whole project keeps zero runtime
dependencies and stays trivially deployment-agnostic (no framework, no vendor
SDK). The handler is a pure router: it maps a path to a controller function and
serialises the result. All logic lives in the controllers / Application API.

Run::

    python -m sanuvia.adapters.http.server

Environment:
    SANUVIA_HOST          (default 0.0.0.0)
    SANUVIA_PORT          (default 8000)
    SANUVIA_BACKEND       memory | sqlite   (default memory)
    SANUVIA_DB_PATH       sqlite file path  (default /data/sanuvia.db)
    SANUVIA_TESTCASE_DIR  dir for saved test cases (default: unset = in-memory)
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast

from . import controllers
from .dashboard import INDEX_HTML
from .manager import TestCaseManager
from .testcase_store import (
    FileTestCaseSpecStore,
    InMemoryTestCaseSpecStore,
    TestCaseSpecStore,
)


class ReviewServer(ThreadingHTTPServer):
    """Holds the shared test-case manager and a lock guarding its mutation."""

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        manager: TestCaseManager,
    ) -> None:
        super().__init__(address, handler)
        self.manager = manager
        self.lock = threading.Lock()


class ReviewHandler(BaseHTTPRequestHandler):
    server_version = "SanuviaReviewHarness/0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _srv(self) -> ReviewServer:
        return cast(ReviewServer, self.server)

    def _send_json(self, obj: dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        parsed: Any = json.loads(raw or b"{}")
        return parsed if isinstance(parsed, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        try:
            path = self.path.split("?", 1)[0]
            srv = self._srv()
            m = srv.manager
            if path in ("/", "/index.html"):
                self._send_html(INDEX_HTML)
                return
            if path == "/api/health":
                self._send_json({"status": "ok"})
                return
            if path == "/api/samples":
                self._send_json(controllers.list_samples())
                return
            if path == "/api/reference-trace":
                self._send_json(controllers.get_reference_trace())
                return
            if path == "/api/reference-graph":
                self._send_json(controllers.get_reference_graph())
                return
            get_routes = {
                "/api/state": controllers.get_state,
                "/api/trace": controllers.get_trace,
                "/api/graph": controllers.get_graph,
                "/api/exit-test": controllers.get_exit_test,
                "/api/export/test-case": controllers.export_test_case,
                "/api/export/trace": controllers.export_trace,
                "/api/export/graph-mermaid": controllers.export_graph_mermaid,
                "/api/export/graph-dot": controllers.export_graph_dot,
                "/api/export/report": controllers.export_report,
            }
            handler = get_routes.get(path)
            if handler is None:
                self._send_json({"error": "not found"}, 404)
                return
            with srv.lock:
                self._send_json(handler(m))
        except Exception as exc:  # noqa: BLE001 — surface errors as JSON
            self._send_json({"error": str(exc)}, 500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = self.path.split("?", 1)[0]
            body = self._read_json()
            m = self._srv().manager
            with self._srv().lock:
                # routes that take a JSON body
                body_routes = {
                    "/api/evidence/add": controllers.add_evidence,
                    "/api/step": controllers.get_step,
                    "/api/test-cases/select": controllers.select_test_case,
                    "/api/test-cases/rename": controllers.rename_test_case,
                    "/api/samples/load": controllers.load_sample,
                    "/api/notes/add": controllers.add_note,
                    "/api/notes/remove": controllers.remove_note,
                    "/api/tags/set": controllers.set_tags,
                    "/api/import": controllers.import_test_case,
                    "/api/compare": controllers.compare,
                    "/api/search": controllers.search,
                }
                # routes that take no body
                simple_routes = {
                    "/api/evidence/run-next": controllers.run_next,
                    "/api/run-all": controllers.run_all,
                    "/api/reset": controllers.reset,
                    "/api/test-cases/new": controllers.new_test_case,
                    "/api/test-cases/duplicate": controllers.duplicate_test_case,
                    "/api/test-cases/save": controllers.save_test_case,
                }
                if path in body_routes:
                    self._send_json(body_routes[path](m, body))
                elif path in simple_routes:
                    self._send_json(simple_routes[path](m))
                else:
                    self._send_json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc)}, 400)


def _spec_store() -> TestCaseSpecStore:
    directory = os.environ.get("SANUVIA_TESTCASE_DIR", "").strip()
    if directory:
        try:
            return FileTestCaseSpecStore(directory)
        except OSError:
            pass  # fall back to in-memory if the directory is not writable
    return InMemoryTestCaseSpecStore()


def main() -> None:
    host = os.environ.get("SANUVIA_HOST", "0.0.0.0")
    port = int(os.environ.get("SANUVIA_PORT", "8000"))
    backend = os.environ.get("SANUVIA_BACKEND", "memory")
    db_path = os.environ.get("SANUVIA_DB_PATH", "/data/sanuvia.db")
    manager = TestCaseManager(
        backend=backend, db_base=db_path, spec_store=_spec_store()
    )
    server = ReviewServer((host, port), ReviewHandler, manager)
    print(
        f"Sanuvia review harness on http://{host}:{port}  "
        f"(backend={backend}, deterministic)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
