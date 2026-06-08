# OpenGeneral CLI

This document tracks the required OpenGeneral CLI surface.

OpenGeneral is a general-purpose agent runtime. The CLI should make four things explicit:

1. which persona is being used as the cognitive template
2. which named agent entity was spawned from that persona
3. which generated agent ID is used as the Action Plane identity
4. which Action Plane endpoint the agent operates through

## Command model

```bash
opengeneral <command> [options]
```

Primary flow:

```bash
opengeneral personas list
opengeneral personas show coder
opengeneral keys add personal-anthropic --type anthropic
opengeneral action-planes add default --endpoint http://127.0.0.1:4767/mcp
opengeneral daemon start
opengeneral spawn --persona coder --name coder
opengeneral agents list
opengeneral talk coder
```

`spawn` is interactive when `--key` or `--model` are omitted. It prompts for the provider type, then either an existing API key or a fresh one (with the secret entered via hidden prompt and stored in the OS keyring), then the model name.

The standard OpenGeneral home is:

```text
~/.opengeneral
```

It stores Action Plane configuration, spawned agent records, API key metadata, and user-installed personas:

```text
~/.opengeneral/keys.json
~/.opengeneral/action-planes.json
~/.opengeneral/agents.json
~/.opengeneral/personas/*.json
```

API key secrets are not stored in any of those JSON files. They are stored in the OS keyring under the service `opengeneral`, keyed by the user-chosen key name.

OpenGeneral spawns agents from personas. A single local supervisor daemon manages all running agents. Each agent has a user-facing name plus a generated persona-prefixed ID. The generated ID is the Action Plane identity. Each agent picks its own provider model and one of the user's stored API keys. The Action Plane owns MCP servers, policies, permissions, tool filtering, argument restrictions, and audit.

## Implemented commands

### `opengeneral personas list`

List known local personas.

```bash
opengeneral personas list
```

### `opengeneral personas show <persona>`

Show a persona manifest and its declared behavior capabilities.

```bash
opengeneral personas show coder
```

### `opengeneral keys list`

List configured API keys (metadata only — secrets stay in the OS keyring).

```bash
opengeneral keys list
```

### `opengeneral keys add <name> --type <type> [--base-url <url>]`

Add an API key. The secret is captured via a hidden interactive prompt and stored in the OS keyring under service `opengeneral` with account `<name>`.

```bash
opengeneral keys add personal-anthropic --type anthropic
opengeneral keys add work-openai --type openai
```

Each key has a readable, unique name so the user can keep multiple keys per provider (e.g., personal vs work).

### `opengeneral keys show <name>`

Show one configured API key's metadata.

```bash
opengeneral keys show personal-anthropic
```

### `opengeneral keys remove <name>`

Remove an API key and delete its secret from the OS keyring.

```bash
opengeneral keys remove personal-anthropic
```

### `opengeneral action-planes list`

List configured Action Plane endpoints.

```bash
opengeneral action-planes list
```

### `opengeneral action-planes add <name> --endpoint <url>`

Add or update an Action Plane endpoint.

```bash
opengeneral action-planes add default \
  --endpoint http://127.0.0.1:4767/mcp
```

### `opengeneral action-planes show <name>`

Show one configured Action Plane.

```bash
opengeneral action-planes show default
```

### `opengeneral action-planes remove <name>`

Remove one configured Action Plane.

```bash
opengeneral action-planes remove default
```

### `opengeneral daemon start`

Start the local supervisor daemon.

```bash
opengeneral daemon start
```

### `opengeneral daemon status`

Show daemon status.

```bash
opengeneral daemon status
```

### `opengeneral daemon stop`

Stop the local supervisor daemon.

```bash
opengeneral daemon stop
```

### `opengeneral spawn --persona <persona> --name <agent-name> [--action-plane <name>] [--key <name>] [--model <model>]`

Spawn a daemon-managed agent from a persona.

Interactive form (recommended):

```bash
opengeneral spawn --persona coder --name coder
# -> Select a provider: anthropic / openai
# -> Select an API key for anthropic (or add a new one — secret prompted, stored in keyring)
# -> Model: anthropic/claude-opus-4-7
```

Non-interactive form (everything pre-resolved):

```bash
opengeneral spawn --persona coder --name coder \
  --key personal-anthropic --model anthropic/claude-opus-4-7
```

