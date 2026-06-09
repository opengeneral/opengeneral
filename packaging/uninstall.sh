#!/usr/bin/env bash
# Remove the installed `opengeneral` binary and unregister its daemon service.
#
# Leaves user config (~/.opengeneral) and keyring secrets intact — those are the
# user's data, not install artifacts.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
TARGET="$INSTALL_DIR/opengeneral"

if [[ -x "$TARGET" ]]; then
  # Unregister the service before removing the binary it points at. If that fails,
  # keep the binary — it is the only tool that can cleanly unregister the service,
  # and deleting it would strand a unit/agent whose ExecStart no longer exists.
  if "$TARGET" daemon uninstall; then
    rm -f "$TARGET"
    echo "Removed $TARGET"
  else
    echo
    echo "Error: 'daemon uninstall' failed, so the binary was left in place."
    echo "The service may still reference it. Resolve the service issue, then re-run"
    echo "this script (or: \"$TARGET\" daemon uninstall && rm \"$TARGET\")."
    exit 1
  fi
else
  echo "No opengeneral binary at $TARGET — nothing to remove."
fi

echo
echo "Left intact:"
echo "  - config at ~/.opengeneral"
echo "  - API key secrets in the OS keyring"
echo "Remove config with:  rm -rf ~/.opengeneral"
