#!/usr/bin/env bash
# Tail / view the service logs (journald).
#
#     scripts/logs.sh            # follow live (Ctrl-C to stop)
#     scripts/logs.sh -n 200     # last 200 lines, no follow
#     scripts/logs.sh --since "1 hour ago"
#
# Any extra arguments are passed straight through to journalctl.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

if (( $# == 0 )); then
	exec ${SUDO} journalctl -u "${SERVICE}" -f --no-pager
fi

# If the caller only passed pass-through options (not -f/-n/--since), default to
# following; otherwise honour exactly what they asked for.
exec ${SUDO} journalctl -u "${SERVICE}" --no-pager "$@"
