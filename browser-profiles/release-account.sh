#!/bin/sh
# release-account.sh [account-name]
#
# Releases the lock held by claim-account.sh so another agent can claim it.
# Call this when the agent session ends cleanly.
#
# Usage:
#   ./release-account.sh          # uses $AGENT_BROWSER_ACCOUNT env var
#   ./release-account.sh userA    # explicit name
#
# Stale locks (from crashed agents) are auto-cleaned by claim-account.sh
# on the next run — a missed release is not fatal.

set -eu

PROFILES_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
LOCK_DIR="$PROFILES_DIR/.locks"

ACCOUNT="${1:-${AGENT_BROWSER_ACCOUNT:-}}"

if [ -z "$ACCOUNT" ]; then
    printf 'ERROR: release-account: no account name given and $AGENT_BROWSER_ACCOUNT is not set.\n' >&2
    printf '       Usage: ./release-account.sh <account-name>\n' >&2
    exit 2
fi

LOCK="$LOCK_DIR/$ACCOUNT.lock"

if [ ! -d "$LOCK" ]; then
    printf '[release-account] no lock found for %s — nothing to release.\n' "$ACCOUNT" >&2
    exit 0
fi

# The lock records PPID of the claim script — which is the calling shell.
# For release-account.sh, OUR PPID is also the calling shell, so they match.
OWNER_PID=0
[ -f "$LOCK/owner_pid" ] && OWNER_PID="$(cat "$LOCK/owner_pid" 2>/dev/null || echo 0)"

OUR_PPID="${PPID:-0}"

if [ "$OWNER_PID" -eq "$OUR_PPID" ] || \
   [ "$OWNER_PID" -eq "$$" ] || \
   ! kill -0 "$OWNER_PID" 2>/dev/null; then
    rm -rf "$LOCK"
    printf '[release-account] released: %s\n' "$ACCOUNT" >&2
else
    printf 'ERROR: release-account: lock on %s is owned by pid %s (our shell: %s).\n' \
        "$ACCOUNT" "$OWNER_PID" "$OUR_PPID" >&2
    printf '       Force-clear with: rm -rf %s/%s.lock\n' "$LOCK_DIR" "$ACCOUNT" >&2
    exit 1
fi
