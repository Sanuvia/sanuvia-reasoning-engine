#!/usr/bin/env bash
# First-time production provisioning on a clean Ubuntu host.
#
# Idempotent: safe to re-run. It creates the service user, directories, virtual
# environment, environment file, and systemd unit, then starts the service.
#
# Prerequisite: this repository is already checked out (recommended at
# /opt/sanuvia). Run from anywhere inside it:
#
#     sudo scripts/deploy.sh
#
# Caddy (HTTPS) is set up separately — see docs/deployment.md.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_root "$@"

# If the repo was cloned somewhere other than APP_DIR, deploy in place.
if [[ "${REPO_ROOT}" != "${APP_DIR}" ]]; then
	warn "Repo is at ${REPO_ROOT}, not APP_DIR=${APP_DIR}."
	warn "Deploying in place from ${REPO_ROOT} (recommended: clone into ${APP_DIR})."
	APP_DIR="${REPO_ROOT}"
	VENV_DIR="${APP_DIR}/.venv"
fi

log "Installing OS prerequisites (python3, venv, pip, git)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git ca-certificates

# --- service account ---------------------------------------------------------
if ! id -u "${SANUVIA_USER}" >/dev/null 2>&1; then
	log "Creating system user '${SANUVIA_USER}'…"
	useradd --system --home-dir "${DATA_DIR}" --shell /usr/sbin/nologin "${SANUVIA_USER}"
fi

# --- directories -------------------------------------------------------------
log "Creating directories…"
install -d -o "${SANUVIA_USER}" -g "${SANUVIA_GROUP}" -m 0750 "${DATA_DIR}" "${DATA_DIR}/testcases"
install -d -o "${SANUVIA_USER}" -g "${SANUVIA_GROUP}" -m 0750 "${BACKUP_DIR}"
install -d -m 0755 "${CONF_DIR}"
chown -R "${SANUVIA_USER}:${SANUVIA_GROUP}" "${APP_DIR}"

# git may refuse to operate on a dir owned by another user; mark it safe.
git config --system --add safe.directory "${APP_DIR}" 2>/dev/null || true

# --- virtualenv + package ----------------------------------------------------
log "Creating virtualenv and installing the package (stdlib-only core)…"
as_service python3 -m venv "${VENV_DIR}"
as_service "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
as_service "${VENV_DIR}/bin/pip" install --quiet "${APP_DIR}"

# --- environment file --------------------------------------------------------
if [[ ! -f "${ENV_FILE}" ]]; then
	log "Installing ${ENV_FILE} from .env.example…"
	install -m 0640 -o root -g "${SANUVIA_GROUP}" "${APP_DIR}/.env.example" "${ENV_FILE}"
else
	ok "Env file ${ENV_FILE} already present (left unchanged)."
fi

# --- systemd unit ------------------------------------------------------------
log "Installing systemd unit '${SERVICE}.service'…"
sed \
	-e "s#@APP_DIR@#${APP_DIR}#g" \
	-e "s#@VENV_DIR@#${VENV_DIR}#g" \
	-e "s#@ENV_FILE@#${ENV_FILE}#g" \
	-e "s#@DATA_DIR@#${DATA_DIR}#g" \
	-e "s#@USER@#${SANUVIA_USER}#g" \
	-e "s#@GROUP@#${SANUVIA_GROUP}#g" \
	"${APP_DIR}/deploy/sanuvia.service" > "/etc/systemd/system/${SERVICE}.service"

systemctl daemon-reload
systemctl enable "${SERVICE}" >/dev/null 2>&1 || true
systemctl restart "${SERVICE}"

# --- health gate -------------------------------------------------------------
log "Waiting for the service to become healthy…"
if out="$(wait_healthy)"; then
	ok "Service healthy: ${out}"
else
	die "Service did not become healthy. Inspect: journalctl -u ${SERVICE} -n 50 --no-pager"
fi

cat <<EOF

$(ok "Deployment complete.")

  Service : ${SERVICE} (systemctl status ${SERVICE})
  App     : ${APP_DIR}
  Data    : ${DATA_DIR}
  Env     : ${ENV_FILE}
  Health  : ${HEALTH_URL}

Next: put Caddy in front for HTTPS on buyafraction.com —
  sudo cp ${APP_DIR}/deploy/Caddyfile /etc/caddy/Caddyfile
  sudo systemctl reload caddy
See docs/deployment.md for details.
EOF
