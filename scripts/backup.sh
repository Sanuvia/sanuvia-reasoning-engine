#!/usr/bin/env bash
# Back up all persistent state (SQLite reasoning databases + saved Review
# Datasets / Test Case definitions) to a timestamped, compressed archive.
#
#     sudo scripts/backup.sh            # -> /var/backups/sanuvia/sanuvia-YYYYmmdd-HHMMSS.tar.gz
#     sudo scripts/backup.sh /path/out  # write archive into a custom directory
#
# SQLite databases are copied with the online-backup API (consistent even while
# the service is running), so no downtime is required.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_root "$@"

out_dir="${1:-${BACKUP_DIR}}"
install -d -o "${SANUVIA_USER}" -g "${SANUVIA_GROUP}" -m 0750 "${out_dir}"

# Timestamp from the system clock (used only to name the archive).
ts="$(date +%Y%m%d-%H%M%S)"
stage="$(mktemp -d)"
trap 'rm -rf "${stage}"' EXIT
snap="${stage}/sanuvia"
mkdir -p "${snap}"

log "Snapshotting ${DATA_DIR} …"
# Consistent copy of every *.db via SQLite's backup API; plain copy of the rest
# (saved Test Case JSON definitions, etc.).
python3 - "${DATA_DIR}" "${snap}" <<-'PY'
	import os, shutil, sqlite3, sys
	src, dst = sys.argv[1], sys.argv[2]
	for root, _dirs, files in os.walk(src):
	    rel = os.path.relpath(root, src)
	    outdir = os.path.join(dst, rel) if rel != "." else dst
	    os.makedirs(outdir, exist_ok=True)
	    for name in files:
	        s = os.path.join(root, name)
	        d = os.path.join(outdir, name)
	        if name.endswith(".db"):
	            src_con = sqlite3.connect(f"file:{s}?mode=ro", uri=True)
	            try:
	                dst_con = sqlite3.connect(d)
	                try:
	                    src_con.backup(dst_con)
	                finally:
	                    dst_con.close()
	            finally:
	                src_con.close()
	        else:
	            shutil.copy2(s, d)
	print("ok")
PY

# Record provenance alongside the data.
{
	echo "created_at=${ts}"
	echo "host=$(hostname)"
	echo "git_commit=$(as_service git -C "${APP_DIR}" rev-parse HEAD 2>/dev/null || echo unknown)"
	echo "data_dir=${DATA_DIR}"
} > "${snap}/BACKUP_MANIFEST.txt"

archive="${out_dir}/sanuvia-${ts}.tar.gz"
tar -czf "${archive}" -C "${stage}" sanuvia
chown "${SANUVIA_USER}:${SANUVIA_GROUP}" "${archive}"
chmod 0640 "${archive}"
ok "Backup written: ${archive} ($(du -h "${archive}" | cut -f1))"

# --- retention ---------------------------------------------------------------
mapfile -t backups < <(ls -1t "${out_dir}"/sanuvia-*.tar.gz 2>/dev/null || true)
if (( ${#backups[@]} > BACKUP_RETENTION )); then
	log "Pruning old backups (keeping ${BACKUP_RETENTION})…"
	for old in "${backups[@]:${BACKUP_RETENTION}}"; do
		rm -f "${old}" && log "  removed $(basename "${old}")"
	done
fi
