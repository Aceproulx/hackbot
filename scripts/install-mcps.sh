#!/usr/bin/env bash
# install-mcps.sh — Installs/updates the MCP servers used by hackbot and
# registers them in the OpenCode and Antigravity configs.
#
# Usage: install-mcps.sh [--update]
#   --update   only update npm packages to latest; skip first-time setup.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG=~/.hackbot/config.json

UPDATE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --update) UPDATE=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--update]"
      exit 0 ;;
    *) echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
  esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

info() { printf "${BOLD}%s${NC}\n" "$*"; }
ok()   { printf "${GREEN}  ✓${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}  !${NC} %s\n" "$*"; }

command -v npm >/dev/null 2>&1 || { echo "ERROR: npm is required but not installed." >&2; exit 1; }
command -v jq  >/dev/null 2>&1 || { echo "ERROR: jq is required but not installed." >&2; exit 1; }

OPENCODE_CONFIG="$HOME/.config/opencode/opencode.jsonc"
ANTIGRAVITY_CONFIG="$HOME/.gemini/antigravity-cli/settings.json"

npm_install() {
  local PKG="$1"
  if [[ "$UPDATE" -eq 1 ]]; then
    npm install -g "$PKG@latest" >/dev/null 2>&1
  else
    npm install -g "$PKG" >/dev/null 2>&1
  fi
}

get_key() {
  local FIELD="$1" LABEL="$2"
  local VAL=""
  if [[ -f "$CONFIG" ]]; then
    VAL="$(jq -r ".${FIELD} // empty" "$CONFIG" 2>/dev/null || true)"
  fi
  if [[ -z "$VAL" && -t 0 ]]; then
    read -r -p "$LABEL" VAL
  fi
  printf '%s' "$VAL"
}

register_mcp() {
  local FILE="$1" NAME="$2" CMD="$3" ARGS_JSON="$4" ENV_JSON="$5"
  mkdir -p "$(dirname "$FILE")"

  local ENTRY TMP
  ENTRY="$(jq -n --arg c "$CMD" --argjson a "$ARGS_JSON" --argjson e "$ENV_JSON" \
    '{command:$c, args:$a, env:$e}')"

  if [[ -f "$FILE" ]]; then
    if jq -e . "$FILE" >/dev/null 2>&1; then
      TMP="$FILE.tmp"
      jq --arg n "$NAME" --argjson v "$ENTRY" '.mcpServers[$n] = $v' "$FILE" > "$TMP" \
        && mv "$TMP" "$FILE"
      ok "registered '$NAME' in $FILE"
    else
      warn "'$NAME' NOT registered in $FILE (file is not parseable JSON — likely JSONC comments)."
      info "    Add manually:"
      jq -n --arg n "$NAME" --argjson v "$ENTRY" '{mcpServers:{($n):$v}}' | sed 's/^/    /'
    fi
  else
    jq -n --arg n "$NAME" --argjson v "$ENTRY" '{mcpServers: {($n): $v}}' > "$FILE"
    ok "created $FILE with '$NAME'"
  fi
}

register_everywhere() {
  local NAME="$1" CMD="$2" ARGS_JSON="$3" ENV_JSON="$4"
  register_mcp "$OPENCODE_CONFIG"     "$NAME" "$CMD" "$ARGS_JSON" "$ENV_JSON"
  register_mcp "$ANTIGRAVITY_CONFIG"  "$NAME" "$CMD" "$ARGS_JSON" "$ENV_JSON"
}

