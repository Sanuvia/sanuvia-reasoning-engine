#!/usr/bin/env bash
# Restore persistent state from a backup archive produced by backup.sh.
#
#     sudo scripts/restore.sh /var/backups/sanuvia/sanuvia-YYYYmmdd-HHMMSS.tar.gz
#     sudo scripts/restore.sh latest      # restore the most recent backup
#
# The service is stopped during restore. The current data directory is moved
# aside (…-prerestore-<ts>) before the archive is unpacked, so a bad restore is
# recoverable.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_root "$@"

arg="${1:-}"
[[ -n "${arg}" ]] || die "usage: sudo $0 <archive.tar.gz | latest>"

if [[ "${arg}" == "latest" ]]; then
	archive="$(ls -1t "${BACKUP_DIR}"/sanuvia-*.tar.gz 2>/dev/null | head -1 || true)"
	[[ -n "${archive}" ]] || die "no backups found in ${BACKUP_DIR}"
else
	archive="${arg}"
fi
[[ -f "${archive}" ]] || die "archive not found: ${archive}"

# Validate the archive contains the expected top-level directory.
tar -tzf "${archive}" | head -1 | grep -q '^sanuvia/' || die "unrecognised archive layout: ${archive}"

log "Restoring from: ${archive}"
warn "This replaces the contents of ${DATA_DIR}."
read -r -p "Continue? [y/N] " reply
[[ "${reply}" =~ ^[Yy]$ ]] || die "aborted."

log "Stopping ${SERVICE}…"
systemctl stop "${SERVICE}" || true

if [[ -d "${DATA_DIR}" ]]; then
	aside="${DATA_DIR}-prerestore-$(date +%Y%m%d-%H%M%S)"
	log "Moving current data aside -> ${aside}"
	mv "${DATA_DIR}" "${aside}"
fi
install -d -o "${SANUVIA_USER}" -g "${SANUVIA_GROUP}" -m 0750 "${DATA_DIR}"

stage="$(mktemp -d)"
trap 'rm -rf "${stage}"' EXIT
tar -xzf "${archive}" -C "${stage}"
# Copy the snapshot contents into DATA_DIR (excluding the manifest).
shopt -s dotglob
cp -a "${stage}/sanuvia/." "${DATA_DIR}/"
rm -f "${DATA_DIR}/BACKUP_MANIFEST.txt"
shopt -u dotglob
chown -R "${SANUVIA_USER}:${SANUVIA_GROUP}" "${DATA_DIR}"

log "Starting ${SERVICE}…"
systemctl start "${SERVICE}"

if out="$(wait_healthy)"; then
	ok "Restore complete and healthy: ${out}"
else
	die "Service unhealthy after restore. Previous data was preserved at ${aside:-<none>}. Inspect: journalctl -u ${SERVICE} -n 50 --no-pager"
fi
