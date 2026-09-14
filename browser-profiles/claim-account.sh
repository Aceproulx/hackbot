#!/bin/sh
# claim-account.sh
#
# Atomically claims the next free account profile for this agent session.
# Designed for concurrent agents that load the same skill — neither knows
# ahead of time which account it is. This script figures it out.
#
# Uses mkdir(2) atomicity (POSIX-guaranteed) as the lock primitive.
# The lock stores the CALLER'S PID ($PPID — the shell that will eval this
# output), not the script's own PID, so liveness checks work correctly even
# though this script is a short-lived subprocess.
#
# ── Usage ────────────────────────────────────────────────────────────────────
#
#   eval "$(./claim-account.sh)"
#
# Sets three env vars in the calling shell:
#   AGENT_BROWSER_ACCOUNT        → claimed account name  (e.g. userA)
#   AGENT_BROWSER_PROFILE        → full path to the Chrome profile dir
#   PLAYWRIGHT_MCP_USER_DATA_DIR → the profile dir, for Playwright MCP's
#                                  --user-data-dir flag (per-agent isolation)
#
# Run ONCE at the very start of every agent session, before any Playwright MCP
# call. Both agents run the same command — they race to claim different slots.
#
# ── Release ───────────────────────────────────────────────────────────────────
#
#   ./release-account.sh          # uses $AGENT_BROWSER_ACCOUNT
#   ./release-account.sh userA    # explicit
#
# ─────────────────────────────────────────────────────────────────────────────

set -eu

PROFILES_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
LOCK_DIR="$PROFILES_DIR/.locks"
mkdir -p "$LOCK_DIR"

# The PID we record in the lock is PPID — the calling shell that is long-lived,
# not this short-lived script.
OWNER_PID="${PPID:-$$}"

# ── Helper: is a PID still alive? ────────────────────────────────────────────
_pid_alive() {
    kill -0 "$1" 2>/dev/null
}

# ── Helper: try to claim one account ─────────────────────────────────────────
_try_claim() {
    ACCOUNT="$1"
    LOCK="$LOCK_DIR/$ACCOUNT.lock"
    TARGET_DIR="$PROFILES_DIR/Profile-$ACCOUNT"

    [ -d "$TARGET_DIR" ] || return 1   # profile doesn't exist — skip

    # Attempt atomic mkdir
    if mkdir "$LOCK" 2>/dev/null; then
        printf '%s\n' "$OWNER_PID" > "$LOCK/owner_pid"
        return 0
    fi

    # Lock exists — check if holder is still alive
    HOLDER_PID=0
    [ -f "$LOCK/owner_pid" ] && HOLDER_PID="$(cat "$LOCK/owner_pid" 2>/dev/null || echo 0)"

    if [ "$HOLDER_PID" -gt 1 ] && _pid_alive "$HOLDER_PID"; then
        return 1   # live owner — respect the lock
    fi

    # Stale lock — reclaim (rm + mkdir; small window, acceptable in practice)
    printf '[claim-account] stale lock on %s (owner pid=%s dead) — reclaiming\n' \
        "$ACCOUNT" "$HOLDER_PID" >&2
    rm -rf "$LOCK"
    if mkdir "$LOCK" 2>/dev/null; then
        printf '%s\n' "$OWNER_PID" > "$LOCK/owner_pid"
        return 0
    fi

    return 1   # lost the race to reclaim — try next account
}

# ── Scan accounts in order ────────────────────────────────────────────────────
CLAIMED=""
for ACCOUNT in userA userB; do
    if _try_claim "$ACCOUNT"; then
        CLAIMED="$ACCOUNT"
        break
    fi
done

if [ -z "$CLAIMED" ]; then
    printf 'ERROR: claim-account: no free account profile available.\n' >&2
    printf '       Both userA and userB are locked by live processes.\n' >&2
    printf '       Run: ls %s/ to inspect locks.\n' "$LOCK_DIR" >&2
    printf '       To force-clear a stale lock: rm -rf %s/<name>.lock\n' "$LOCK_DIR" >&2
    exit 1
fi

TARGET_DIR="$PROFILES_DIR/Profile-$CLAIMED"
printf '[claim-account] claimed: %s  (owner_pid=%s)\n' "$CLAIMED" "$OWNER_PID" >&2

# Output export lines for: eval "$(./claim-account.sh)"
printf 'export AGENT_BROWSER_ACCOUNT="%s"\n'        "$CLAIMED"
printf 'export AGENT_BROWSER_PROFILE="%s"\n'        "$TARGET_DIR"
printf 'export PLAYWRIGHT_MCP_USER_DATA_DIR="%s"\n' "$TARGET_DIR"