# OpenCode uses a different MCP schema than the generic mcpServers format:
#   "mcp": { "<name>": { "type": "local", "command": [...], "enabled": true, "environment": {...} } }
register_opencode_native() {
  local NAME="$1" CMD_ARRAY_JSON="$2" ENV_JSON="$3"
  mkdir -p "$(dirname "$OPENCODE_CONFIG")"

  local ENTRY TMP
  if [[ "$ENV_JSON" == '{}' ]]; then
    ENTRY="$(jq -n --argjson c "$CMD_ARRAY_JSON" \
      '{type:"local", command:$c, enabled:true}')"
  else
    ENTRY="$(jq -n --argjson c "$CMD_ARRAY_JSON" --argjson e "$ENV_JSON" \
      '{type:"local", command:$c, enabled:true, environment:$e}')"
  fi

  if [[ -f "$OPENCODE_CONFIG" ]]; then
    if jq -e . "$OPENCODE_CONFIG" >/dev/null 2>&1; then
      TMP="$OPENCODE_CONFIG.tmp"
      jq --arg n "$NAME" --argjson v "$ENTRY" \
        '.mcp[$n] = $v' "$OPENCODE_CONFIG" > "$TMP" \
        && mv "$TMP" "$OPENCODE_CONFIG"
      ok "registered '$NAME' in $OPENCODE_CONFIG (opencode native format)"
    else
      warn "'$NAME' NOT registered in $OPENCODE_CONFIG (file is not parseable JSON — likely JSONC comments)."
      info "    Add manually:"
      jq -n --arg n "$NAME" --argjson v "$ENTRY" '{mcp:{($n):$v}}' | sed 's/^/    /'
    fi
  else
    jq -n --arg n "$NAME" --argjson v "$ENTRY" '{mcp: {($n): $v}}' > "$OPENCODE_CONFIG"
    ok "created $OPENCODE_CONFIG with '$NAME'"
  fi
}

install_caido() {
  info "[1/5] Caido MCP"
  if npm_install "@caido/mcp-server"; then
    ok "@caido/mcp-server installed/updated"
  else
    warn "@caido/mcp-server npm install failed"
    return 0
  fi

  local KEY PORT URL
  KEY="$(get_key caido_api_key "Enter your Caido API key (from Caido Settings → API): ")"
  PORT="$(jq -r '.caido_proxy_port // 1337' "$CONFIG" 2>/dev/null || echo 1337)"
  URL="http://127.0.0.1:${PORT}"

  if [[ -z "$KEY" ]]; then
    warn "No Caido API key set — skipping registration."
    info "    Set 'caido_api_key' in $CONFIG and re-run, or register manually."
    return 0
  fi

  local ENV_JSON
  ENV_JSON="$(jq -n --arg k "$KEY" --arg u "$URL" '{CAIDO_API_KEY:$k, CAIDO_URL:$u}')"
  register_everywhere "caido" "npx" '["-y","@caido/mcp-server"]' "$ENV_JSON"
}

install_intigriti() {
  info "[2/5] Intigriti MCP"
  if npm_install "@intigriti/mcp"; then
    ok "@intigriti/mcp installed/updated"
  else
    warn "@intigriti/mcp npm install failed"
    return 0
  fi

  local KEY
  KEY="$(get_key intigriti_api_key "Get your API key at https://app.intigriti.com/profile/api-keys
Enter it: ")"

  if [[ -z "$KEY" ]]; then
    warn "No Intigriti API key set — skipping registration."
    info "    Set 'intigriti_api_key' in $CONFIG and re-run, or register manually."
    return 0
  fi

  local ENV_JSON
  ENV_JSON="$(jq -n --arg k "$KEY" '{INTIGRITI_API_KEY:$k}')"
  register_everywhere "intigriti" "npx" '["-y","@intigriti/mcp"]' "$ENV_JSON"
}

