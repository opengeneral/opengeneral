#!/bin/sh
# OpenGeneral installer for Linux and macOS. POSIX sh — safe to `curl ... | sh`
# (Debian/Ubuntu /bin/sh is dash, so no bashisms here).
#
#   curl -LsSf https://raw.githubusercontent.com/opengeneral/opengeneral/main/install.sh | sh
#
# Downloads the matching prebuilt binary from the latest GitHub Release, verifies
# its checksum, and installs it to ~/.local/bin. Flags:
#   --with-service   also run `opengeneral daemon install`
#   --uninstall      remove the installed binary (and unregister the daemon)
#   --version=vX.Y.Z install a specific release instead of the latest
#
# Env overrides: INSTALL_DIR, OPENGENERAL_REPO, OPENGENERAL_VERSION.
set -eu

REPO="${OPENGENERAL_REPO:-opengeneral/opengeneral}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
VERSION="${OPENGENERAL_VERSION:-latest}"
WITH_SERVICE=0
DO_UNINSTALL=0

for arg in "$@"; do
  case "$arg" in
    --with-service) WITH_SERVICE=1 ;;
    --uninstall) DO_UNINSTALL=1 ;;
    --version=*) VERSION="${arg#*=}" ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [ "$DO_UNINSTALL" -eq 1 ]; then
  bin="$INSTALL_DIR/opengeneral"
  if [ -x "$bin" ]; then
    "$bin" daemon uninstall || echo "Note: 'daemon uninstall' reported an issue; continuing."
    rm -f "$bin"
    echo "Removed $bin"
  else
    echo "No opengeneral binary at $bin — nothing to remove."
  fi
  echo "Config at ~/.opengeneral and keyring secrets were left intact."
  exit 0
fi

os="$(uname -s)"
arch="$(uname -m)"
case "$os" in
  Linux) os_name=linux ;;
  Darwin) os_name=macos ;;
  *) echo "Unsupported OS: $os. Build from source: https://github.com/$REPO" >&2; exit 1 ;;
esac
case "$arch" in
  x86_64 | amd64) arch_name=x86_64 ;;
  arm64 | aarch64) arch_name=arm64 ;;
  *) echo "Unsupported architecture: $arch" >&2; exit 1 ;;
esac
target="${os_name}-${arch_name}"

# Only linux-x86_64 and macos-arm64 are published. Intel macOS has no prebuilt
# binary (Rosetta runs Intel binaries on Apple Silicon, not arm64 on Intel).
case "$target" in
  linux-x86_64 | macos-arm64) ;;
  macos-x86_64)
    echo "No prebuilt binary for Intel macOS — build from source:" >&2
    echo "  git clone https://github.com/$REPO && cd opengeneral" >&2
    echo "  pip install -e '.[build]' && ./packaging/build.sh" >&2
    exit 1 ;;
  *)
    echo "No prebuilt binary for $target — build from source: https://github.com/$REPO" >&2
    exit 1 ;;
esac

asset="opengeneral-${target}"
if [ "$VERSION" = "latest" ]; then
  base="https://github.com/$REPO/releases/latest/download"
else
  base="https://github.com/$REPO/releases/download/$VERSION"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Downloading $asset ($VERSION) ..."
curl -fsSL "$base/$asset" -o "$tmp/opengeneral"
curl -fsSL "$base/SHA256SUMS" -o "$tmp/SHA256SUMS"

expected="$(awk -v a="$asset" '$2 == a {print $1}' "$tmp/SHA256SUMS")"
if [ -z "$expected" ]; then
  echo "Checksum for $asset not found in SHA256SUMS." >&2
  exit 1
fi
if command -v sha256sum >/dev/null 2>&1; then
  actual="$(sha256sum "$tmp/opengeneral" | awk '{print $1}')"
else
  actual="$(shasum -a 256 "$tmp/opengeneral" | awk '{print $1}')"
fi
if [ "$actual" != "$expected" ]; then
  echo "Checksum mismatch for $asset:" >&2
  echo "  expected: $expected" >&2
  echo "  actual:   $actual" >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR"
install -m 0755 "$tmp/opengeneral" "$INSTALL_DIR/opengeneral"
echo "Installed opengeneral to $INSTALL_DIR/opengeneral"

case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *)
    echo
    echo "Warning: $INSTALL_DIR is not on your PATH."
    echo "Add it to your shell profile:  export PATH=\"$INSTALL_DIR:\$PATH\""
    ;;
esac

if [ "$WITH_SERVICE" -eq 1 ]; then
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
