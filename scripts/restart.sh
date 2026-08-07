#!/usr/bin/env bash
# Restart the service and confirm it comes back healthy.
#
#     sudo scripts/restart.sh

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_root "$@"

log "Restarting ${SERVICE}…"
systemctl restart "${SERVICE}"

if out="$(wait_healthy)"; then
	ok "Healthy: ${out}"
else
	die "Service unhealthy after restart. Inspect: journalctl -u ${SERVICE} -n 50 --no-pager"
fi
