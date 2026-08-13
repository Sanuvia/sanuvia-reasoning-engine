#!/usr/bin/env bash
# Clean-host deployment smoke test (Finding 3).
#
# Proves, on a fresh checkout with nothing but Python 3.11+ available, that the
# application installs, initialises persistence, starts, answers a health check,
# and passes the Phase 0 exit test. No cloud-vendor infrastructure required.
#
#     scripts/smoke.sh
#
# Exit code 0 = the clean-host deployment path works end to end.

set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"; [[ -n "${SRV_PID:-}" ]] && kill "${SRV_PID}" 2>/dev/null || true' EXIT

PY="${PYTHON:-python3}"
PORT="${SMOKE_PORT:-8931}"

echo "== 1. Load example configuration =="
test -f .env.example
# shellcheck disable=SC2046
export $(grep -E '^[A-Z0-9_]+=' .env.example | xargs)
# Redirect persistence to a throwaway dir for the smoke run.
export SANUVIA_BACKEND=sqlite
export SANUVIA_DB_PATH="${WORK}/sanuvia.db"
export SANUVIA_TESTCASE_DIR="${WORK}/testcases"
export SANUVIA_HOST=127.0.0.1
export SANUVIA_PORT="${PORT}"
mkdir -p "${SANUVIA_TESTCASE_DIR}"

echo "== 2. Build / install dependencies (stdlib-only core) =="
"${PY}" -m venv "${WORK}/venv"
"${WORK}/venv/bin/pip" install --quiet --upgrade pip
"${WORK}/venv/bin/pip" install --quiet .
VENV_PY="${WORK}/venv/bin/python"

echo "== 3. Phase 0 verification (synthetic exit test) =="
"${VENV_PY}" -m sanuvia.exit_test

echo "== 4. Start the application =="
"${VENV_PY}" -m sanuvia.adapters.http.server >"${WORK}/server.log" 2>&1 &
SRV_PID=$!

echo "== 5. Health check =="
ok=""
for _ in $(seq 1 30); do
	if body="$("${VENV_PY}" -c "import urllib.request,sys;print(urllib.request.urlopen('http://127.0.0.1:${PORT}/health',timeout=2).read().decode())" 2>/dev/null)"; then
		ok="${body}"; break
	fi
	sleep 1
done
[[ -n "${ok}" ]] || { echo "health check failed; server log:"; cat "${WORK}/server.log"; exit 1; }
echo "   ${ok}"
echo "${ok}" | grep -q '"status": "ok"'
echo "${ok}" | grep -q '"backend": "sqlite"'

echo "== 6. Persistence initialised on disk =="
# The harness creates one durable SQLite file per Test Case, derived from
# SANUVIA_DB_PATH (e.g. sanuvia.test-case-1.db). Confirm at least one exists.
db_dir="$(dirname "${SANUVIA_DB_PATH}")"
db_stem="$(basename "${SANUVIA_DB_PATH}" .db)"
count="$(find "${db_dir}" -maxdepth 1 -name "${db_stem}*.db" | wc -l | tr -d ' ')"
[[ "${count}" -ge 1 ]] || { echo "no SQLite database created under ${db_dir}"; ls -la "${db_dir}"; exit 1; }
echo "   ${count} SQLite database file(s) under ${db_dir}"

echo "SMOKE OK — clean-host deployment path works end to end."
