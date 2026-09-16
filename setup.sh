#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
HACKBOT_DIR="$HOME/.hackbot"
LOG_FILE="$HACKBOT_DIR/install.log"
CONFIG_LOCATION="$HACKBOT_DIR/config.json"

mkdir -p "$HACKBOT_DIR"
: >> "$LOG_FILE"

GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
RED=$'\033[0;31m'
NC=$'\033[0m'

SED_FLAGS=(-i)
if [[ "$(uname -s)" == "Darwin" ]]; then
  SED_FLAGS=(-i '')
fi

log() {
  local ts
  ts="$(date '+%Y-%m-%dT%H:%M:%S%z')"
  printf '[%s] %s\n' "$ts" "$*" >> "$LOG_FILE"
}

ok()  { echo "${GREEN}  ✓ $*${NC}";   log "OK:   $*"; }
warn(){ echo "${YELLOW}  ⚠ $*${NC}"; log "WARN: $*"; }
die() { echo "${RED}✗ $*${NC}" >&2;  log "FATAL: $*"; exit 1; }

check_deps() {
  local missing=()
  if (( ${BASH_VERSINFO[0]} < 4 )); then
    missing+=("bash>=4 (have ${BASH_VERSINFO[0]})")
  fi
  local d
  for d in jq curl git; do
    if ! command -v "$d" >/dev/null 2>&1; then
      missing+=("$d")
    fi
  done
  if (( ${#missing[@]} > 0 )); then
    die "Missing required dependencies: ${missing[*]}"
  fi
  ok "Dependencies satisfied (bash ${BASH_VERSINFO[0]}, jq, curl, git)"
}

gather_platform() {
  PLATFORM="opencode"
  log "Platform selection: $PLATFORM"
}

prompt_value() {
  local desc="$1" default="${2:-}" val
  if [[ -n "$default" ]]; then
    read -rp "$desc [$default]: " val
    val="${val:-$default}"
  else
    read -rp "$desc: " val
  fi
  printf '%s' "$val"
}

prompt_int() {
  local desc="$1" default="$2" val
  while :; do
    read -rp "$desc [$default]: " val
    val="${val:-$default}"
    if [[ "$val" =~ ^[0-9]+$ ]]; then
      printf '%s' "$val"
      return 0
    fi
    warn "Please enter a valid number"
  done
}

gather_config() {
  echo ""
  echo "── Configuration ──"
  CONFIG_INTIGRITI_USERNAME="$(prompt_value "Intigriti username")"
  CONFIG_EMAIL_BASE="$(prompt_value "Intigriti email (your @intigriti.me address base, e.g. aceproulx)" "${CONFIG_INTIGRITI_USERNAME:-}")"
  CONFIG_TELEGRAM_BOT_TOKEN="$(prompt_value "Telegram bot token (for notifications)")"
  CONFIG_TELEGRAM_CHAT_ID="$(prompt_value "Telegram chat ID")"
  CONFIG_BLIND_XSS_URL="$(prompt_value "Blind XSS collector URL (e.g. https://xss.report/c/username)")"
  CONFIG_CAIDO_PROXY_PORT="$(prompt_int "Caido proxy port" "8080")"
  CONFIG_CURL_PROXY_PORT="$(prompt_int "curl proxy port" "8081")"
  CONFIG_OOB_TUNNEL_URL="$(prompt_value "OOB SSRF tunnel (cloudflared URL, can set later)")"
  CONFIG_PAYLOADS_DIR="$(prompt_value "Payloads directory" "$HOME/Projects/payloads/coffinxp-payloads")"
  CONFIG_SESSIONS_DIR="$(prompt_value "Hunt sessions directory" "$HOME/Projects/hackbot/hunts/sessions")"
  CONFIG_MAX_WORKER_SLOTS="$(prompt_int "Max worker slots" "2")"
}

write_config() {
  local installed_at
  installed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  jq -n \
    --arg platform "$PLATFORM" \
    --arg intigriti_username "${CONFIG_INTIGRITI_USERNAME:-}" \
    --arg email_base "${CONFIG_EMAIL_BASE:-}" \
    --arg email_domain "intigriti.me" \
    --arg telegram_bot_token "${CONFIG_TELEGRAM_BOT_TOKEN:-}" \
    --arg telegram_chat_id "${CONFIG_TELEGRAM_CHAT_ID:-}" \
    --arg blind_xss_url "${CONFIG_BLIND_XSS_URL:-}" \
    --argjson caido_proxy_port "${CONFIG_CAIDO_PROXY_PORT:-8080}" \
    --argjson curl_proxy_port "${CONFIG_CURL_PROXY_PORT:-8081}" \
    --arg oob_tunnel_url "${CONFIG_OOB_TUNNEL_URL:-}" \
    --arg payloads_dir "${CONFIG_PAYLOADS_DIR:-$HOME/Projects/payloads/coffinxp-payloads}" \
    --arg sessions_dir "${CONFIG_SESSIONS_DIR:-$HOME/Projects/hackbot/hunts/sessions}" \
    --arg hackbot_misc_dir "$HOME/Projects/hackbot-misc" \
    --arg playwright_profile "$HOME/Projects/hackbot-misc/.agent-browser-profiles/Profile-userA" \
    --argjson max_worker_slots "${CONFIG_MAX_WORKER_SLOTS:-2}" \
    --arg installed_at "$installed_at" \
    --arg version "" \
    '{platform:$platform,
      intigriti_username:$intigriti_username,
      email_base:$email_base,
      email_domain:$email_domain,
      telegram_bot_token:$telegram_bot_token,
      telegram_chat_id:$telegram_chat_id,
      blind_xss_url:$blind_xss_url,
      caido_proxy_port:$caido_proxy_port,
      curl_proxy_port:$curl_proxy_port,
      oob_tunnel_url:$oob_tunnel_url,
      payloads_dir:$payloads_dir,
      sessions_dir:$sessions_dir,
      hackbot_misc_dir:$hackbot_misc_dir,
      playwright_profile:$playwright_profile,
      max_worker_slots:$max_worker_slots,
      installed_at:$installed_at,
      version:$version}' > "$CONFIG_LOCATION"
  ok "Config written to $CONFIG_LOCATION"
  log "Config written (platform=$PLATFORM)"
}

load_config() {
  PLATFORM="$(jq -r '.platform // "opencode"' "$CONFIG_LOCATION")"
  CONFIG_INTIGRITI_USERNAME="$(jq -r '.intigriti_username // ""' "$CONFIG_LOCATION")"
  CONFIG_EMAIL_BASE="$(jq -r '.email_base // ""' "$CONFIG_LOCATION")"
  CONFIG_TELEGRAM_BOT_TOKEN="$(jq -r '.telegram_bot_token // ""' "$CONFIG_LOCATION")"
  CONFIG_TELEGRAM_CHAT_ID="$(jq -r '.telegram_chat_id // ""' "$CONFIG_LOCATION")"
  CONFIG_BLIND_XSS_URL="$(jq -r '.blind_xss_url // ""' "$CONFIG_LOCATION")"
  CONFIG_OOB_TUNNEL_URL="$(jq -r '.oob_tunnel_url // ""' "$CONFIG_LOCATION")"
  CONFIG_PAYLOADS_DIR="$(jq -r '.payloads_dir // ""' "$CONFIG_LOCATION")"
  CONFIG_SESSIONS_DIR="$(jq -r '.sessions_dir // ""' "$CONFIG_LOCATION")"
  ok "Keeping existing config (platform=$PLATFORM)"
}

create_dirs() {
  mkdir -p "$HOME/Projects/hackbot-misc/notify"
  mkdir -p "$HOME/Projects/hackbot/hunts/sessions"
  mkdir -p "$HOME/Projects/hackbot-misc/.agent-browser-profiles"
  mkdir -p "$HOME/.agent-browser"
  mkdir -p "$HACKBOT_DIR"
  mkdir -p "$HOME/.local/bin"
  ok "Directory structure ready"
}

apply_config() {
  local FILE="$1"
  local CONFIG="$HOME/.hackbot/config.json"
  sed "${SED_FLAGS[@]}" \
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
    -e "s|{{MAX_WORKER_SLOTS}}|$(jq -r '.max_worker_slots' "$CONFIG")|g" \
    "$FILE"
}

apply_config_to_installed() {
  local dir f s
  local dirs=(
    "$HOME/.config/opencode/skill"
    "$HOME/.config/opencode/agent"
    "$HOME/Projects/hackbot-misc"
  )
  for dir in "${dirs[@]}"; do
    [[ -d "$dir" ]] || continue
    while IFS= read -r -d '' f; do
      case "$f" in
        *.sh|*.md|*.json|*.yml|*.yaml|*.txt) apply_config "$f" ;;
      esac
    done < <(find "$dir" -type f \( -name '*.sh' -o -name '*.md' -o -name '*.json' -o -name '*.yml' -o -name '*.yaml' -o -name '*.txt' \) -print0 2>/dev/null)
  done
  for s in notify-telegram.sh queue-manager.sh dashboard.sh worker-pool.sh watchdog.sh watchdog-helper.sh; do
    if [[ -f "$REPO_ROOT/scripts/$s" ]]; then
      apply_config "$REPO_ROOT/scripts/$s"
    fi
  done
  ok "Config placeholders applied to installed files"
}

install_skills_agents() {
  if [[ -f "$REPO_ROOT/scripts/install-skills.sh" ]]; then
    bash "$REPO_ROOT/scripts/install-skills.sh" --config "$CONFIG_LOCATION"
    ok "Skills + agents installed"
  else
    warn "scripts/install-skills.sh not found — skipping skills/agents"
  fi
}

install_tools() {
  if [[ -f "$REPO_ROOT/scripts/install-tools.sh" ]]; then
    bash "$REPO_ROOT/scripts/install-tools.sh"
    ok "CLI tools installed"
  else
    warn "scripts/install-tools.sh not found — skipping tools"
  fi
}

install_symlinks() {
  if compgen -G "$REPO_ROOT/scripts/*.sh" >/dev/null 2>&1; then
    chmod +x "$REPO_ROOT"/scripts/*.sh
  fi
  ln -sf "$REPO_ROOT/scripts/notify-telegram.sh" "$HOME/.local/bin/hackbot-notify"
  ln -sf "$REPO_ROOT/scripts/queue-manager.sh"    "$HOME/.local/bin/hackbot-queue"
  ln -sf "$REPO_ROOT/scripts/dashboard.sh"        "$HOME/.local/bin/hackbot-dashboard"
  ln -sf "$REPO_ROOT/scripts/worker-pool.sh"      "$HOME/.local/bin/hackbot-workers"
  ln -sf "$REPO_ROOT/scripts/watchdog.sh"         "$HOME/.local/bin/hackbot-watchdog"
  ok "CLI symlinks created in ~/.local/bin"
}

install_mcps() {
  if [[ -f "$REPO_ROOT/scripts/install-mcps.sh" ]]; then
    bash "$REPO_ROOT/scripts/install-mcps.sh"
    ok "MCPs installed"
  else
    warn "scripts/install-mcps.sh not found — skipping MCPs"
  fi
}

install_browser_profiles() {
  local PROFILES_DIR="$HOME/Projects/hackbot-misc/.agent-browser-profiles"
  local AGENT_CFG="$HOME/.agent-browser/config.json"
  mkdir -p "$PROFILES_DIR" "$HOME/.agent-browser"
  if [[ -d "$REPO_ROOT/browser-profiles" ]]; then
    cp -a "$REPO_ROOT/browser-profiles/." "$PROFILES_DIR/"
    chmod +x "$PROFILES_DIR"/*.sh 2>/dev/null || true
    # Resolve {{HACKBOT_MISC_DIR}} in the installed scripts in place (same
    # placeholder substitution install-skills.sh does for skills, mirrored here).
    sed -i -e "s|{{HACKBOT_MISC_DIR}}|$HOME/Projects/hackbot-misc|g" \
      "$PROFILES_DIR"/*.sh "$PROFILES_DIR"/README.md 2>/dev/null || true
    ok "Browser profiles installed (seed + clone/switch/sync scripts)"
  else
    warn "browser-profiles/ not found — skipping browser profiles"
  fi
  # Legacy agent-browser config (kept so switch-account.sh still works).
  # Playwright MCP ignores this — it gets the profile via --user-data-dir.
  if [[ ! -f "$AGENT_CFG" ]]; then
    local DEFAULT_PROFILE
    DEFAULT_PROFILE="$PROFILES_DIR/Profile-Default"
    jq -n --arg profile "$DEFAULT_PROFILE" \
      '{headed:true,args:"--disable-blink-features=AutomationControlled,--start-maximized",profile:$profile}' \
      > "$AGENT_CFG"
    ok "Created ~/.agent-browser/config.json -> Profile-Default"
  fi
}

validate() {
  export PATH="$HOME/.local/bin:$PATH"
  echo ""
  echo "── Validation ──"
  if hackbot-notify test "Setup complete" 2>/dev/null; then
    ok "Telegram"
  else
    warn "Telegram not configured"
  fi
  if hackbot-queue status 2>/dev/null | grep -q .; then
    ok "Queue"
  else
    warn "Queue"
  fi
  if hackbot-dashboard stats 2>/dev/null | grep -q .; then
    ok "Dashboard"
  else
    warn "Dashboard"
  fi
  if hackbot-workers status 2>/dev/null | grep -q .; then
    ok "Workers"
  else
    warn "Workers"
  fi
  echo ""
  echo "── Tools ──"
  local t
  for t in trufflehog gitleaks trivy osv-scanner jq tmux git; do
    if command -v "$t" >/dev/null 2>&1; then
      echo "  ✓ $t"
    else
      echo "  ⚠ $t (missing)"
    fi
  done
}

summary() {
  local skill_count=0 dir
  for dir in "$HOME/.config/opencode/skill"; do
    if [[ -d "$dir" ]]; then
      skill_count=$((skill_count + $(find "$dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)))
    fi
  done

  echo ""
  echo "── Summary ──"
  echo "  Platform:            $PLATFORM"
  echo "  Config file:         $CONFIG_LOCATION"
  echo "  Install log:         $LOG_FILE"
  echo "  Skills installed:    $skill_count"
  echo "  CLI scripts:         hackbot-notify, hackbot-queue, hackbot-dashboard, hackbot-workers, hackbot-watchdog"
  echo "  MCPs:                installed via scripts/install-mcps.sh"
  echo ""
  echo "  Manual steps remaining:"
  echo "    1. Caido: create an API token (Settings → API Tokens) and wire it into your environment"
  echo "    2. Browser: install Google Chrome; Playwright MCP (registered by install-mcps.sh) will drive it."
  echo "       FoxyProxy + rules ship in the seeded Profile-Default; the CAPTCHA-solver unpacked extension"
  echo "       is NOT in the repo (load it once manually via chrome://extensions → Developer mode → Load unpacked)"
  echo "    3. OOB tunnel: if you left the cloudflared URL empty, set oob_tunnel_url in $CONFIG_LOCATION later"
  echo "    4. Intigriti: confirm your account/MCP login is active so the queue can pull programs"
  echo "    5. Telegram: if token/chat ID are empty, fill $CONFIG_LOCATION and run hackbot-notify test again"
  echo "    6. PATH: ensure $HOME/.local/bin is on your PATH for the CLI scripts"
  echo ""
  ok "hackbot setup complete"
}

main() {
  local os config_ans
  os="$(uname -s)"
  log "hackbot install starting (repo=$REPO_ROOT os=$os)"
  echo "  hackbot interactive installer"
  echo "  OS: $os | repo: $REPO_ROOT"
  echo ""

  check_deps

  if [[ -f "$CONFIG_LOCATION" ]]; then
    echo ""
    read -rp "Existing config found. Update config or keep existing? (u)pdate / (k)eep [k]: " config_ans
    case "${config_ans:-k}" in
      u|U|update|Update|y|Y|yes)
        log "User chose to update config"
        gather_platform
        gather_config
        write_config
        ;;
      *)
        log "Keeping existing config"
        load_config
        ;;
    esac
  else
    gather_platform
    gather_config
    write_config
  fi

  echo ""
  create_dirs
  install_skills_agents
  install_tools
  install_symlinks
  install_mcps
  install_browser_profiles
  apply_config_to_installed
  validate
  summary
  log "hackbot setup complete"
}

main "$@"