install_captcha_bridge() {
  info "[3/5] CAPTCHA bridge MCP"
  local SRC="$REPO_ROOT/mcp/captcha-bridge"
  if [[ ! -d "$SRC" ]]; then
    info "    captcha-bridge not present in repo ($SRC) — skipping"
    return 0
  fi

  local BIN="$SRC/dist/index.js"
  if [[ ! -f "$BIN" ]]; then
    if (cd "$SRC" && npm install >/dev/null 2>&1 && npm run build >/dev/null 2>&1); then
      ok "built captcha-bridge"
    else
      warn "captcha-bridge build failed — skipping registration"
      return 0
    fi
  fi

  local ARGS_JSON
  ARGS_JSON="$(jq -n --arg p "$BIN" '[$p]')"
  register_everywhere "captcha-bridge" "node" "$ARGS_JSON" "{}"
  info "    Install the captcha-bridge Chrome extension and ensure it's enabled in every Chrome profile."
}

install_composio() {
  info "[4/5] Composio MCP"
  if npm_install "composio-mcp"; then
    ok "composio-mcp installed/updated"
  else
    warn "composio-mcp npm install failed"
    return 0
  fi

  local KEY
  KEY="$(get_key composio_api_key "Enter your Composio API key: ")"
  if [[ -z "$KEY" ]]; then
    warn "No Composio API key set — skipping registration."
    info "    Set 'composio_api_key' in $CONFIG and re-run, or register manually."
    return 0
  fi

  local ENV_JSON
  ENV_JSON="$(jq -n --arg k "$KEY" '{COMPOSIO_API_KEY:$k}')"
  register_everywhere "composio" "npx" '["-y","composio-mcp"]' "$ENV_JSON"
}

install_playwright() {
  info "[5/5] Playwright MCP (browser automation)"
  # Uses npx lazily (@playwright/mcp fetched on first launch) — no global install.
  # Requires Google Chrome installed on the system (the skill configures
  # --browser chrome with isolated --user-data-dir profiles).
  if ! command -v google-chrome >/dev/null 2>&1 && ! command -v google-chrome-stable >/dev/null 2>&1; then
    warn "Google Chrome not found on PATH — Playwright MCP is configured with --browser chrome."
    info "    Install Chrome: https://www.google.com/chrome/  (or set the flag to 'chromium')."
  fi

  local MISC PORT
  MISC="$(jq -r '.hackbot_misc_dir // "~/Projects/hackbot-misc"' "$CONFIG" 2>/dev/null || echo "~/Projects/hackbot-misc")"
  MISC="${MISC/#\~/$HOME}"
  PORT="$(jq -r '.caido_proxy_port // 8080' "$CONFIG" 2>/dev/null || echo 8080)"

  local CMD_JSON ENV_JSON
  # Match the live opencode config command array exactly.
  CMD_JSON="$(jq -n --arg misc "$MISC" --arg port "$PORT" \
    '["npx","-y","@playwright/mcp@latest","--no-sandbox","--browser","chrome","--caps","vision","--console-level","info","--ignore-https-errors","--proxy-server",("http://127.0.0.1:"+$port),"--user-data-dir",($misc+"/.agent-browser-profiles/Profile-userA")]')"
  ENV_JSON="{}"

  # OpenCode uses the native "mcp" schema; Antigravity uses the generic mcpServers schema.
  register_opencode_native "playwright" "$CMD_JSON" "$ENV_JSON"
  register_mcp "$ANTIGRAVITY_CONFIG" "playwright" "npx" \
    "$(jq -n --argjson c "$CMD_JSON" '$c[1:]')" "$ENV_JSON"
  ok "registered 'playwright' in both configs"

  info "    Browser profiles: $MISC/.agent-browser-profiles/ (claim-account.sh / use-account.sh)"
  info "    Create profiles with: $REPO_ROOT/browser-profiles/clone-profile.sh <name>"
  info "    NOTE: each concurrent agent needs its OWN Playwright MCP server process pointed at its own --user-data-dir profile."
}

echo ""
install_caido
echo ""
install_intigriti
echo ""
install_captcha_bridge
echo ""
install_composio
echo ""
install_playwright

echo ""
if [[ "$UPDATE" -eq 1 ]]; then
  echo "MCP update complete."
else
  echo "MCP setup complete. Restart your agent session to pick up new MCP servers."
fi