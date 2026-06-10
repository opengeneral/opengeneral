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
results (`allure-pytest`). The conftest in `tests/` labels every test on two axes:
the **Behaviors** tab groups by product domain (Epic) / component (Feature) — what
is tested — and the **Suites** tab groups by tier (Unit / Binary usage /
Installer) / component — how it runs. Tests are also tagged by tier and OS, with
the OS recorded as a parameter so history is tracked per platform. This job:
1. downloads every job's `allure-results-*`,
2. seeds `history/` from the latest archived run (trend continuity),
3. writes `environment.properties` + `executor.json` so the report shows the
   commit / ref / trigger and links to the GitHub run,
4. runs `allure generate`,
5. runs `scripts/allure_runs_index.py` to **archive this run's report under
   `runs/<run-number>/`, render a root `index.html` table of all runs, and prune**
   (keep every `v*` release run + the last 10 dispatch runs),
6. deploys the site to GitHub Pages (full replace, so pruned runs drop off).

The GitHub Pages root is a **table of test runs** — run number, date, ref/tag,
commit, trigger, passed/failed/skipped counts, and links to each run's full Allure
report and its GitHub Actions run. Click any row to open that run's report; the
trend/history charts live inside each report.

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
