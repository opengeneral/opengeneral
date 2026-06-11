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

It deliberately does **not** run on every push: the 3-OS matrix is expensive, and
doc/config-only changes shouldn't trigger it.

## The flow mirrors the end-user journey

```
unit ──> build ──> e2e ──┐
  └──────────────────────┴──> report   (Allure -> GitHub Pages, always runs)
```

The guiding idea: **test the binary the way a user actually gets it.** Earlier the
binary was built and tested in the same job — but that environment has the Python
toolchain, the source tree, and dev deps, so a binary that secretly leans on any of
them passes in CI yet breaks once installed. So `build` now only *produces* the
artifact, and a separate `e2e` job downloads it onto a clean runner and walks the
real journey: **install script → service install → use the installed binary against
the service-managed daemon → uninstall.**

The default journey is the **service-managed** one, because that's where most
(non-technical) users are: the binary is installed *and* the daemon is registered
with the OS service manager. The service-less, foreground-daemon path
(`opengeneral daemon run`) is the **`--no-service`** case for technical users on
systems without a service manager — it's covered as a secondary scenario.

## Jobs

### `unit`
Installs `.[dev]` and runs the mocked source tests (ignoring `tests/integration`,
`tests/installer`, and `tests/e2e`, which need the built binary). Platform-specific
backends are guarded: launchd tests skip on Windows; Windows SCM tests skip
elsewhere. `systemctl`/`launchctl`/`win32serviceutil` are mocked.

### `build`
Installs `.[build]`, builds the binary (`packaging/build.sh` / `build.ps1`), and
**uploads it as the `binary-<os>` artifact**. No tests run here — that's the point.

### `e2e`
Downloads the `binary-<os>` artifact onto a fresh runner and installs **only the
test runner** (`pytest allure-pytest keyring`) — deliberately *not* `pip install -e
.`, so the binary is exercised without its own source or deps present. Then:

1. **Install (the "install script" stage):** runs the real `install.sh` /
   `install.ps1`, fed an *offline fake release* built from the artifact (the
   installer pulls from Releases `latest`, which wouldn't match this commit), to put
   the binary on `PATH`.
2. **Binary + installer suites (no service):** `pytest tests/integration
   tests/installer` — the secondary `--no-service` path. `tests/integration` drives
   a **foreground** daemon (isolated port + `OPENGENERAL_HOME`); `tests/installer`
   is installer-correctness (download + checksum verify + checksum-mismatch
   rejection + uninstall). No OS service is touched here, so it runs first and can't
   disturb the service started next.
3. **Service journey (`OPENGENERAL_E2E=1`):** `pytest tests/e2e` installs and starts
   the **real OS service** (systemd user unit / launchd agent / Windows SCM —
   abstracted by the binary itself), then asserts the service-managed daemon is
   serving RPC and exercises `spawn`/`talk` against it, then uninstalls it (fixture
   teardown).
4. **Uninstall + verify:** runs `install.sh --uninstall` and asserts the binary is
   gone (Unix).

Linux gets `loginctl enable-linger` + `XDG_RUNTIME_DIR` so the per-user systemd
manager is reachable; macOS uses the runner's GUI session for launchd.

The Windows SCM service is hosted by a second, tiny binary (`opengeneral-svc.exe`)
that ships alongside `opengeneral.exe` — a one-file `opengeneral.exe` extracts too
slowly to host the dispatcher within the SCM start timeout, so the small host hosts
the service and supervises `opengeneral.exe daemon run` as a child. Secrets are stored
by the daemon (OS keyring where available, else a `0600` file), so the service can use
them even running as LocalSystem.

**Known failure (documented, not hidden):** `spawn`/`talk` are `xfail` on every OS —
the binary loads default personas/skills via a relative `Path("personas")` and bundles
no data files, so an installed binary finds no persona. They flip to pass once that
bundling is fixed.

### `report` (Allure -> GitHub Pages)
`if: always()`, so it reports even when tests fail. Each test job emits Allure
results (`allure-pytest`). The conftest in `tests/` labels every test so the
report's tree groups by product domain (Epic) / component (Feature) — what is tested
— via the Allure 3 `awesome` report's `groupBy` (see [`allurerc.mjs`](../allurerc.mjs)).
Tests are also tagged by tier (Unit / Binary usage / Service journey / Installer) and
OS, with the OS recorded as a parameter so history is kept per platform. This job:
1. downloads every job's `allure-results-*`,
2. installs the Allure 3 CLI (`npm install -g allure`),
3. restores the cumulative `history.jsonl` from `gh-pages` (trend continuity),
4. runs `allure generate` (config in `allurerc.mjs`),
5. runs `scripts/allure_runs_index.py` to **archive this run's report under
   `runs/<run-number>/`, render a root `index.html` table of all runs, and prune**
   (keep every `v*` release run + the last 10 dispatch runs),
6. deploys the site to GitHub Pages.

The GitHub Pages root is a **table of test runs** — run number, date, ref/tag,
commit, trigger, passed/failed/skipped counts, and links to each run's full Allure
report and its GitHub Actions run.

## Running the tiers locally

```bash
# Unit (mocked source)
pytest tests --ignore=tests/integration --ignore=tests/installer --ignore=tests/e2e

# Build, then the binary-dependent suites pick the binary up automatically
# (tests resolve $OPENGENERAL_BINARY, else dist/opengeneral[.exe]).
./packaging/build.sh
pytest tests/integration tests/installer

# Service journey — installs and starts a REAL OS service, so it's opt-in.
# (Best run in a throwaway VM/container; it touches your ~/.opengeneral and
# registers an OS service.)
OPENGENERAL_E2E=1 OPENGENERAL_BINARY="$PWD/dist/opengeneral" pytest tests/e2e

# Emit Allure results (then `allure serve allure-results` to view locally)
pytest tests --alluredir=allure-results
```
