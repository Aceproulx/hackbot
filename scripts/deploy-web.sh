#!/usr/bin/env bash
set -euo pipefail

# Deploy dashboard-web.py from repo → installed location with real paths
# substituted ({{PLACEHOLDERS}} from ~/.hackbot/config.json). Always use this
# instead of a bare `cp` — the repo copy is scrubbed and won't resolve paths.
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

sed -e "s|{{HACKBOT_MISC_DIR}}|$MISC|g" \
    -e "s|{{PAYLOADS_DIR}}|$PAYLOADS|g" \
    -e "s|{{EMAIL_DOMAIN}}|$EMAIL_DOMAIN|g" \
    -e "s|{{INTIGRITI_USERNAME}}|$INTIGRITI_USERNAME|g" \
    -e "s|{{BLIND_XSS_URL}}|$BLIND_XSS_URL|g" \
    "$HERE/dashboard-web.py" > "$DEST/dashboard-web.py"

echo "deployed → $DEST/dashboard-web.py"
grep -c "{{" "$DEST/dashboard-web.py" || true