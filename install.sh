#!/bin/sh
# OpenGeneral installer for Linux and macOS. POSIX sh — safe to `curl ... | sh`
# (Debian/Ubuntu /bin/sh is dash, so no bashisms here).
#
#   curl -LsSf https://raw.githubusercontent.com/opengeneral/opengeneral/main/install.sh | sh
#
# Installs the prebuilt binary to /usr/local/bin — a system location the daemon's
# low-privilege service account can execute (a user-home binary can't be). Uses sudo
# for the system steps; sudo reads its password from the terminal, so this works even
# under `curl | sh`. Flags:
#   --with-service   also register the OS service (systemd / launchd)
#   --uninstall      unregister the daemon and remove the binary
#   --version=vX.Y.Z install a specific release instead of the latest
#
# Env overrides: INSTALL_DIR, OPENGENERAL_REPO, OPENGENERAL_VERSION.
set -eu

REPO="${OPENGENERAL_REPO:-opengeneral/opengeneral}"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
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

# Root is needed to write a system dir and to manage the system service. Use sudo for
# those steps when not already root; if the install dir is user-writable (an
# INSTALL_DIR override for a CLI-only install) no sudo is used for the copy.
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if [ -w "$INSTALL_DIR" ] || { [ ! -e "$INSTALL_DIR" ] && [ -w "$(dirname "$INSTALL_DIR")" ]; }; then
    SUDO=""
  else
    SUDO="sudo"
  fi
fi

if [ "$DO_UNINSTALL" -eq 1 ]; then
  bin="$INSTALL_DIR/opengeneral"
  if [ -x "$bin" ]; then
    $SUDO "$bin" daemon uninstall || echo "Note: 'daemon uninstall' reported an issue; continuing."
    $SUDO rm -f "$bin"
    echo "Removed $bin"
  else
    echo "No opengeneral binary at $bin — nothing to remove."
  fi
  echo "The daemon's config and secrets were left intact."
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

$SUDO mkdir -p "$INSTALL_DIR"
$SUDO install -m 0755 "$tmp/opengeneral" "$INSTALL_DIR/opengeneral"
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
  $SUDO "$INSTALL_DIR/opengeneral" daemon install
  echo "Start it with: sudo opengeneral daemon start"
else
  echo
  echo "Next steps (the daemon runs as an OS service, so these need sudo):"
  echo "  sudo opengeneral daemon install"
  echo "  sudo opengeneral daemon start"
  echo "  opengeneral action-planes add default --endpoint http://127.0.0.1:4767/mcp"
  echo "  opengeneral keys add <name> --type anthropic"
fi
