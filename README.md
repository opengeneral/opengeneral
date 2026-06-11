<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="logos/opengeneral-logo-dark.svg">
    <img src="logos/opengeneral-logo.svg" alt="OpenGeneral" height="88">
  </picture>
</p>

OpenGeneral is a general-purpose runtime for spawning agents from reusable personas.

Unlike coding-specific agent harnesses, OpenGeneral does not embed a fixed tool bundle into the agent runtime. It loads a persona, spawns an agent and connects it to an Action Plane, and lets the same cognitive harness operate across different domains.

```bash
opengeneral spawn --persona coder
opengeneral spawn --persona research
opengeneral spawn --persona devops
opengeneral spawn --persona data-analysis
opengeneral spawn --persona personal-admin
```

The first included persona is a coder persona because coding makes the action boundary easy to inspect: filesystem, shell, and git access are useful but high-impact environment operations.

## Why OpenGeneral?

Claude Code and Codex are excellent coding agent harnesses. OpenGeneral is aiming at a different layer: a general-purpose harness whose action surface is governed by an external Action Plane.

The practical difference is:

| Coding-specific harness | OpenGeneral |
|---|---|
| Optimized around one domain | Same harness can run many personas |
| Tool surface is embedded or bundled | Tool surface comes from an external Action Plane |
| Adding a new domain usually means new harness behavior | Adding a new domain means declaring a persona |
| Safety is usually wrapped around built-in tools | Safety is enforced at the Action Plane boundary |

OpenGeneral's pitch is **generality first**: one harness, many cognitive personas. Safety follows from keeping reasoning separate from environment-modifying actions.

## What is an Action Plane?

An Action Plane is the external boundary where an agent's environment-changing work happens. OpenGeneral owns the cognitive side: loading personas, spawning agents, and running the agent loop. The Action Plane owns the tool side: exposing MCP tools, authenticating agent identities, enforcing permissions, filtering tool access, and auditing actions.

By default, OpenGeneral is designed to set up and connect to MCP Harbour as the default Action Plane. That default should make the first-run experience simple, but it is not a lock-in point. Users can independently set up and configure their own Action Plane locally, on another machine, or as a shared remote service, then point OpenGeneral at its MCP endpoint.

This keeps OpenGeneral composable. The same `coder` persona can run against a default Action Plane for personal projects or a remote Action Plane for a team environment, without changing the persona or embedding tools into the runtime.

```text
persona -> spawned agent -> Action Plane -> MCP tools
```

## Personas and agents

A persona is a manifest plus the construction material needed for a domain: declared capabilities and extension-provided construction material such as Agent Skills-style skill references. An agent is a spawned entity created from a persona. The agent has a readable user-facing name and a generated ID used as its Action Plane identity.

Skills are cognitive instruction packages loaded from `SKILL.md` files. They shape how an agent works, but they are not environment tools and do not grant access. Environment access still belongs to the Action Plane.

The same OpenGeneral harness should be able to spawn agents from any persona against any configured Action Plane.

## Install

OpenGeneral ships as a self-contained binary — no Python environment is needed at runtime.

**Linux / macOS (Apple Silicon):**

```bash
curl -LsSf https://raw.githubusercontent.com/opengeneral/opengeneral/main/install.sh | sh
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/opengeneral/opengeneral/main/install.ps1 | iex
```

The installer downloads the matching binary from the latest GitHub Release, verifies its checksum, and installs it to `~/.local/bin` (Linux/macOS) or `%LOCALAPPDATA%\Programs\OpenGeneral` (Windows, added to your per-user PATH). Useful flags:

- `--with-service` (`-WithService` on Windows) also registers the background daemon. On Windows that step prompts for Administrator elevation automatically.
- `--uninstall` (`-Uninstall`) unregisters the daemon and removes the binary, leaving your config and keyring secrets intact.
- `--version=vX.Y.Z` (`-Version`) installs a specific release; `INSTALL_DIR` overrides the install directory.

The binaries are unsigned, so macOS Gatekeeper / Windows SmartScreen may warn on first launch. The frozen binary is service-manager aware: `opengeneral daemon install` writes a systemd unit / launchd agent / Windows service whose launch command is the installed binary plus `daemon run`.

**Intel Macs** have no prebuilt binary (Rosetta runs Intel binaries on Apple Silicon, not the reverse) — build from source instead (see below).

### Build from source

PyInstaller does not cross-compile, so build on the target OS:

```bash
pip install -e '.[build]'   # get PyInstaller + deps
./packaging/build.sh        # -> dist/opengeneral  (build.ps1 on Windows -> dist\opengeneral.exe)
```

