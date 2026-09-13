#!/bin/sh
# switch-account.sh <account-name>
#
# Switches the active profile used by agent-browser to
# {{HACKBOT_MISC_DIR}}/.agent-browser-profiles/Profile-<account-name>.
#
# - Validates the target profile directory exists (fails loudly otherwise).
# - Updates the "profile" field in ~/.agent-browser/config.json in place using
#   a proper JSON parser, leaving all other fields (headed/args) untouched.
# - Kills any agent-browser / Chrome process whose --user-data-dir matches the
#   OLD profile path (not a blanket kill of all Chrome).

set -eu

PROFILES_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
CONFIG="$HOME/.agent-browser/config.json"

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

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: config file '$CONFIG' not found." >&2
    exit 1
fi

# Read the current "profile" value using a real JSON parser. jq preferred,
# python3 fallback (both are true parsers, not regex parse).
if command -v jq >/dev/null 2>&1; then
    OLD_PROFILE="$(jq -r '.profile // empty' "$CONFIG")"
    HAVE_JQ=1
elif command -v python3 >/dev/null 2>&1; then
    OLD_PROFILE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("profile",""))' "$CONFIG")"
    HAVE_JQ=0
else
    echo "ERROR: need jq or python3 to parse '$CONFIG'." >&2
    exit 1
fi

# Write the new value in place (temp file + atomic mv, same parser both ways).
if [ "$HAVE_JQ" -eq 1 ]; then
    jq --arg p "$TARGET_DIR" '.profile = $p' "$CONFIG" > "$CONFIG.tmp"
    mv "$CONFIG.tmp" "$CONFIG"
else
    python3 -c '
import json, sys
conf = json.load(open(sys.argv[1]))
conf["profile"] = sys.argv[2]
with open(sys.argv[1], "w") as f:
    json.dump(conf, f, indent=2)
    f.write("\n")
' "$CONFIG" "$TARGET_DIR"
fi

# Kill Chrome processes using the OLD profile directory. Match on the
# --user-data-dir argument, which is how agent-browser hands the profile path
# to Chrome. Only processes tied to the old dir are touched.
if [ -n "$OLD_PROFILE" ] && [ "$OLD_PROFILE" != "$TARGET_DIR" ]; then
    case "$OLD_PROFILE" in
        "~/"*) OLD_EXPANDED="$HOME/${OLD_PROFILE#\~/}" ;;
        *)     OLD_EXPANDED="$OLD_PROFILE" ;;
    esac

    # Escape regex metacharacters so the path matches pgrep's -f pattern literally.
    OLD_RE=$(printf '%s' "$OLD_EXPANDED" | sed 's/[.[\*^$()+?{|]/\\&/g')

    # Build an exclude set: this script's PID plus its entire ancestor chain.
    # If this script is invoked from a shell whose command line happens to
    # contain the profile path (e.g. a wrapper that echoes the command), pgrep
    # would match that shell. We never want to kill our own process tree, so
    # walk PPIDs up to PID 1 and refuse to touch any of them. Chrome spawned by
    # agent-browser is never an ancestor, so it is unaffected.
    EXCLUDE=" $$"
    _P=$PPID
    _DEPTH=0
    while [ "$_P" -gt 1 ] && [ "$_DEPTH" -lt 32 ]; do
        EXCLUDE="$EXCLUDE $_P"
        _P=$(ps -o ppid= -p "$_P" 2>/dev/null | tr -d ' ')
        _DEPTH=$((_DEPTH + 1))
    done

    PIDS=$(pgrep -f "user-data-dir=${OLD_RE}" || true)
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
            echo "Stopping $COUNT process(es) using old profile: $OLD_EXPANDED"
            # shellcheck disable=SC2086
            kill $_FILTERED 2>/dev/null || true
            sleep 1
            # shellcheck disable=SC2086
            kill -9 $_FILTERED 2>/dev/null || true
        fi
    fi
fi

echo "Active account: $1"
echo "Profile directory: $TARGET_DIR"