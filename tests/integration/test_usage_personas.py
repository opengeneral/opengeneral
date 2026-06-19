"""Usage tests that exercise the default personas through the installed binary.

The defaults (`coder`, `minimal`, and the standard skills) are bundled into the
binary via `--add-data` and resolved through `sys._MEIPASS`, so an installed binary
finds them from any working directory. Personas are resolved by the daemon (the
single source of truth), so `personas list` talks to a running daemon.
"""

from __future__ import annotations


def test_personas_list_shows_defaults(daemon, run) -> None:
    result = run("personas", "list")
    assert result.returncode == 0
    assert "coder" in result.stdout
    assert "minimal" in result.stdout


def test_static_spawn_and_talk(daemon, run) -> None:
    # A "static" key needs no keyring secret and yields the StaticChatProvider. Keys
    # and action planes are daemon-owned, so register them through the daemon RPC.
    assert daemon.rpc("keys.add", {"name": "static", "type": "static"})["ok"]
    assert daemon.rpc(
        "action_planes.add", {"name": "default", "endpoint": "http://127.0.0.1:4767/mcp"}
    )["ok"]

    spawned = run(
        "spawn", "--persona", "coder", "--name", "s1", "--key", "static", "--model", "static/none"
    )
    assert spawned.returncode == 0, spawned.stdout + spawned.stderr

    talked = run("talk", "s1", stdin="hi\n/exit\n")
    assert "I'm ready to work on that." in talked.stdout