On Linux/macOS, `make install-bin` builds and copies the binary to `~/.local/bin` (override with `INSTALL_DIR`); `make uninstall-bin` reverses it.

### Releases

Pushing a `v*` tag (e.g. `v0.1.0`) runs `.github/workflows/release.yml`, which runs the tests, builds binaries on Linux (x86_64), macOS (arm64), and Windows (x86_64), and publishes them with `SHA256SUMS` to a GitHub Release — the assets the installer above downloads. A manual run (`workflow_dispatch`) builds the same binaries as downloadable artifacts without publishing.

### GitHub Actions workflows

- [`docs/cross-platform-tests.md`](docs/cross-platform-tests.md) — the cross-platform test workflow. Mirrors the end-user journey across Linux/macOS/Windows: unit (mocked source) → build (artifact) → e2e (install the artifact, register + start the OS service, exercise the installed binary against the service-managed daemon, uninstall), with an Allure history report published to GitHub Pages. Runs on a `v*` tag or manual dispatch.
- [`docs/release.md`](docs/release.md) — the release workflow: per-platform binary builds published to GitHub Releases on a `v*` tag.

## Usage guide

### 1. Install for local development

```bash
pip install -e '.[dev]'
```

You can also run without installing by setting `PYTHONPATH=src` in front of commands. Prefer the binary above for normal use.

On Linux/macOS a `Makefile` wraps the common tasks — run `make help` to list them (`make dev`, `make test`, `make build`, `make install-bin`, `make clean`).

### 2. Install and start the daemon

The daemon owns all runtime state — agents, API keys, and Action Plane endpoints. Install and start it first; the `keys` and `action-planes` commands below are thin clients that talk to it.

```bash
opengeneral daemon install
opengeneral daemon start
opengeneral daemon status
```

- Linux: installs a per-user `systemd` unit at `~/.config/systemd/user/opengeneral.service`. Run `loginctl enable-linger $USER` once if you want the service to keep running after you log out.
- macOS: installs a per-user `launchd` agent at `~/Library/LaunchAgents/com.opengeneral.daemon.plist`.
- Windows: registers a Windows service — a tiny `opengeneral-svc.exe` hosts the SCM service and supervises the daemon process.

The service's launch command is pinned at install time (the install output prints it). If that path changes — you rebuild the environment or move a packaged binary — re-run `opengeneral daemon install`.

If the daemon fails to load persisted agents on startup it exits with code 78, and the service definition keeps it from respawning in a tight loop (`RestartPreventExitStatus=78` on systemd, `KeepAlive=Crashed` on launchd). Fix the underlying config and then `opengeneral daemon start`.

In a container or other environment without a supported service manager, run the daemon in the foreground instead:

```bash
opengeneral daemon run
```

### 3. Add an API key

Keys are managed by the running daemon. The CLI sends the secret to the daemon, which stores the metadata (name, provider type, optional base URL) under its own config home and the secret in its OS keyring (service `opengeneral`). Storing and reading the secret in the same process is what lets the daemon use your key even when it runs as an OS service.

```bash
opengeneral keys add personal-anthropic --type anthropic
# Prompts (hidden) for the API key secret and hands it to the daemon to store.
```

You can keep multiple keys per provider — pick distinct, readable names like `personal-anthropic` and `work-anthropic` so each agent can pick the right one.

### 4. Configure an Action Plane

Register a default Action Plane endpoint with the daemon:

```bash
opengeneral action-planes add default \
  --endpoint http://127.0.0.1:4767/mcp
```

Or a remote Action Plane endpoint:

```bash
opengeneral action-planes add prod \
  --endpoint https://action-plane.company.com/mcp
```

### 5. Spawn an agent from a persona

```bash
opengeneral spawn --persona coder --name coder
```

`spawn` is interactive when `--key` and `--model` are not supplied. It will prompt to choose a provider, then select (or add) an API key for that provider, then enter the model name.

To skip the prompts, pass everything inline:

```bash
opengeneral spawn --persona coder --name coder \
  --key personal-anthropic \
  --model anthropic/claude-opus-4-7
```

Either form creates a running daemon-managed agent named `coder` with a generated ID prefixed with the persona name, such as:

```text
coder-a1b2c3d4e5f6
```

The generated ID is also the Action Plane identity. The Action Plane remains responsible for authentication, policy, tool filtering, argument restrictions, and audit.

### 6. Talk to the agent

```bash
opengeneral talk coder
```

### 7. Run tests

```bash
pytest
```
