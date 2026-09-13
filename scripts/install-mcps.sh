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

install_caido() {
  info "[1/4] Caido MCP"
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
  info "[2/4] Intigriti MCP"
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
  info "[3/4] CAPTCHA bridge MCP"
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
  info "[4/4] Composio MCP"
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

echo ""
install_caido
echo ""
install_intigriti
echo ""
install_captcha_bridge
echo ""
install_composio

echo ""
if [[ "$UPDATE" -eq 1 ]]; then
  echo "MCP update complete."
else
  echo "MCP setup complete. Restart your agent session to pick up new MCP servers."
fi