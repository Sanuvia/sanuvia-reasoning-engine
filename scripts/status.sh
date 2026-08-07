#!/usr/bin/env bash
# One-shot health + status overview: service state, health endpoint, deployed
# commit, data footprint, and recent log lines.
#
#     scripts/status.sh

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

echo "── Service ────────────────────────────────────────────────"
${SUDO} systemctl status "${SERVICE}" --no-pager --lines=0 || true

echo
echo "── Health endpoint (${HEALTH_URL}) ────────────────────────"
if out="$(health_json 2>/dev/null)"; then
	ok "${out}"
else
	warn "unreachable — the service may be down (scripts/logs.sh)"
fi

echo
echo "── Deployed code ──────────────────────────────────────────"
if commit="$(as_service git -C "${APP_DIR}" rev-parse --short HEAD 2>/dev/null)"; then
	branch="$(as_service git -C "${APP_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
	echo "  ${APP_DIR} @ ${branch} ${commit}"
else
	echo "  ${APP_DIR} (not a git checkout?)"
fi

echo
echo "── Persistent data (${DATA_DIR}) ──────────────────────────"
if [[ -d "${DATA_DIR}" ]]; then
	dbs="$(find "${DATA_DIR}" -maxdepth 1 -name '*.db' | wc -l | tr -d ' ')"
	specs="$(find "${DATA_DIR}/testcases" -type f 2>/dev/null | wc -l | tr -d ' ')"
	echo "  size:   $(du -sh "${DATA_DIR}" 2>/dev/null | cut -f1)"
	echo "  db files:        ${dbs}"
	echo "  saved testcases: ${specs}"
else
	warn "data dir missing"
fi

echo
echo "── Backups (${BACKUP_DIR}) ────────────────────────────────"
if latest="$(ls -1t "${BACKUP_DIR}"/sanuvia-*.tar.gz 2>/dev/null | head -1)"; then
	echo "  count:  $(ls -1 "${BACKUP_DIR}"/sanuvia-*.tar.gz 2>/dev/null | wc -l | tr -d ' ')"
	echo "  latest: $(basename "${latest}") ($(du -h "${latest}" | cut -f1))"
else
	echo "  none yet (run scripts/backup.sh)"
fi

echo
echo "── Recent logs ────────────────────────────────────────────"
${SUDO} journalctl -u "${SERVICE}" -n 8 --no-pager -o cat 2>/dev/null || true
