#!/usr/bin/env bash
# install-skills.sh — Copies skills/agents from the repo into the OpenCode
# directories, then substitutes config values into each installed file.
#
# Usage: install-skills.sh --config <path-to-config.json> [--no-prompt]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

CONFIG_FILE=""
NO_PROMPT=0

usage() {
  cat <<EOF
Usage: $0 --config <path-to-config.json> [--no-prompt]
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)    CONFIG_FILE="$2"; shift 2 ;;
    --no-prompt) NO_PROMPT=1; shift ;;
    -h|--help)   usage ;;
    *) echo "ERROR: Unknown option: $1" >&2; usage ;;
  esac
done

[[ -n "$CONFIG_FILE" ]] || { echo "ERROR: --config is required." >&2; usage; }
[[ -f "$CONFIG_FILE" ]] || { echo "ERROR: Config file not found: $CONFIG_FILE" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq is required but not installed." >&2; exit 1; }

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

apply_config() {
  local FILE="$1"
  local CONFIG="${CONFIG_FILE:-$HOME/.hackbot/config.json}"
  sed -i \
    -e "s|{{EMAIL_BASE}}|$(jq -r '.email_base' "$CONFIG")|g" \
    -e "s|{{EMAIL_DOMAIN}}|$(jq -r '.email_domain' "$CONFIG")|g" \
    -e "s|{{INTIGRITI_USERNAME}}|$(jq -r '.intigriti_username' "$CONFIG")|g" \
    -e "s|{{BLIND_XSS_URL}}|$(jq -r '.blind_xss_url' "$CONFIG")|g" \
    -e "s|{{CAIDO_PROXY_PORT}}|$(jq -r '.caido_proxy_port' "$CONFIG")|g" \
    -e "s|{{CURL_PROXY_PORT}}|$(jq -r '.curl_proxy_port' "$CONFIG")|g" \
    -e "s|{{TELEGRAM_BOT_TOKEN}}|$(jq -r '.telegram_bot_token' "$CONFIG")|g" \
    -e "s|{{TELEGRAM_CHAT_ID}}|$(jq -r '.telegram_chat_id' "$CONFIG")|g" \
    -e "s|{{OOB_TUNNEL_URL}}|$(jq -r '.oob_tunnel_url' "$CONFIG")|g" \
    -e "s|{{PAYLOADS_DIR}}|$(jq -r '.payloads_dir' "$CONFIG")|g" \
    -e "s|{{SESSIONS_DIR}}|$(jq -r '.sessions_dir' "$CONFIG")|g" \
    -e "s|{{HACKBOT_MISC_DIR}}|$(jq -r '.hackbot_misc_dir' "$CONFIG")|g" \
    -e "s|{{HACKBOT_DIR}}|$REPO_ROOT|g" \
    -e "s|{{MAX_WORKER_SLOTS}}|$(jq -r '.max_worker_slots' "$CONFIG")|g" \
    "$FILE"
}

install_if_changed() {
  local SRC="$1" DST="$2"
  mkdir -p "$(dirname "$DST")"
  if [[ -f "$DST" ]] && diff -q <(sha256sum "$SRC" | cut -d' ' -f1) <(sha256sum "$DST" | cut -d' ' -f1) &>/dev/null; then
    return 0
  fi
  cp "$SRC" "$DST"
  apply_config "$DST"
  echo "  ✓ $(basename "$DST")"
}

# Copies a skill's supporting files (reference/, scripts/, etc.) from the repo
# skill dir into the installed skill dir, applying config substitution to each.
install_skill_support_files() {
  local SRC_DIR="$1" DST_DIR="$2"
  local FILE REL DST
  while IFS= read -r -d '' FILE; do
    REL="${FILE#"$SRC_DIR"/}"
    DST="$DST_DIR/$REL"
    install_if_changed "$FILE" "$DST"
  done < <(find "$SRC_DIR" -type f ! -name 'SKILL.md' -print0)
}

install_opencode() {
  local SKILL_DIR="$REPO_ROOT/skills/opencode"
  if [[ ! -d "$SKILL_DIR" ]]; then
    echo "  ${YELLOW}!${NC} $SKILL_DIR not found — skipping opencode skills"
  else
    mkdir -p "$HOME/.config/opencode/skill"
    local NAME SRC DST
    for NAME in "$SKILL_DIR"/*/; do
      [[ -d "$NAME" ]] || continue
      local SKILL_NAME; SKILL_NAME="$(basename "$NAME")"
      SRC="$NAME/SKILL.md"
      [[ -f "$SRC" ]] || { echo "  ${YELLOW}!${NC} no SKILL.md in $NAME — skipping"; continue; }
      DST="$HOME/.config/opencode/skill/$SKILL_NAME/SKILL.md"
      install_if_changed "$SRC" "$DST"
      # Supporting files (reference/, scripts/, ...) — required for skills
      # that reference relative paths from their base directory.
      # Normalize NAME (glob leaves a trailing slash) so the prefix-strip
      # inside install_skill_support_files matches.
      install_skill_support_files "${NAME%/}" "$HOME/.config/opencode/skill/$SKILL_NAME"
    done
  fi

  local AGENT_DIR="$REPO_ROOT/agents/opencode"
  if [[ ! -d "$AGENT_DIR" ]]; then
    echo "  ${YELLOW}!${NC} $AGENT_DIR not found — skipping opencode agents"
    return 0
  fi
  mkdir -p "$HOME/.config/opencode/agent"
  local SRC DST installed=0
  for SRC in "$AGENT_DIR"/*.md; do
    [[ -f "$SRC" ]] || continue
    DST="$HOME/.config/opencode/agent/$(basename "$SRC")"
    install_if_changed "$SRC" "$DST"
    installed=$((installed + 1))
  done
  echo "  → opencode: $installed agent(s) installed into $HOME/.config/opencode/agent"
}

install_opencode

echo ""
echo "Skills install complete."
exit 0