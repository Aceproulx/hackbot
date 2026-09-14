#!/bin/sh
# use-account.sh <account-name>
#
# Concurrent-safe account bootstrap for Playwright MCP.
# Sets AGENT_BROWSER_PROFILE and PLAYWRIGHT_MCP_USER_DATA_DIR so the calling
# agent points its own Playwright MCP server instance at its own Chrome profile.
#
# ── Why two variables? ────────────────────────────────────────────────────────
# AGENT_BROWSER_PROFILE        → which Chrome user-data-dir to use (cookies/login)
# PLAYWRIGHT_MCP_USER_DATA_DIR → feed this into Playwright MCP's --user-data-dir
#
# Without a per-agent Playwright MCP server process (each with its own
# --user-data-dir), two agents drive the same browser context — one agent's
# browser_navigate moves the other agent's session. Both are required for
# true isolation.
# ─────────────────────────────────────────────────────────────────────────────
#
# Usage:
#   eval "$(./use-account.sh userA)"        # any shell; capture-and-eval
#   source ./use-account.sh userA            # bash/zsh (direct source)
#
# Note: `sh source ./use-account.sh userA` does NOT work — POSIX sh's `.`
# drops positional args. Use the capture-and-eval form in sh.
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
is_sourced() {
  if [ -n "$BASH_VERSION" ]; then
    [ "${BASH_SOURCE[0]}" != "$0" ] && return 0
  elif [ -n "$ZSH_VERSION" ]; then
    case "${ZSH_EVAL_CONTEXT:-}" in *:file*) return 0 ;; esac
  fi
  return 1
}

if is_sourced; then
    # Sourced — set vars in the current shell
    export AGENT_BROWSER_PROFILE="$TARGET_DIR"
    export PLAYWRIGHT_MCP_USER_DATA_DIR="$TARGET_DIR"
    printf '[use-account] AGENT_BROWSER_PROFILE        = %s\n' "$TARGET_DIR" >&2
    printf '[use-account] PLAYWRIGHT_MCP_USER_DATA_DIR = %s\n' "$TARGET_DIR" >&2
    printf '[use-account] Launch your own Playwright MCP server instance with --user-data-dir %s\n' "$TARGET_DIR" >&2
else
    # Executed — print for eval "$(./use-account.sh <name>)"
    printf 'export AGENT_BROWSER_PROFILE="%s"\n'        "$TARGET_DIR"
    printf 'export PLAYWRIGHT_MCP_USER_DATA_DIR="%s"\n' "$TARGET_DIR"
    printf '[use-account] eval this output to set AGENT_BROWSER_PROFILE and PLAYWRIGHT_MCP_USER_DATA_DIR\n' >&2
fi
