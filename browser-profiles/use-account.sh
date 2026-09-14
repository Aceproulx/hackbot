#!/bin/sh
# use-account.sh <account-name>
#
# Concurrent-safe account bootstrap for agent-browser.
# Sets AGENT_BROWSER_PROFILE and AGENT_BROWSER_NAMESPACE so the calling agent
# gets its own isolated Chrome daemon AND its own Chrome profile.
#
# ── Why two variables? ────────────────────────────────────────────────────────
# AGENT_BROWSER_PROFILE   → which Chrome user-data-dir to use (cookies/login)
# AGENT_BROWSER_NAMESPACE → which daemon socket to bind (separate Chrome window)
#
# Without AGENT_BROWSER_NAMESPACE, two agents share one daemon → one Chrome
# window → `agent-browser open <url>` in agent B hijacks agent A's tab.
# Without AGENT_BROWSER_PROFILE, two agents share one login session (cookies).
# Both are required for true isolation.
# ─────────────────────────────────────────────────────────────────────────────
#
# Usage (source so the exports reach the current shell):
#   source ./use-account.sh userA     # bash/zsh
#   . ./use-account.sh userA          # POSIX sh
#
# Or capture-and-eval from a sub-shell:
#   eval "$(./use-account.sh userA)"
#
# The profile directory must already exist (create with clone-profile.sh).

PROFILES_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ "$#" -ne 1 ]; then
    printf 'ERROR: usage: source use-account.sh <account-name>\n' >&2
    exit 2
fi

ACCOUNT="$1"
TARGET_DIR="$PROFILES_DIR/Profile-$ACCOUNT"

if [ ! -d "$TARGET_DIR" ]; then
    printf 'ERROR: profile "%s" does not exist.\n' "$TARGET_DIR" >&2
    printf '       Create it with: %s/clone-profile.sh %s\n' "$(dirname -- "$0")" "$ACCOUNT" >&2
    exit 1
fi

# If sourced: export into current shell directly.
# If executed as a subprocess: print export lines so the caller can eval them.
_SELF="$(basename -- "$0")"
if [ "$_SELF" = "use-account.sh" ]; then
    # Executed — print for eval "$(./use-account.sh <name>)"
    printf 'export AGENT_BROWSER_PROFILE="%s"\n' "$TARGET_DIR"
    printf 'export AGENT_BROWSER_NAMESPACE="agent-%s"\n' "$ACCOUNT"
else
    # Sourced — set in the current shell
    export AGENT_BROWSER_PROFILE="$TARGET_DIR"
    export AGENT_BROWSER_NAMESPACE="agent-$ACCOUNT"
    printf '[use-account] AGENT_BROWSER_PROFILE  = %s\n' "$TARGET_DIR" >&2
    printf '[use-account] AGENT_BROWSER_NAMESPACE = agent-%s\n' "$ACCOUNT" >&2
    printf '[use-account] Run: agent-browser open <url>\n' >&2
fi
