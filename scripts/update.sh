#!/usr/bin/env bash
# Update to the latest code from GitHub and restart the service.
#
#     sudo scripts/update.sh
#
# Steps: back up data -> git pull -> reinstall package -> run the deterministic
# Exit Test as a gate -> restart -> health check. If the Exit Test fails, the
# service is NOT restarted onto the new code.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_root "$@"

[[ "${REPO_ROOT}" == "${APP_DIR}" ]] || { APP_DIR="${REPO_ROOT}"; VENV_DIR="${APP_DIR}/.venv"; }

log "Backing up data before update…"
"${_LIB_DIR}/backup.sh" || warn "Backup step reported a problem; continuing."

log "Fetching latest code (${GIT_BRANCH})…"
as_service git -C "${APP_DIR}" fetch --quiet origin "${GIT_BRANCH}"
before="$(as_service git -C "${APP_DIR}" rev-parse HEAD)"
as_service git -C "${APP_DIR}" pull --ff-only --quiet origin "${GIT_BRANCH}"
after="$(as_service git -C "${APP_DIR}" rev-parse HEAD)"

if [[ "${before}" == "${after}" ]]; then
	ok "Already up to date at ${after:0:8}; reinstalling + verifying anyway."
else
	log "Updated ${before:0:8} -> ${after:0:8}."
fi

log "Reinstalling package…"
as_service "${VENV_DIR}/bin/pip" install --quiet "${APP_DIR}"

log "Running the Exit Test (determinism / Phase 0 proof gate)…"
if as_service "${VENV_DIR}/bin/python" -m sanuvia.exit_test; then
	ok "Exit Test PASS."
else
	die "Exit Test FAILED on the new code — service left running on the previous version. Investigate before retrying."
fi

log "Restarting ${SERVICE}…"
systemctl restart "${SERVICE}"

if out="$(wait_healthy)"; then
	ok "Update complete and healthy: ${out}"
else
	die "Service unhealthy after restart. Inspect: journalctl -u ${SERVICE} -n 50 --no-pager (consider scripts/restore.sh)"
fi
