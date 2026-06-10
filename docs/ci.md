# CI workflow

File: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

Verifies that OpenGeneral's **installation and usage** work across Linux, macOS,
and Windows. Every job runs on the full matrix:

| Runner | Platform |
|---|---|
| `ubuntu-latest` | Linux x86_64 |
| `macos-14` | macOS arm64 (Apple Silicon) |
| `windows-latest` | Windows x86_64 |

`fail-fast: false`, so one platform failing does not cancel the others.

## Triggers

Runs on every `push`, and on `workflow_dispatch` (manual run). No pull-request
trigger.

## Jobs

```
unit ──> build+integration ──> installer
                          └──> service-lifecycle  (non-blocking)
```

### `unit`
Installs `.[dev]` and runs `pytest -q tests` on each OS. Platform-specific tests
are guarded: the launchd backend tests skip on Windows (they use `os.getuid()`),
and the Windows SCM backend tests skip elsewhere. The service-backend tests mock
`systemctl` / `launchctl` / `win32serviceutil`, so they assert command
construction without touching a real service manager.

### `build+integration`
Installs `.[build,dev]`, builds the binary (`packaging/build.sh` /
`packaging/build.ps1`), then runs the black-box integration suite
(`tests/integration/`) against that binary with `OPENGENERAL_BINARY` set. The
built binary is uploaded as an artifact for the downstream jobs.

The integration suite drives the binary as a subprocess from a scratch working
directory with an isolated `OPENGENERAL_HOME` and a free daemon port:
- **CLI smoke** — `--help`, `keys list`, `action-planes add/list`.
- **Daemon lifecycle** — `daemon run` in the foreground, a JSON-RPC `daemon.status`
  round-trip, and a clean `daemon.stop`. This is the OS-agnostic daemon test (no
  service manager involved), so it is reliable on headless runners.
- **Persona usage** — `personas list` and a static-key `spawn` + `talk`. These are
  marked **`xfail`**: the binary loads default personas/skills via a relative path
  and bundles no data files, so an installed binary finds none. The tests document
  that gap and will flip to passing once personas/skills are bundled.

### `installer`
Downloads the built-binary artifact and runs the installer tests offline against a
fake release (a local dir + a stubbed downloader), so no network or published
release is needed and it validates *this commit's* installer against *this
commit's* binary:
- Linux/macOS: `tests/installer/run_install_sh.sh` exercises `install.sh` via `sh`
  (catching any non-POSIX `curl | sh` breakage).
- Windows: `tests/installer/run_install.ps1` exercises `install.ps1`.

Both assert: download + checksum verify + install + run `--help`, and that a
tampered checksum is rejected.

### `service-lifecycle` (non-blocking)
`continue-on-error: true`, so its result never blocks the build. Installs the
built binary and attempts a **real** service-manager lifecycle —
`daemon install/start/status/stop/uninstall` — on each OS:
- Linux: enables a systemd user session (`loginctl enable-linger`, `XDG_RUNTIME_DIR`).
- macOS: uses the runner's launchd GUI session.
- Windows: runs against the SCM (the runner is elevated).

It passes on Linux and macOS. On Windows it currently fails at `daemon start`: a
one-file PyInstaller binary cannot host a pywin32 SCM service as wired today
(needs `PythonService.exe`). Being non-blocking, this surfaces the gap without
gating CI.

## Running the tiers locally

```bash
# Unit tests
pytest -q tests

# Build the binary, then the integration + installer suites against it
./packaging/build.sh
OPENGENERAL_BINARY="$PWD/dist/opengeneral" pytest -q tests/integration
OPENGENERAL_BINARY="$PWD/dist/opengeneral" bash tests/installer/run_install_sh.sh
```
