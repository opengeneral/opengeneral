#!/usr/bin/env bash
# Install the `opengeneral` binary onto the user's PATH.
#
# Works both from a release download (the binary ships next to this script) and
# from a source checkout (builds dist/opengeneral if needed). Copies the binary to
# ~/.local/bin by default (override with INSTALL_DIR=...). Pass --with-service to
# also register the daemon with the OS service manager.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
WITH_SERVICE=0

for arg in "$@"; do
  case "$arg" in
    --with-service) WITH_SERVICE=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Locate the binary to install:
#   1. one shipped alongside this script (release download/archive)
#   2. the repo build output, building it if this is a source checkout
BIN_SOURCE=""
for cand in "$SCRIPT_DIR/opengeneral" "$SCRIPT_DIR"/opengeneral-*; do
  if [[ -f "$cand" && "$cand" != *.sh && "$cand" != *.ps1 ]]; then
    BIN_SOURCE="$cand"
    break
  fi
done
if [[ -z "$BIN_SOURCE" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  BIN_SOURCE="$REPO_ROOT/dist/opengeneral"
  if [[ ! -x "$BIN_SOURCE" ]]; then
    if [[ -x "$REPO_ROOT/packaging/build.sh" ]]; then
      echo "No binary found — building from source."
      "$REPO_ROOT/packaging/build.sh"
    else
      echo "No opengeneral binary found next to this script or at $BIN_SOURCE." >&2
      exit 1
    fi
  fi
fi

mkdir -p "$INSTALL_DIR"
install -m 0755 "$BIN_SOURCE" "$INSTALL_DIR/opengeneral"
echo "Installed opengeneral to $INSTALL_DIR/opengeneral"

case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *)
    echo
    echo "Warning: $INSTALL_DIR is not on your PATH."
    echo "Add it to your shell profile:  export PATH=\"$INSTALL_DIR:\$PATH\""
    ;;
esac

if [[ "$WITH_SERVICE" -eq 1 ]]; then
  echo
  echo "Registering the daemon service ..."
  "$INSTALL_DIR/opengeneral" daemon install
else
  echo
  echo "Next steps:"
  echo "  opengeneral keys add <name> --type anthropic"
  echo "  opengeneral action-planes add default --endpoint http://127.0.0.1:4767/mcp"
  echo "  opengeneral daemon install && opengeneral daemon start"
fi
