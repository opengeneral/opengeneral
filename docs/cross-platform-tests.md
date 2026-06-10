# cross-platform-tests workflow

File: [`.github/workflows/cross-platform-tests.yml`](../.github/workflows/cross-platform-tests.yml)

Verifies that OpenGeneral's **installation and usage** work across Linux, macOS,
and Windows, and publishes an **Allure report with run-over-run history** to
GitHub Pages. Every test job runs on the full matrix:

| Runner | Platform |
|---|---|
| `ubuntu-latest` | Linux x86_64 |
| `macos-14` | macOS arm64 (Apple Silicon) |
| `windows-latest` | Windows x86_64 |

`fail-fast: false`, so one platform failing does not cancel the others.

## Triggers

Runs only on:

- **`workflow_dispatch`** — a manual run from the Actions tab.
- **A `v*` tag push** — so the full matrix verifies a release-worthy commit.

It deliberately does **not** run on every push: the 3-OS build matrix is
expensive, and doc/config-only changes shouldn't trigger it.

## Jobs

```
unit ──> build ──> service-lifecycle  (non-blocking)
   └────────┴────> report             (Allure -> GitHub Pages, always runs)
```

### `unit`
Installs `.[dev]` and runs the unit tests (excluding `tests/integration` and
`tests/installer`, which need the built binary). Platform-specific tests are
guarded: launchd backend tests skip on Windows; the Windows SCM backend tests skip
elsewhere. Service-backend tests mock `systemctl`/`launchctl`/`win32serviceutil`.

### `build`
Installs `.[build,dev]`, builds the binary (`packaging/build.sh` /
`packaging/build.ps1`), then runs the binary-dependent suites against it with
`OPENGENERAL_BINARY` set:
- **Integration** (`tests/integration/`) — drives the binary from a scratch dir
  with an isolated `OPENGENERAL_HOME`/port: CLI smoke, a real `daemon run` +
  JSON-RPC round-trip + clean stop, and persona/spawn usage (`xfail`, documenting
  that the binary bundles no default personas/skills yet).
- **Installer** (`tests/installer/`) — `test_install_script.py` runs `install.sh`
  (Unix) / `install.ps1` (Windows) against a fake release: download + checksum
  verify + install + uninstall, with mismatch rejection.

### `service-lifecycle` (non-blocking)
`continue-on-error: true`. Builds the binary and attempts a **real**
`daemon install/start/status/stop/uninstall` per OS (systemd user session on
Linux, launchd on macOS, SCM on Windows). Passes on Linux/macOS; on Windows it
currently fails at `daemon start` (a one-file PyInstaller binary can't host a
pywin32 SCM service as wired today). Being non-blocking, it reports the gap
without gating the workflow.

### `report` (Allure -> GitHub Pages)
`if: always()`, so it reports even when tests fail. Each test job emits Allure
results (`allure-pytest`, tagged with an `os` parameter so history is tracked per
platform) and uploads them as artifacts. This job:
1. downloads every job's `allure-results-*`,
2. restores the previous report's `history/` from the `gh-pages` branch (trends),
3. runs `allure generate`,
4. deploys the HTML report to GitHub Pages.

The result is a browsable report at the repo's GitHub Pages URL that accumulates
pass/fail/flaky history across runs.

## Running the tiers locally

```bash
# Unit
pytest tests --ignore=tests/integration --ignore=tests/installer

# Build, then the binary-dependent suites
./packaging/build.sh
OPENGENERAL_BINARY="$PWD/dist/opengeneral" pytest tests/integration tests/installer

# Emit Allure results (then `allure serve allure-results` to view locally)
pytest tests --alluredir=allure-results
```
