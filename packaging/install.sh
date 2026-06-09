#!/usr/bin/env bash
# Install the locally-built `opengeneral` binary onto the user's PATH.
#
# Builds the binary first if dist/opengeneral is missing. Copies it to
# ~/.local/bin by default (override with INSTALL_DIR=...). Pass --with-service to
# also register the daemon with the OS service manager.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
BIN_SOURCE="$REPO_ROOT/dist/opengeneral"
WITH_SERVICE=0

for arg in "$@"; do
  case "$arg" in
    --with-service) WITH_SERVICE=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ ! -x "$BIN_SOURCE" ]]; then
  echo "No binary at $BIN_SOURCE — building it first."
  "$REPO_ROOT/packaging/build.sh"
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