Required behavior:

- Resolve the persona tag.
- Resolve the Action Plane endpoint.
- Use `--name` as the readable agent name.
- Generate a persona-prefixed agent ID.
- Use that generated agent ID as the Action Plane identity.
- Prompt for or resolve a provider type, then an API key of that type.
- Prompt for or resolve a model name.
- Store the selected key name and model on the spawned agent.
- Ask the local daemon to spawn and manage the running agent.
- Store the agent in `~/.opengeneral/agents.json`.
- Create a Streamable HTTP MCP client to the Action Plane.
- Route all Environment-Modifying Operations through the Action Plane.

Current limitation:

- Creates and manages the agent in the local daemon.
- Uses an empty Action Plane connector until real Action Plane MCP client transport is implemented.

### `opengeneral talk <name>`

Open a chat with a spawned agent.

```bash
opengeneral talk coder
```

Expected terminal behavior:

```text
Talking to coder. Type /exit to leave.

coder> hello
<agent response>

coder> /exit
```


### `opengeneral agents list`

List spawned agents.

```bash
opengeneral agents list
```

Expected output:

```text
Agents:
  coder  coder-a1b2c3d4e5f6  coder  default  personal-anthropic  anthropic/claude-opus-4-7
```

### `opengeneral agents show <name>`

Show a spawned agent by readable name.

```bash
opengeneral agents show coder
```

Expected output:

```text
Agent: coder
ID: coder-a1b2c3d4e5f6
Persona: coder
Action Plane identity: coder-a1b2c3d4e5f6
Action plane: default
Key: personal-anthropic
Model: anthropic/claude-opus-4-7
Status: idle
```

### `opengeneral agents remove <name>`

Remove a spawned agent record.

```bash
opengeneral agents remove coder
```

## Persona construction format

Personas construct agents with declared capabilities and Agent Skills-style skill references.

```json
{
  "id": "opengeneral/persona:opengeneral-coder-v1",
  "capabilities": [],
  "extensions": {
    "opengeneral.skills": ["debugging", "implementation"]
  }
}
```

Skills are loaded from Agent Skills-style directories:

```text
skills/<skill-name>/SKILL.md
~/.opengeneral/skills/<skill-name>/SKILL.md
```

Each `SKILL.md` has YAML-like frontmatter with `name` and `description`, followed by markdown instructions.

## Keys configuration format

Standard keys config path:

```text
~/.opengeneral/keys.json
```

Shape (metadata only — secrets live in the OS keyring):

```json
{
  "keys": {
    "personal-anthropic": {
      "type": "anthropic"
    },
    "work-openai": {
      "type": "openai",
      "base_url": "https://gateway.example.com/v1"
    }
  }
}
```

## Action Plane configuration format

Standard Action Plane config path:

```text
~/.opengeneral/action-planes.json
```

Shape:

```json
{
  "action_planes": {
    "default": {
      "endpoint": "http://127.0.0.1:4767/mcp"
    },
    "prod": {
      "endpoint": "https://action-plane.company.com/mcp"
    }
  }
}
```

## Agent configuration format

Standard agents config path:

```text
~/.opengeneral/agents.json
```

Shape:

```json
{
  "agents": {
    "coder": {
      "id": "coder-a1b2c3d4e5f6",
      "persona": "coder",
      "action_plane": "default",
      "key": "personal-anthropic",
      "model": "anthropic/claude-opus-4-7"
    }
  }
}
```

Rules:

- Agent names are user-facing handles.
- Agent IDs are generated by OpenGeneral and prefixed with the persona tag.
- The generated agent ID is the Action Plane identity.
- The `action_plane` field points to `action-planes.json`.
- The `key` field points to `keys.json`; the actual secret lives in the OS keyring.
- OpenGeneral does not self-authorize; the Action Plane owns authentication and authorization.
- The Action Plane owns docked MCP servers, policies, permissions, tool filtering, argument restrictions, and audit.

## Implementation priority

1. Persona tags everywhere; no user-facing manifest paths.
2. Action Plane config path: `~/.opengeneral/action-planes.json`.
3. Agent config path: `~/.opengeneral/agents.json`.
4. `action-planes add/list/show/remove`, `agents list/show/remove`.
5. Live Action Plane MCP client creation for spawned agents.
