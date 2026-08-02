"""Architecture guards.

The core's independence from frameworks, cloud, and foundation models is a hard
constraint, not a convention. These tests fail the build if the domain (or the
application layer) grows a forbidden dependency — so deployment-agnosticism is
enforced automatically rather than remembered.
"""

from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "sanuvia"

# Substrings that must never appear in a core import. Frameworks, ORMs, web,
# cloud SDKs, and foundation-model clients all belong in adapters only.
FORBIDDEN_IMPORT_FRAGMENTS = (
    "fastapi",
    "flask",
    "django",
    "starlette",
    "pydantic",
    "sqlalchemy",
    "sqlite3",
    "psycopg",
    "boto3",
    "botocore",
    "google.cloud",
    "azure",
    "redis",
    "requests",
    "httpx",
    "openai",
    "anthropic",
)


def _imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _python_files(package: str) -> list[pathlib.Path]:
    return sorted((SRC / package).rglob("*.py"))


def test_domain_has_no_forbidden_dependencies() -> None:
    offenders: dict[str, set[str]] = {}
    for path in _python_files("domain"):
        bad = {
            mod
            for mod in _imported_modules(path)
            if any(frag in mod for frag in FORBIDDEN_IMPORT_FRAGMENTS)
        }
        if bad:
            offenders[str(path.relative_to(SRC))] = bad
    assert not offenders, f"Domain imports forbidden infrastructure: {offenders}"


def test_domain_does_not_depend_on_application_or_adapters() -> None:
    for path in _python_files("domain"):
        for mod in _imported_modules(path):
            assert not mod.startswith("sanuvia.application"), path
            assert not mod.startswith("sanuvia.adapters"), path


def test_application_has_no_forbidden_dependencies() -> None:
    offenders: dict[str, set[str]] = {}
    for path in _python_files("application"):
        bad = {
            mod
            for mod in _imported_modules(path)
            if any(frag in mod for frag in FORBIDDEN_IMPORT_FRAGMENTS)
        }
        if bad:
            offenders[str(path.relative_to(SRC))] = bad
    assert not offenders, f"Application imports forbidden infrastructure: {offenders}"


def test_application_does_not_depend_on_adapters() -> None:
    for path in _python_files("application"):
        for mod in _imported_modules(path):
            assert not mod.startswith("sanuvia.adapters"), path
