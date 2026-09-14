#!/bin/sh
# clone-profile.sh <new-account-name> [source-profile]
#
# Clones an existing profile directory to a new account profile so the new
# account starts with the same extensions (FoxyProxy + captcha solver) already
# installed and configured. It does NOT automate login - after cloning, launch
# Playwright MCP (or Chrome) once against the new profile and log in manually.
#
# Usage:
#   ./clone-profile.sh myaccount
#   ./clone-profile.sh myaccount SomeOtherSource

set -eu

PROFILES_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SRC_DIR="$PROFILES_DIR"

if [ "$#" -lt 1 ]; then
    echo "ERROR: usage: clone-profile.sh <new-account-name> [source-profile]" >&2
    exit 2
fi

NEW_NAME="$1"
SOURCE="${2:-Default}"

# Validate account name is a sane single path component (no slashes, no '..').
case "$NEW_NAME" in
    */*|*..*|*\\\\*|'')
        echo "ERROR: invalid account name '$NEW_NAME' (must be a single path component, no slashes)." >&2
        exit 2
        ;;
esac

DEST_DIR="$PROFILES_DIR/Profile-$NEW_NAME"
SOURCE_DIR="$PROFILES_DIR/Profile-$SOURCE"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: source profile directory '$SOURCE_DIR' does not exist." >&2
    exit 1
fi

if [ -d "$DEST_DIR" ]; then
    echo "ERROR: destination profile directory '$DEST_DIR' already exists." >&2
    exit 1
fi

echo "Cloning '$SOURCE_DIR' -> '$DEST_DIR'"
cp -a "$SOURCE_DIR" "$DEST_DIR"

# Remove runtime-only state so the clone starts fresh and doesn't fight the
# source profile over singleton locks / sockets. '-r' is a no-op if absent.
rm -rf "$DEST_DIR/SingletonLock" \
       "$DEST_DIR/SingletonCookie" \
       "$DEST_DIR/SingletonSocket" \
       "$DEST_DIR/Default/LOCK" \
       "$DEST_DIR/Default/cache" \
       "$DEST_DIR/Default/Code Cache" 2>/dev/null || :

echo "Done. Account profile created at: $DEST_DIR"
echo "Launch Playwright MCP now with this profile active (use-account.sh $NEW_NAME) and log in once manually."
