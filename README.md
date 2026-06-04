# OpenGeneral

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

## Usage guide

### 1. Install for local development

```bash
pip install -e '.[dev]'
```

You can also run without installing by setting `PYTHONPATH=src` in front of commands.

### 2. Configure an Action Plane

OpenGeneral stores user configuration and user-installed personas under:

```text
~/.opengeneral/action-planes.json
~/.opengeneral/agents.json
~/.opengeneral/personas/*.json
```

Configure a default Action Plane endpoint:

```bash
opengeneral action-planes add default \
  --endpoint http://127.0.0.1:4767/mcp
```

Or configure a remote Action Plane endpoint:

```bash
opengeneral action-planes add prod \
  --endpoint https://action-plane.company.com/mcp
```

### 3. Start the daemon

```bash
opengeneral daemon start
opengeneral daemon status
```

OpenGeneral uses one local supervisor daemon to manage all running agents.

### 4. Spawn an agent from a persona

```bash
opengeneral spawn --persona coder --name coder
```

This creates a running daemon-managed agent named `coder` with a generated ID prefixed with the persona name, such as:

```text
coder-a1b2c3d4e5f6
```

The generated ID is also the Action Plane identity. The Action Plane remains responsible for authentication, policy, tool filtering, argument restrictions, and audit.

### 5. Talk to the agent

```bash
opengeneral talk coder
```

### 6. Run tests

```bash
pytest
```
