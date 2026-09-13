#!/usr/bin/env bash
# update.sh — Non-interactive updater for existing hackbot installs.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
CONFIG=~/.hackbot/config.json

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

info() { printf "${BOLD}%s${NC}\n" "$*"; }
ok()   { printf "${GREEN}  ✓${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}  !${NC} %s\n" "$*" >&2; }
die()  { printf "${RED}  ✗${NC} %s\n" "$*" >&2; exit 1; }

info "Updating hackbot..."
cd "$REPO_ROOT"

if ! git pull origin main; then
  die "git pull failed. Resolve any conflicts or fix your network, then re-run ./update.sh."
fi
ok "Pulled latest changes"

[[ -f "$CONFIG" ]] || die "No config found at $CONFIG. Run ./setup.sh first."
ok "Config found: $CONFIG"

PLATFORM="$(jq -r '.platform // empty' "$CONFIG")"
[[ -n "$PLATFORM" ]] || die "Config is missing the 'platform' field (antigravity|opencode|both)."
if [[ "$PLATFORM" != "antigravity" && "$PLATFORM" != "opencode" && "$PLATFORM" != "both" ]]; then
  die "Config 'platform' must be antigravity, opencode, or both (got '$PLATFORM')."
fi
info "Platform: $PLATFORM"

echo ""
info "[1/3] Installing skills & agents"
bash "$REPO_ROOT/scripts/install-skills.sh" --platform "$PLATFORM" --config "$CONFIG" --no-prompt
ok "Skills & agents up to date"

echo ""
info "[2/3] Checking tools"
bash "$REPO_ROOT/scripts/install-tools.sh" --check-only
ok "Tool check complete"

echo ""
info "[3/3] Updating MCP servers"
bash "$REPO_ROOT/scripts/install-mcps.sh" --update
ok "MCP servers updated"

echo ""
echo "==============================================="
printf "${GREEN}${BOLD}  Update complete${NC}\n"
echo "==============================================="
info "Run 'hackbot-workers status' to verify the install."