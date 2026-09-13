#!/usr/bin/env bash
# install-tools.sh — Ensures required security/CLI tools are installed.
#
# Usage: install-tools.sh [--check-only]
#   --check-only   only report which tools are missing, never install anything.
set -euo pipefail

CHECK_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only) CHECK_ONLY=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--check-only]"
      exit 0 ;;
    *) echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
  esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

info() { printf "${BOLD}%s${NC}\n" "$*"; }
ok()   { printf "${GREEN}  ✓${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}  !${NC} %s\n" "$*"; }

OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Linux|Darwin) ;;
  *) echo "ERROR: Unsupported OS: $OS" >&2; exit 1 ;;
esac

case "$ARCH" in
  x86_64|amd64)  CPU_ARCH="x86_64" ;;
  aarch64|arm64) CPU_ARCH="arm64" ;;
  *) echo "ERROR: Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

DEST_DIR="$HOME/.local/bin"
mkdir -p "$DEST_DIR"

gh_asset_pattern() {
  case "${1}:${2}:${3}" in
    trufflehog:Linux:x86_64)   echo 'trufflehog_.*_linux_amd64\.tar\.gz$' ;;
    trufflehog:Linux:arm64)    echo 'trufflehog_.*_linux_arm64\.tar\.gz$' ;;
    trufflehog:Darwin:x86_64)  echo 'trufflehog_.*_darwin_amd64\.tar\.gz$' ;;
    trufflehog:Darwin:arm64)   echo 'trufflehog_.*_darwin_arm64\.tar\.gz$' ;;
    trivy:Linux:x86_64)        echo 'trivy_.*_Linux-64bit\.tar\.gz$' ;;
    trivy:Linux:arm64)         echo 'trivy_.*_Linux-ARM64\.tar\.gz$' ;;
    trivy:Darwin:x86_64)       echo 'trivy_.*_macOS-64bit\.tar\.gz$' ;;
    trivy:Darwin:arm64)        echo 'trivy_.*_macOS-ARM64\.tar\.gz$' ;;
    gitleaks:Linux:x86_64)     echo 'gitleaks_.*_linux_x64\.tar\.gz$' ;;
    gitleaks:Linux:arm64)      echo 'gitleaks_.*_linux_arm64\.tar\.gz$' ;;
    gitleaks:Darwin:x86_64)    echo 'gitleaks_.*_darwin_x64\.tar\.gz$' ;;
    gitleaks:Darwin:arm64)     echo 'gitleaks_.*_darwin_arm64\.tar\.gz$' ;;
    osv-scanner:Linux:x86_64)  echo 'osv-scanner_.*_linux_amd64$' ;;
    osv-scanner:Linux:arm64)   echo 'osv-scanner_.*_linux_arm64$' ;;
    osv-scanner:Darwin:x86_64) echo 'osv-scanner_.*_darwin_amd64$' ;;
    osv-scanner:Darwin:arm64)  echo 'osv-scanner_.*_darwin_arm64$' ;;
    *) return 1 ;;
  esac
}

install_gh_tool() {
  local BIN="$1" REPO="$2"
  local DEST="$DEST_DIR/$BIN"

  if [[ -x "$DEST" ]]; then
    ok "$BIN (installed: $DEST)"
    return 0
  fi
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    warn "$BIN (missing — run without --check-only to install)"
    return 0
  fi

  local PATTERN
  PATTERN="$(gh_asset_pattern "$BIN" "$OS" "$CPU_ARCH")" || {
    warn "$BIN: no release asset matches $OS/$CPU_ARCH — install manually"
    return 0
  }

  local TMPDIR REL_JSON TAG ASSET
  TMPDIR="$(mktemp -d)"
  REL_JSON="$TMPDIR/release.json"

  if ! curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" -o "$REL_JSON"; then
    warn "$BIN: failed to fetch latest release from $REPO"
    rm -rf "$TMPDIR"
    return 0
  fi

  TAG="$(jq -r '.tag_name // empty' "$REL_JSON")"
  ASSET="$(jq -r --arg re "$PATTERN" '.assets[].name | select(test($re))' "$REL_JSON" | head -n1)"
  if [[ -z "$TAG" || -z "$ASSET" ]]; then
    warn "$BIN: could not determine release asset for $OS/$CPU_ARCH"
    rm -rf "$TMPDIR"
    return 0
  fi

  echo "  → downloading $BIN $TAG ($ASSET)"
  local URL="https://github.com/$REPO/releases/download/$TAG/$ASSET"
  if ! curl -fsSL "$URL" -o "$TMPDIR/$ASSET"; then
    warn "$BIN: download failed from $URL"
    rm -rf "$TMPDIR"
    return 0
  fi

  case "$ASSET" in
    *.tar.gz|*.tgz) tar -xzf "$TMPDIR/$ASSET" -C "$TMPDIR" ;;
    *.zip) (cd "$TMPDIR" && unzip -q "$ASSET") ;;
    *.gz)  gunzip -c "$TMPDIR/$ASSET" > "$TMPDIR/$BIN" ;;
    *)     cp "$TMPDIR/$ASSET" "$TMPDIR/$BIN" ;;
  esac

  local FOUND
  FOUND="$(find "$TMPDIR" -maxdepth 2 -type f -name "$BIN" | head -n1)"
  if [[ -z "$FOUND" ]]; then
    warn "$BIN: binary '$BIN' not found inside archive — install manually"
    rm -rf "$TMPDIR"
    return 0
  fi

  install -m 0755 "$FOUND" "$DEST"
  rm -rf "$TMPDIR"
  ok "$BIN installed ($DEST)"
}

check_basic() {
  local BIN="$1" PKG="$2"
  if command -v "$BIN" >/dev/null 2>&1; then
    ok "$BIN"
    return 0
  fi
  warn "$BIN (missing — install: $PKG)"
}

info "Detected: $OS / $CPU_ARCH"
echo ""

info "Installed tools"
install_gh_tool trufflehog trufflesecurity/trufflehog
install_gh_tool trivy       aquasecurity/trivy
install_gh_tool gitleaks    gitleaks/gitleaks
install_gh_tool osv-scanner google/osv-scanner

echo ""
info "GitHub CLI"
if command -v gh >/dev/null 2>&1; then
  ok "gh"
else
  warn "gh (missing)"
  if [[ "$OS" == "Linux" ]]; then
    info "    Install: curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && sudo apt install gh"
  elif [[ "$OS" == "Darwin" ]]; then
    info "    Install: brew install gh"
  fi
fi

echo ""
info "Required base tools"
check_basic jq    "apt install jq (Linux) / brew install jq (macOS)"
check_basic tmux  "apt install tmux / brew install tmux"
if [[ "$OS" == "Darwin" ]]; then
  check_basic flock "brew install util-linux"
else
  check_basic flock "apt install -y util-linux"
fi
check_basic curl  "apt install curl / brew install curl"
check_basic git   "apt install git / brew install git"

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  echo ""
  echo "Check complete. Run ./scripts/install-tools.sh to install missing tools."
else
  echo ""
  echo "Tool install complete."
fi