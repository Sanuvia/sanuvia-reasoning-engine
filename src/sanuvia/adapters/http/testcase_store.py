"""Persistence for Test Case *definitions* (their evidence sequences).

Only the authored sequence is persisted — never the reasoning state, which is
regenerable by rerunning the sequence deterministically. Kept behind a small
port so persistence is optional and deployment-agnostic: the in-memory adapter is
the default; a file adapter (JSON per test case, under a configured directory)
provides durability across restarts.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TestCaseSpecStore(Protocol):
    def save(self, spec: dict[str, Any]) -> None: ...
    def load_all(self) -> list[dict[str, Any]]: ...
    def delete(self, test_case_id: str) -> None: ...


class InMemoryTestCaseSpecStore:
    """Non-durable store (default). Save works within the process lifetime."""

    def __init__(self) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}

    def save(self, spec: dict[str, Any]) -> None:
        self._by_id[str(spec["id"])] = spec

    def load_all(self) -> list[dict[str, Any]]:
        return list(self._by_id.values())

    def delete(self, test_case_id: str) -> None:
        self._by_id.pop(test_case_id, None)


class FileTestCaseSpecStore:
    """Durable store: one JSON file per test case under ``directory``."""

    def __init__(self, directory: str) -> None:
        self._dir = directory
        os.makedirs(self._dir, exist_ok=True)

    def _path(self, test_case_id: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in test_case_id)
        return os.path.join(self._dir, f"{safe}.json")

    def save(self, spec: dict[str, Any]) -> None:
        with open(self._path(str(spec["id"])), "w", encoding="utf-8") as fh:
            json.dump(spec, fh, indent=2)

    def load_all(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for name in sorted(os.listdir(self._dir)):
            if name.endswith(".json"):
                with open(os.path.join(self._dir, name), encoding="utf-8") as fh:
                    out.append(json.load(fh))
        return out

    def delete(self, test_case_id: str) -> None:
        path = self._path(test_case_id)
        if os.path.exists(path):
            os.remove(path)
