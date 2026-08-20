"""Finding 3 — clean-host deployment / configuration smoke test.

Verifies, without any cloud-vendor infrastructure, that a fresh environment can:

* obtain the repository (the required deployment artifacts are present),
* load the example configuration (`.env.example` parses; no secrets),
* build/install dependencies (the stdlib-only package imports),
* initialize required persistence (a SQLite store initialises + migrates),
* start the application (the HTTP server boots),
* perform a health check (`/health` returns the documented body),
* run the relevant Phase 0 verification (the synthetic exit test passes).

A shell equivalent for a real host is `scripts/smoke.sh`.
"""

from __future__ import annotations

import ipaddress
import json
import re
import threading
import urllib.request
from pathlib import Path

from sanuvia.adapters.http.manager import TestCaseManager
from sanuvia.adapters.http.server import ReviewHandler, ReviewServer
from sanuvia.adapters.persistence.sqlite_store import SqliteReasoningStore
from sanuvia.adapters.persistence.sqlite_migration import SCHEMA_VERSION
from sanuvia.exit_test.runner import run as run_exit_test

REPO_ROOT = Path(__file__).resolve().parents[1]


def _parse_env(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def test_required_deployment_artifacts_present() -> None:
    for rel in (
        ".env.example", "pyproject.toml", "README.md",
        "deploy/sanuvia.service", "scripts/deploy.sh", "scripts/smoke.sh",
    ):
        assert (REPO_ROOT / rel).exists(), f"missing deployment artifact: {rel}"


def test_env_example_loads_and_contains_no_secrets() -> None:
    text = (REPO_ROOT / ".env.example").read_text()
    env = _parse_env(text)

    # Required, documented keys are present with non-empty placeholder values.
    for key in ("SANUVIA_HOST", "SANUVIA_PORT", "SANUVIA_BACKEND",
                "SANUVIA_DB_PATH", "SANUVIA_TESTCASE_DIR", "PYTHONHASHSEED"):
        assert env.get(key), f"missing/empty config key: {key}"

    # No configuration KEY names a secret (the file holds only non-sensitive
    # config; explanatory comments about secrets are fine and not scanned).
    banned = ("password", "secret", "token", "api_key", "apikey", "private_key")
    for key, value in env.items():
        low_key = key.lower()
        assert not any(b in low_key for b in banned), f"secret-like config key: {key}"
        # No routable IP literal baked into any value (loopback is fine).
        for match in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", value):
            ip = ipaddress.ip_address(match)
            assert ip.is_loopback or ip.is_unspecified, f"routable IP in {key}: {match}"

    # No routable IP literal anywhere in the file (loopback only).
    for match in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text):
        ip = ipaddress.ip_address(match)
        assert ip.is_loopback or ip.is_unspecified, f"unexpected IP literal: {match}"

    # Old repository slug must be gone.
    assert "eelitedesire" not in text


def test_persistence_initializes_and_migrates(tmp_path) -> None:
    store = SqliteReasoningStore(str(tmp_path / "sanuvia.db"))
    assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    store.close()


def test_application_starts_and_health_check_passes(tmp_path) -> None:
    # Emulate the deployed configuration: durable SQLite backend on a temp path.
    manager = TestCaseManager(backend="sqlite", db_base=str(tmp_path / "sanuvia.db"))
    server = ReviewServer(("127.0.0.1", 0), ReviewHandler, manager)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as resp:
            body = json.loads(resp.read())
        assert body == {"status": "ok", "version": "phase0", "backend": "sqlite"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_phase0_exit_test_passes() -> None:
    report = run_exit_test()
    assert report.passed, report.render()
