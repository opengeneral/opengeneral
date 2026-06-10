# Release workflow

File: [`.github/workflows/release.yml`](../.github/workflows/release.yml)

Builds the self-contained `opengeneral` binary on each OS and publishes the
binaries — with checksums — to a GitHub Release. These are the assets the
[curl installer](../install.sh) downloads from `releases/latest/download/`.

## Triggers

| Trigger | What happens |
|---|---|
| Push a tag matching `v*` (e.g. `v0.1.0`) | Test, build all platforms, **publish a GitHub Release**. |
| `workflow_dispatch` (manual run) | Test and build all platforms, upload the binaries as **workflow artifacts** only — no release. Useful for smoke-testing the build. |

PyInstaller cannot cross-compile, so each platform's binary is built on its own
runner.

## Jobs

```
test ──> build (matrix) ──> release   (release only on v* tags)
```

### `test`
Runs on `ubuntu-latest`. Installs `.[dev]` and runs `pytest -q`. Gates the build
so a tag can't publish a release from failing code.

### `build` (matrix)
One job per target; `fail-fast: false`.

| Runner | Target asset |
|---|---|
| `ubuntu-latest` | `opengeneral-linux-x86_64` |
| `macos-14` | `opengeneral-macos-arm64` |
| `windows-latest` | `opengeneral-windows-x86_64.exe` |

Each job installs `.[build]`, runs `packaging/build.sh` (Unix) or
`packaging/build.ps1` (Windows), renames the binary with its platform suffix, and
uploads it as an artifact.

Intel macOS is intentionally not built — Rosetta runs Intel binaries on Apple
Silicon, not the reverse, and Intel runners are scarce. Intel-Mac users build from
source.

### `release` (tags only)
Runs on `ubuntu-latest` with `contents: write`. Only runs when the ref is a `v*`
tag. Downloads every build artifact, generates `SHA256SUMS`, and publishes a
GitHub Release (via `softprops/action-gh-release`) with the binaries + checksums
attached and auto-generated release notes.

## Cutting a release

```bash
git tag v0.1.0
git push origin v0.1.0
```

The tag name becomes the release name. The published binaries are unsigned, so
macOS Gatekeeper / Windows SmartScreen warn on first launch.

## Permissions

Least-privilege: `contents: read` workflow-wide; only the `release` job is granted
`contents: write` to create the release.
