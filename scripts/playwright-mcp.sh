#!/usr/bin/env bash
# playwright-mcp.sh — Playwright MCP launcher for hackbot.
#
# Why a wrapper: Playwright MCP has no CLI flag for arbitrary Chrome launch
# args (--load-extension etc.), but its config file supports
# browser.launchOptions.args. CLI flags override the config wholesale, so all
# browser-related settings live in a generated config file and only
# non-browser flags are passed through to the MCP.
#
# Wired up here:
#   - browser profile: PLAYWRIGHT_PROFILE env (per-slot, set by worker-pool.sh),
#     or --profile <path> (shared), or --isolated (fresh temp profile).
#     Unset env falls back to a fresh temp profile.
#   - headed mode: set "playwright_headed": true in ~/.hackbot/config.json
#     (or PLAYWRIGHT_HEADED=1 env) to launch a visible browser instead of
#     headless. Defaults to headless so autonomous workers stay quiet.
#   - Caido proxy: browser traffic lands in Caido history for evidence.
#   - captcha extensions: buster + captcha-bridge clicker (unpacked MV3),
#     loaded regardless of profile mode (persistent-mode contexts only — the
#     MCP's isolated mode creates a context that skips --load-extension, so
#     --isolated here maps to a fresh temp userDataDir instead).
#
# Usage: playwright-mcp.sh [--isolated|--profile <path>] [MCP flags...]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="${PLAYWRIGHT_PROFILE:-}"
PROXY="${PLAYWRIGHT_PROXY:-http://127.0.0.1:8080}"
EXTENSIONS="${PLAYWRIGHT_EXTENSIONS:-}"

# Extension dirs come from ~/.hackbot/config.json (playwright_extensions) if set.
if [[ -z "$EXTENSIONS" && -f "$HOME/.hackbot/config.json" ]]; then
  EXTENSIONS="$(jq -r '.playwright_extensions // ""' "$HOME/.hackbot/config.json" 2>/dev/null || true)"
fi
if [[ -z "$EXTENSIONS" ]]; then
  EXTENSIONS="$REPO_ROOT/extensions/buster/buster,$REPO_ROOT/extensions/captcha-bridge-mcp/captcha-bridge/extension"
fi

ISOLATED=0
MCP_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --isolated) ISOLATED=1; shift ;;
    --profile) PROFILE="$2"; shift 2 ;;
    *) MCP_ARGS+=("$1"); shift ;;
  esac
done

# Only emit --load-extension for dirs that exist (Chrome is picky about
# missing paths when combined with --disable-extensions-except).
EXT_ARGS='[]'
if [[ -n "$EXTENSIONS" ]]; then
  OK_DIRS=""
  IFS=',' read -ra DIRS <<< "$EXTENSIONS"
  for d in "${DIRS[@]}"; do
    if [[ -d "$d" ]]; then
      OK_DIRS="${OK_DIRS:+$OK_DIRS,}$d"
    else
      echo "playwright-mcp: WARNING extension dir not found: $d" >&2
    fi
  done
  if [[ -n "$OK_DIRS" ]]; then
    EXT_ARGS="$(jq -n --arg e "$OK_DIRS" \
      '[("--load-extension="+$e), ("--disable-extensions-except="+$e)]')"
  fi
fi

CONFIG="$(mktemp /tmp/playwright-mcp.XXXXXX.json)"
trap 'rm -f "$CONFIG"' EXIT

BASE_ARGS="$(jq -n --arg p "$PROXY" \
  '["--no-sandbox", "--proxy-server="+$p]')"
ARGS="$(jq -n --argjson b "$BASE_ARGS" --argjson e "$EXT_ARGS" '$b + $e')"

# Headed mode: opt-in via ~/.hackbot/config.json ("playwright_headed": true)
# or PLAYWRIGHT_HEADED=1 env. Default headless.
HEADED="${PLAYWRIGHT_HEADED:-}"
if [[ -z "$HEADED" && -f "$HOME/.hackbot/config.json" ]]; then
  HEADED="$(jq -r '.playwright_headed // ""' "$HOME/.hackbot/config.json" 2>/dev/null || true)"
fi
if [[ "$HEADED" == "true" || "$HEADED" == "1" ]]; then
  HEADLESS=false
else
  HEADLESS=true
fi

BROWSER="$(jq -n --argjson a "$ARGS" --argjson h "$HEADLESS" \
  '{browserName:"chromium", launchOptions:{channel:"chromium", headless:$h, ignoreDefaultArgs:["--disable-extensions"], args:$a}}')"

# Isolated mode: the MCP's `isolated: true` creates a fresh browser context via
# browser.newContext(), which does NOT carry --load-extension extensions (they
# only attach to the default/persistent context). So "isolated" here means a
# fresh temp userDataDir in persistent mode: same fresh-state semantics, no
# profile-lock collisions, and the captcha extensions still load.
if [[ "$ISOLATED" -eq 1 ]]; then
  TMP_PROFILE="$(mktemp -d /tmp/playwright-profile.XXXXXX)"
  BROWSER="$(jq -n --argjson b "$BROWSER" --arg p "$TMP_PROFILE" '$b + {userDataDir:$p}')"
elif [[ -n "$PROFILE" ]]; then
  BROWSER="$(jq -n --argjson b "$BROWSER" --arg p "$PROFILE" '$b + {userDataDir:$p}')"
fi

jq -n --argjson b "$BROWSER" '{browser:$b}' > "$CONFIG"

export NPM_CONFIG_PREFER_OFFLINE=true NPM_CONFIG_OFFLINE=true
exec npx -y @playwright/mcp@latest --config "$CONFIG" "${MCP_ARGS[@]}"