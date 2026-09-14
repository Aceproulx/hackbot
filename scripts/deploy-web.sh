#!/usr/bin/env bash
set -euo pipefail

# Deploy the hackbot web dashboard from repo → installed location with real
# paths substituted ({{PLACEHOLDERS}} from ~/.hackbot/config.json). Always use
# this instead of a bare `cp` — the repo copy is scrubbed and won't resolve
# paths. Deploys both the dashboard-web.py shim and the dashboard/ package.
#
# Usage: scripts/deploy-web.sh [install_dir]
#   install_dir defaults to ~/Projects/hackbot-misc (from config).

HERE="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$HOME/.hackbot/config.json"
[ -f "$CONFIG" ] || { echo "ERROR: missing $CONFIG" >&2; exit 1; }

MISC="$(jq -r '.hackbot_misc_dir' "$CONFIG")"
PAYLOADS="$(jq -r '.payloads_dir' "$CONFIG")"
EMAIL_DOMAIN="$(jq -r '.email_domain' "$CONFIG")"
INTIGRITI_USERNAME="$(jq -r '.intigriti_username' "$CONFIG")"
BLIND_XSS_URL="$(jq -r '.blind_xss_url // ""' "$CONFIG")"

DEST="${1:-${MISC}}"
[ -d "$DEST" ] || mkdir -p "$DEST"
mkdir -p "$DEST/dashboard"

SUB="-e s|{{HACKBOT_MISC_DIR}}|$MISC|g \
     -e s|{{PAYLOADS_DIR}}|$PAYLOADS|g \
     -e s|{{EMAIL_DOMAIN}}|$EMAIL_DOMAIN|g \
     -e s|{{INTIGRITI_USERNAME}}|$INTIGRITI_USERNAME|g \
     -e s|{{BLIND_XSS_URL}}|$BLIND_XSS_URL|g"

# shim (no placeholders, but kept for a single deploy path)
cp "$HERE/dashboard-web.py" "$DEST/dashboard-web.py"

# package modules — one sed pass per file (sed can't s/// across the {{}} set)
for f in "$HERE"/dashboard/*.py; do
  sed $SUB "$f" > "$DEST/dashboard/$(basename "$f")"
done

# __pycache__ cleanup so stale bytecode never shadows new source
rm -rf "$DEST/dashboard/__pycache__" "$DEST/__pycache__"

echo "deployed → $DEST/dashboard-web.py + $DEST/dashboard/ ($(ls "$HERE"/dashboard/*.py | wc -l) modules)"
REMAINING=$(grep -l "{{" "$DEST/dashboard"/*.py "$DEST/dashboard-web.py" 2>/dev/null || true)
if [ -n "$REMAINING" ]; then
  echo "NOTICE: remaining placeholders in: $REMAINING" >&2
fi