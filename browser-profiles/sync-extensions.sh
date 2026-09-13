#!/bin/sh
# sync-extensions.sh [source-profile]
#
# Propagates the extension install + configuration from a "source of truth"
# profile to every other account profile under this directory.
#
# Copies the Chrome profile's Default/Extensions and
# Default/Local Extension Settings (where FoxyProxy rules and the captcha
# solver config are stored) over the corresponding folders in every other
# Profile-* directory.
#
# Use this whenever FoxyProxy rules or the captcha solver config change, so
# all account profiles stay in sync without redoing manual extension setup.
#
# Usage:
#   ./sync-extensions.sh                # source of truth is Profile-Default
#   ./sync-extensions.sh SomeProfile    # use Profile-SomeProfile as source

set -eu

PROFILES_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SOURCE="${1:-Default}"
SOURCE_DIR="$PROFILES_DIR/Profile-$SOURCE"

SOURCE_EXT="$SOURCE_DIR/Default/Extensions"
SOURCE_LES="$SOURCE_DIR/Default/Local Extension Settings"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: source profile directory '$SOURCE_DIR' does not exist." >&2
    exit 1
fi

# Only the two folders that hold extension code + persisted extension config
# (FoxyProxy rules, captcha solver settings) are synced; everything else that
# is account-specific (cookies, login state, history) is left untouched.
for WHAT in "Extensions:$SOURCE_EXT" "Local Extension Settings:$SOURCE_LES"; do
    REL="${WHAT%%:*}"
    SRC="${WHAT#*:}"
    if [ ! -d "$SRC" ]; then
        echo "ERROR: source folder '$SRC' does not exist in '$SOURCE_DIR'." >&2
        exit 1
    fi
done

UPDATED=0
for DEST in "$PROFILES_DIR"/Profile-*/; do
    [ -d "$DEST" ] || continue
    DEST=$(printf '%s' "$DEST" | sed 's:/*$::')
    case "$DEST" in
        "$PROFILES_DIR/Profile-$SOURCE") continue ;;
    esac
    if [ ! -d "$DEST/Default" ]; then
        echo "WARNING: skipping '$DEST' (no Default/ directory - not a usable Chrome profile)." >&2
        continue
    fi

    rm -rf "$DEST/Default/Extensions" "$DEST/Default/Local Extension Settings"
    cp -a "$SOURCE_EXT" "$DEST/Default/Extensions"
    cp -a "$SOURCE_LES" "$DEST/Default/Local Extension Settings"
    UPDATED=$((UPDATED + 1))
    echo "Synced extensions from '$SOURCE_DIR' -> $DEST"
done

if [ "$UPDATED" -eq 0 ]; then
    echo "No other account profiles found to sync (only source '$SOURCE' exists)." >&2
    exit 0
fi

echo "Done. $UPDATED profile(s) updated."