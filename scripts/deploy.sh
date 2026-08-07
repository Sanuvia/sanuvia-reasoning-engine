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

log "Installing OS prerequisites (git, ca-certificates)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git ca-certificates

# --- ensure a Python interpreter that meets the package's floor (>=3.11) ------
# Ubuntu 22.04 ships 3.10; the package requires >=3.11. Find a suitable
# interpreter, or install python3.11 from the deadsnakes PPA (non-disruptive:
# it does not replace the system python3).
py_ok() { "$1" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)' >/dev/null 2>&1; }

PYTHON_BIN=""
for cand in python3.13 python3.12 python3.11 python3; do
	if command -v "${cand}" >/dev/null 2>&1 && py_ok "${cand}"; then
		PYTHON_BIN="$(command -v "${cand}")"; break
	fi
done

if [[ -z "${PYTHON_BIN}" ]]; then
	log "No Python >= 3.11 found; installing python3.11 (deadsnakes PPA)…"
	apt-get install -y -qq software-properties-common
	add-apt-repository -y ppa:deadsnakes/ppa
	apt-get update -qq
	apt-get install -y -qq python3.11 python3.11-venv
	py_ok python3.11 || die "python3.11 install did not yield a usable interpreter."
	PYTHON_BIN="$(command -v python3.11)"
fi

# Ensure the venv module for the chosen interpreter is present (e.g. python3.11-venv).
py_ver="$("${PYTHON_BIN}" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if ! "${PYTHON_BIN}" -m venv --help >/dev/null 2>&1; then
	log "Installing python${py_ver}-venv…"
	apt-get install -y -qq "python${py_ver}-venv" || apt-get install -y -qq python3-venv
fi
ok "Using ${PYTHON_BIN} (Python ${py_ver})."

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
# Recreate the venv if it is missing or was built with an unsuitable Python
# (e.g. a previous run that picked up the system 3.10).
if [[ -x "${VENV_DIR}/bin/python" ]] && ! py_ok "${VENV_DIR}/bin/python"; then
	warn "Existing venv uses an unsupported Python; recreating it."
	rm -rf "${VENV_DIR}"
fi

log "Creating virtualenv with ${PYTHON_BIN} and installing the package…"
as_service "${PYTHON_BIN}" -m venv "${VENV_DIR}"
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
