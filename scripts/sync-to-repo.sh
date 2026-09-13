#!/usr/bin/env bash
# Usage: ./scripts/sync-to-repo.sh
# Run from the repo root (REPO AUTHOR ONLY). Copies live installed files back
# into the repo source, then de-substitutes config values back to {{PLACEHOLDERS}}.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG=~/.hackbot/config.json
[[ -f "$CONFIG" ]] || { echo "ERROR: No config found at $CONFIG" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq is required but not installed." >&2; exit 1; }

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

info() { printf "${BOLD}%s${NC}\n" "$*"; }
ok()   { printf "${GREEN}  ✓${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}  !${NC} %s\n" "$*" >&2; }

EMAIL_BASE="$(jq -r '.email_base' "$CONFIG")"
EMAIL_DOMAIN="$(jq -r '.email_domain' "$CONFIG")"
INTIGRITI_USERNAME="$(jq -r '.intigriti_username' "$CONFIG")"
BLIND_XSS_URL="$(jq -r '.blind_xss_url' "$CONFIG")"
TELEGRAM_TOKEN="$(jq -r '.telegram_bot_token' "$CONFIG")"
TELEGRAM_CHAT="$(jq -r '.telegram_chat_id' "$CONFIG")"

desubstitute() {
  local FILE="$1"
  local TMP="$FILE.tmp"

  cp "$FILE" "$TMP"

  local -a CMD=()

  # Guarded so an empty config value never yields "s||X|g" (which would
  # corrupt the file by matching every empty string).
  [[ -n "$TELEGRAM_TOKEN" ]]   && CMD+=(-e "s|${TELEGRAM_TOKEN}|{{TELEGRAM_BOT_TOKEN}}|g")
  [[ -n "$TELEGRAM_CHAT" ]]    && CMD+=(-e "s|${TELEGRAM_CHAT}|{{TELEGRAM_CHAT_ID}}|g")
  [[ -n "$BLIND_XSS_URL" ]]    && CMD+=(-e "s|${BLIND_XSS_URL}|{{BLIND_XSS_URL}}|g")
  [[ -n "$EMAIL_BASE" ]]       && CMD+=(-e "s|${EMAIL_BASE}+|{{EMAIL_BASE}}+|g")
  [[ -n "$EMAIL_BASE" ]]       && CMD+=(-e "s|${EMAIL_BASE}-|{{EMAIL_BASE}}-|g")
  [[ -n "$EMAIL_DOMAIN" ]]     && CMD+=(-e "s|@${EMAIL_DOMAIN}|@{{EMAIL_DOMAIN}}|g")
  [[ -n "$EMAIL_DOMAIN" ]]     && CMD+=(-e "s|${EMAIL_DOMAIN}|{{EMAIL_DOMAIN}}|g")
  [[ -n "$INTIGRITI_USERNAME" ]] && CMD+=(-e "s|${INTIGRITI_USERNAME}|{{INTIGRITI_USERNAME}}|g")

  if [[ ${#CMD[@]} -gt 0 ]]; then
    sed "${CMD[@]}" "$TMP" > "$FILE.new" && mv "$FILE.new" "$FILE"
  fi
  rm -f "$TMP"
}

CORE_SKILLS=(bug-hunting hunter-orchestrator notify target-queue findings-dashboard parallel-workers repo-recon)

sync_antigravity_skills() {
  local SRC_DIR="$HOME/.gemini/antigravity-cli/skills"
  local DST_DIR="$REPO_ROOT/skills/antigravity"
  mkdir -p "$DST_DIR"
  local NAME
  for NAME in "${CORE_SKILLS[@]}"; do
    local SRC="$SRC_DIR/$NAME.md" DST="$DST_DIR/$NAME.md"
    [[ -f "$SRC" ]] || { warn "skip (missing): $SRC"; continue; }
    cp "$SRC" "$DST"
    desubstitute "$DST"
    ok "synced skills/antigravity/$NAME.md"
  done
}

sync_opencode_skills() {
  local SRC_DIR="$HOME/.config/opencode/skill"
  local DST_DIR="$REPO_ROOT/skills/opencode"
  mkdir -p "$DST_DIR"
  local NAME
  for NAME in "${CORE_SKILLS[@]}"; do
    local SRC="$SRC_DIR/$NAME/SKILL.md" DST="$DST_DIR/$NAME/SKILL.md"
    [[ -f "$SRC" ]] || { warn "skip (missing): $SRC"; continue; }
    mkdir -p "$(dirname "$DST")"
    cp "$SRC" "$DST"
    desubstitute "$DST"
    ok "synced skills/opencode/$NAME/SKILL.md"
  done
}

sync_opencode_agents() {
  local SRC_DIR="$HOME/.config/opencode/agent"
  local DST_DIR="$REPO_ROOT/agents/opencode"
  mkdir -p "$DST_DIR"
  local SRC DST
  for SRC in "$SRC_DIR"/*.md; do
    [[ -f "$SRC" ]] || continue
    DST="$DST_DIR/$(basename "$SRC")"
    cp "$SRC" "$DST"
    desubstitute "$DST"
    ok "synced agents/opencode/$(basename "$SRC")"
  done
}

sync_scripts() {
  local SRC_DIR="$HOME/Projects/hackbot-misc"
  local DST_DIR="$REPO_ROOT/scripts"
  if [[ ! -d "$SRC_DIR" ]]; then
    warn "skip (missing dir): $SRC_DIR"
    return 0
  fi
  mkdir -p "$DST_DIR"
  local SRC DST
  for SRC in "$SRC_DIR"/*.sh; do
    [[ -f "$SRC" ]] || continue
    DST="$DST_DIR/$(basename "$SRC")"
    cp "$SRC" "$DST"
    desubstitute "$DST"
    ok "synced scripts/$(basename "$SRC")"
  done
}

sync_browser_profiles_scripts() {
  # Only scripts + README sync back. Profile-Default's installed copy contains
  # live session data (sessions, cookies, history), so the sanitized seed in the
  # repo is intentionally NOT overwritten from the live install.
  local SRC_DIR="$HOME/Projects/hackbot-misc/.agent-browser-profiles"
  local DST_DIR="$REPO_ROOT/browser-profiles"
  if [[ ! -d "$SRC_DIR" ]]; then
    warn "skip (missing dir): $SRC_DIR"
    return 0
  fi
  mkdir -p "$DST_DIR"
  local F
  for F in clone-profile.sh switch-account.sh sync-extensions.sh README.md; do
    if [[ -f "$SRC_DIR/$F" ]]; then
      cp "$SRC_DIR/$F" "$DST_DIR/$F"
      desubstitute "$DST_DIR/$F"
      chmod +x "$DST_DIR/$F" 2>/dev/null || true
      ok "synced browser-profiles/$F"
    fi
  done
}

info "Syncing from live install to repo..."
sync_antigravity_skills
sync_opencode_skills
sync_opencode_agents
sync_scripts
sync_browser_profiles_scripts

echo ""
info "All files synced. Review git diff before committing."