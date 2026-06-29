#!/usr/bin/env bash
# Offline test of the root install.sh (Linux/macOS) against a fake GitHub release.
#
# Stubs `curl` to serve a local fake-release dir, so no network and no published
# release are needed. Uses $OPENGENERAL_BINARY as the installed binary if set,
# otherwise a tiny stub. Exits non-zero on the first failed assertion.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALL_SH="$REPO_ROOT/install.sh"
SBX="$(mktemp -d)"
trap 'rm -rf "$SBX"' EXIT

pass=0
assert() { if eval "$2"; then echo "ok: $1"; pass=$((pass + 1)); else echo "FAIL: $1" >&2; exit 1; fi; }

# Compute this platform's asset name the same way install.sh does.
case "$(uname -s)" in Linux) os=linux ;; Darwin) os=macos ;; *) echo "unsupported OS" >&2; exit 2 ;; esac
case "$(uname -m)" in x86_64 | amd64) arch=x86_64 ;; arm64 | aarch64) arch=arm64 ;; *) echo "unsupported arch" >&2; exit 2 ;; esac
asset="opengeneral-${os}-${arch}"
tui_asset="opengeneral-tui-${os}-${arch}"

# Binary to "release": the real one if provided, else a stub.
srcbin="${OPENGENERAL_BINARY:-}"
if [[ -z "$srcbin" || ! -x "$srcbin" ]]; then
  srcbin="$SBX/stub"
  cat > "$srcbin" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in --help) echo "opengeneral: spawn daemon keys" ;; daemon) echo "daemon ${2:-}" ;; *) echo "stub $*" ;; esac
exit 0
EOF
  chmod +x "$srcbin"
fi

# Fake release dir + checksums. The TUI ships alongside the main binary; the same
# stand-in binary serves for both (we test install logic, not their runtime).
REL="$SBX/release"; mkdir -p "$REL"
cp "$srcbin" "$REL/$asset"
cp "$srcbin" "$REL/$tui_asset"
gensums() {
  ( cd "$REL" && { command -v sha256sum >/dev/null 2>&1 \
      && sha256sum "$asset" "$tui_asset" \
      || shasum -a 256 "$asset" "$tui_asset"; } > SHA256SUMS )
}
gensums

# Stub curl that serves files from the fake release dir by basename.
STUB="$SBX/stubbin"; mkdir -p "$STUB"
cat > "$STUB/curl" <<EOF
#!/usr/bin/env bash
out=""; url=""
while [[ \$# -gt 0 ]]; do case "\$1" in -o) out="\$2"; shift 2;; -*) shift;; *) url="\$1"; shift;; esac; done
src="$REL/\$(basename "\$url")"
[[ -f "\$src" ]] || { echo "curl: 404 \$url" >&2; exit 22; }
cp "\$src" "\$out"
EOF
chmod +x "$STUB/curl"

BIN="$SBX/bin"
export PATH="$STUB:$PATH"
export INSTALL_DIR="$BIN"
export XDG_CONFIG_HOME="$SBX/xdg"
export OPENGENERAL_HOME="$SBX/home"

echo "== install =="
sh "$INSTALL_SH"
assert "binary installed" "[[ -x '$BIN/opengeneral' ]]"
assert "tui installed" "[[ -x '$BIN/opengeneral-tui' ]]"
assert "installed binary runs --help" "'$BIN/opengeneral' --help >/dev/null 2>&1"

echo "== checksum mismatch is rejected =="
echo "deadbeef  $asset" > "$REL/SHA256SUMS"
rm -f "$BIN/opengeneral"
set +e
sh "$INSTALL_SH" >/dev/null 2>&1
rc=$?
set -e
assert "tampered checksum -> non-zero exit" "[[ $rc -ne 0 ]]"
assert "no binary installed on checksum failure" "[[ ! -e '$BIN/opengeneral' ]]"

echo "== reinstall then uninstall =="
gensums
sh "$INSTALL_SH" >/dev/null
assert "reinstalled" "[[ -x '$BIN/opengeneral' ]]"
sh "$INSTALL_SH" --uninstall >/dev/null 2>&1
assert "uninstall removed the binary" "[[ ! -e '$BIN/opengeneral' ]]"
assert "uninstall removed the tui" "[[ ! -e '$BIN/opengeneral-tui' ]]"

echo "All $pass installer checks passed."
