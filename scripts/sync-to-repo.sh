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
OOB_TUNNEL_URL="$(jq -r '.oob_tunnel_url' "$CONFIG")"
PAYLOADS_DIR="$(jq -r '.payloads_dir' "$CONFIG")"
SESSIONS_DIR="$(jq -r '.sessions_dir' "$CONFIG")"
HACKBOT_MISC_DIR="$(jq -r '.hackbot_misc_dir' "$CONFIG")"

# Dir values may appear in live files as absolute ($HOME/...) or tilde (~/...)
# forms depending on which setup version wrote them. Derive both so scrub-back
# always converts to a single {{PLACEHOLDER}}. Empty/unset → empty tilde.
tilde_form() {
  local v="$1"
  if [[ -z "$v" ]]; then printf ''; return; fi
  printf '~/%s' "${v#"$HOME"/}"
}
PAYLOADS_DIR_TILDE="$(tilde_form "$PAYLOADS_DIR")"
SESSIONS_DIR_TILDE="$(tilde_form "$SESSIONS_DIR")"
HACKBOT_MISC_DIR_TILDE="$(tilde_form "$HACKBOT_MISC_DIR")"

desubstitute() {
  local FILE="$1"
  local TMP="$FILE.tmp"

  cp "$FILE" "$TMP"

  local -a CMD=()

  # Guarded so an empty config value never yields "s||X|g" (which would
  # corrupt the file by matching every empty string).
  [[ -n "$TELEGRAM_TOKEN" ]]   && CMD+=(-e "s|${TELEGRAM_TOKEN}|{{TELEGRAM_BOT_TOKEN}}|g")
  [[ -n "$TELEGRAM_CHAT" ]]    && CMD+=(-e "s|${TELEGRAM_CHAT}|{{TELEGRAM_CHAT_ID}}|g")
  # Blind XSS URL can appear in three forms in live files (with scheme,
  # protocol-relative, or bare host/path). NOSCHEME is derived from the
  # configured URL so all three scrub down to a single {{BLIND_XSS_URL}}.
  if [[ -n "$BLIND_XSS_URL" ]]; then
    local NOSCHEME="${BLIND_XSS_URL#*://}"
    CMD+=(-e "s|${BLIND_XSS_URL}|{{BLIND_XSS_URL}}|g")
    CMD+=(-e "s|//${NOSCHEME}|{{BLIND_XSS_URL}}|g")
    CMD+=(-e "s|${NOSCHEME}|{{BLIND_XSS_URL}}|g")
  fi
  [[ -n "$EMAIL_BASE" ]]       && CMD+=(-e "s|${EMAIL_BASE}+|{{EMAIL_BASE}}+|g")
  [[ -n "$EMAIL_BASE" ]]       && CMD+=(-e "s|${EMAIL_BASE}-|{{EMAIL_BASE}}-|g")
  [[ -n "$EMAIL_DOMAIN" ]]     && CMD+=(-e "s|@${EMAIL_DOMAIN}|@{{EMAIL_DOMAIN}}|g")
  [[ -n "$EMAIL_DOMAIN" ]]     && CMD+=(-e "s|${EMAIL_DOMAIN}|{{EMAIL_DOMAIN}}|g")
  [[ -n "$INTIGRITI_USERNAME" ]] && CMD+=(-e "s|${INTIGRITI_USERNAME}|{{INTIGRITI_USERNAME}}|g")
  [[ -n "$OOB_TUNNEL_URL" ]]   && CMD+=(-e "s|${OOB_TUNNEL_URL}|{{OOB_TUNNEL_URL}}|g")
  [[ -n "$PAYLOADS_DIR" ]]     && CMD+=(-e "s|${PAYLOADS_DIR}|{{PAYLOADS_DIR}}|g")
  [[ -n "$PAYLOADS_DIR_TILDE" ]] && CMD+=(-e "s|${PAYLOADS_DIR_TILDE}|{{PAYLOADS_DIR}}|g")
  [[ -n "$SESSIONS_DIR" ]]     && CMD+=(-e "s|${SESSIONS_DIR}|{{SESSIONS_DIR}}|g")
  [[ -n "$SESSIONS_DIR_TILDE" ]] && CMD+=(-e "s|${SESSIONS_DIR_TILDE}|{{SESSIONS_DIR}}|g")
  [[ -n "$HACKBOT_MISC_DIR" ]] && CMD+=(-e "s|${HACKBOT_MISC_DIR}|{{HACKBOT_MISC_DIR}}|g")
  [[ -n "$HACKBOT_MISC_DIR_TILDE" ]] && CMD+=(-e "s|${HACKBOT_MISC_DIR_TILDE}|{{HACKBOT_MISC_DIR}}|g")

  if [[ ${#CMD[@]} -gt 0 ]]; then
    sed "${CMD[@]}" "$TMP" > "$FILE.new" && mv "$FILE.new" "$FILE"
  fi
  rm -f "$TMP"
}

sync_opencode_skills() {
  local SRC_DIR="$HOME/.config/opencode/skill"
  local DST_DIR="$REPO_ROOT/skills/opencode"
  mkdir -p "$DST_DIR"

  # Discover all skill directories from source — no hardcoded list needed.
  # A skill dir is any directory containing a SKILL.md file.
  local SKILL_DIR NAME SRC DST FILE REL
  for SKILL_DIR in "$SRC_DIR"/*/; do
    [[ -d "$SKILL_DIR" ]] || continue
    NAME="$(basename "$SKILL_DIR")"
    SRC="$SKILL_DIR/SKILL.md"
    DST="$DST_DIR/$NAME/SKILL.md"
    [[ -f "$SRC" ]] || { warn "skip (no SKILL.md): $SKILL_DIR"; continue; }
    mkdir -p "$(dirname "$DST")"
    cp "$SRC" "$DST"
    desubstitute "$DST"
    ok "synced skills/opencode/$NAME/SKILL.md"

    # Sync supporting files (reference/, scripts/, ...) back too.
    while IFS= read -r -d '' FILE; do
      REL="${FILE#"$SKILL_DIR"}"
      DST="$DST_DIR/$NAME/$REL"
      mkdir -p "$(dirname "$DST")"
      cp "$FILE" "$DST"
      desubstitute "$DST"
      ok "synced skills/opencode/$NAME/$REL"
    done < <(find "$SKILL_DIR" -type f ! -name 'SKILL.md' -print0)
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
    chmod +x "$DST"
    ok "synced scripts/$(basename "$SRC")"
  done
  for SRC in "$SRC_DIR"/*.py; do
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
  local SRC_DIR="$HOME/Projects/hackbot-misc/.playwright-profiles"
  local DST_DIR="$REPO_ROOT/browser-profiles"
  if [[ ! -d "$SRC_DIR" ]]; then
    warn "skip (missing dir): $SRC_DIR"
    return 0
  fi
  mkdir -p "$DST_DIR"

  # Sync ALL .sh scripts (glob — new scripts are picked up automatically)
  local SRC DST
  for SRC in "$SRC_DIR"/*.sh; do
    [[ -f "$SRC" ]] || continue
    DST="$DST_DIR/$(basename "$SRC")"
    cp "$SRC" "$DST"
    desubstitute "$DST"
    chmod +x "$DST"
    ok "synced browser-profiles/$(basename "$SRC")"
  done

  # Sync README separately
  if [[ -f "$SRC_DIR/README.md" ]]; then
    cp "$SRC_DIR/README.md" "$DST_DIR/README.md"
    desubstitute "$DST_DIR/README.md"
    ok "synced browser-profiles/README.md"
  fi
}

info "Syncing from live install to repo..."
sync_opencode_skills
sync_opencode_agents
sync_scripts
sync_browser_profiles_scripts

echo ""
info "All files synced. Review git diff before committing."