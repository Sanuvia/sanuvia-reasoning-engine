#!/usr/bin/env bash
# Shared configuration + helpers for the Sanuvia deployment scripts.
# Sourced by deploy.sh / update.sh / backup.sh / restore.sh / logs.sh /
# restart.sh / status.sh. Not meant to be run directly.
#
# Override any default by creating /etc/sanuvia/deploy.conf with KEY=value lines,
# or by exporting the variable before invoking a script.

set -Eeuo pipefail

# --- locate the repo this script lives in (<repo>/scripts/lib.sh) ------------
_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${_LIB_DIR}/.." && pwd)"

# --- canonical layout (override in /etc/sanuvia/deploy.conf) -----------------
APP_DIR="${APP_DIR:-/opt/sanuvia}"                 # where the repo is checked out
SERVICE="${SERVICE:-sanuvia}"                      # systemd unit name
SANUVIA_USER="${SANUVIA_USER:-sanuvia}"            # service account
SANUVIA_GROUP="${SANUVIA_GROUP:-sanuvia}"
DATA_DIR="${DATA_DIR:-/var/lib/sanuvia}"           # persistent SQLite + testcases
CONF_DIR="${CONF_DIR:-/etc/sanuvia}"
ENV_FILE="${ENV_FILE:-${CONF_DIR}/sanuvia.env}"    # systemd EnvironmentFile
BACKUP_DIR="${BACKUP_DIR:-/var/backups/sanuvia}"
VENV_DIR="${VENV_DIR:-${APP_DIR}/.venv}"
BACKUP_RETENTION="${BACKUP_RETENTION:-14}"         # keep this many backups
GIT_BRANCH="${GIT_BRANCH:-main}"

# Load site overrides if present.
if [[ -f /etc/sanuvia/deploy.conf ]]; then
	# shellcheck disable=SC1091
	source /etc/sanuvia/deploy.conf
fi

# Derive the health URL from the env file's port when possible.
_port="8000"
if [[ -f "${ENV_FILE}" ]]; then
	_p="$(grep -E '^SANUVIA_PORT=' "${ENV_FILE}" 2>/dev/null | tail -1 | cut -d= -f2 | tr -d '[:space:]')"
	[[ -n "${_p}" ]] && _port="${_p}"
fi
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${_port}/health}"

# --- logging -----------------------------------------------------------------
_c() { [[ -t 1 ]] && printf '%s' "$1" || printf ''; }
log()  { printf '%s[sanuvia]%s %s\n' "$(_c $'\033[1;34m')" "$(_c $'\033[0m')" "$*"; }
ok()   { printf '%s[  ok  ]%s %s\n'  "$(_c $'\033[1;32m')" "$(_c $'\033[0m')" "$*"; }
warn() { printf '%s[ warn ]%s %s\n'  "$(_c $'\033[1;33m')" "$(_c $'\033[0m')" "$*" >&2; }
die()  { printf '%s[ fail ]%s %s\n'  "$(_c $'\033[1;31m')" "$(_c $'\033[0m')" "$*" >&2; exit 1; }

# --- privilege helpers -------------------------------------------------------
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then SUDO=""; else SUDO="sudo"; fi
require_root() { [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "must run as root: sudo $0 $*"; }

# Run a command as the service user (repo/venv are owned by it).
as_service() { runuser -u "${SANUVIA_USER}" -- "$@"; }

# --- health probe (stdlib python only; no curl dependency) -------------------
health_json() {
	local url="${1:-${HEALTH_URL}}"
	python3 - "$url" <<-'PY'
	import sys, urllib.request
	print(urllib.request.urlopen(sys.argv[1], timeout=4).read().decode())
	PY
}

wait_healthy() {
	local url="${1:-${HEALTH_URL}}" tries="${2:-30}" out
	for _ in $(seq 1 "${tries}"); do
		if out="$(health_json "${url}" 2>/dev/null)"; then
			printf '%s\n' "${out}"; return 0
		fi
		sleep 1
	done
	return 1
}
