#!/bin/sh
# switch-account.sh <account-name>
#
# Switches the active profile used by Playwright MCP to
# {{HACKBOT_MISC_DIR}}/.playwright-profiles/Profile-<account-name>.
#
# - Validates the target profile directory exists (fails loudly otherwise).
# - Kills any Chrome process whose --user-data-dir lives under the profiles
#   directory (not a blanket kill of all Chrome), releasing the old profile's
#   lock so a new browser can start on it.
# - Prints the --user-data-dir to relaunch your Playwright MCP server with.
#
# NOTE: Playwright MCP reads the profile only from its --user-data-dir launch
# flag — there is no config file to edit. After switching you must relaunch
# your Playwright MCP server with the printed --user-data-dir.

set -eu

PROFILES_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ "$#" -ne 1 ]; then
    echo "ERROR: usage: switch-account.sh <account-name>" >&2
    exit 2
fi

TARGET_DIR="$PROFILES_DIR/Profile-$1"

if [ ! -d "$TARGET_DIR" ]; then
    echo "ERROR: account profile directory '$TARGET_DIR' does not exist." >&2
    echo "       Create it with: $(dirname -- "$0")/clone-profile.sh <name>" >&2
    exit 1
fi

# Kill Chrome processes whose --user-data-dir lives under the profiles dir.
# Switching accounts means the old browser must die so its profile lock is
# released. Only processes tied to our profiles are touched.
PROFILES_RE=$(printf '%s' "$PROFILES_DIR" | sed 's/[.[\*^$()+?{|]/\\&/g')

# Build an exclude set: this script's PID plus its entire ancestor chain.
# If this script is invoked from a shell whose command line happens to
# contain the profile path (e.g. a wrapper that echoes the command), pgrep
# would match that shell. We never want to kill our own process tree, so
# walk PPIDs up to PID 1 and refuse to touch any of them.
EXCLUDE=" $$"
_P=$PPID
_DEPTH=0
while [ "$_P" -gt 1 ] && [ "$_DEPTH" -lt 32 ]; do
    EXCLUDE="$EXCLUDE $_P"
    _P=$(ps -o ppid= -p "$_P" 2>/dev/null | tr -d ' ')
    _DEPTH=$((_DEPTH + 1))
done

PIDS=$(pgrep -f "user-data-dir=${PROFILES_RE}" || true)
if [ -n "$PIDS" ]; then
    _FILTERED=""
    for _PID in $PIDS; do
        case "$EXCLUDE" in
            *" $_PID "*) : ;;
            *) _FILTERED="$_FILTERED $_PID" ;;
        esac
    done
    _FILTERED=${_FILTERED# }
    if [ -n "$_FILTERED" ]; then
        COUNT=$(printf '%s\n' "$_FILTERED" | grep -c '^')
        echo "Stopping $COUNT process(es) using profiles under: $PROFILES_DIR"
        # shellcheck disable=SC2086
        kill $_FILTERED 2>/dev/null || true
        sleep 1
        # shellcheck disable=SC2086
        kill -9 $_FILTERED 2>/dev/null || true
    fi
fi

echo "Active account: $1"
echo "Profile directory: $TARGET_DIR"
echo "Relaunch your Playwright MCP server with: --user-data-dir \"$TARGET_DIR\""