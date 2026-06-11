"""Usage tests that exercise the default personas through the installed binary.

These are XFAIL on purpose: the binary loads default personas/skills via a relative
`Path("personas")` and PyInstaller bundles no data files, so an installed binary run
from any other directory finds no personas — `personas list` is empty and `spawn`
fails. The tests document that gap and will xpass once personas/skills are bundled
(resource resolver + PyInstaller --add-data).
"""

from __future__ import annotations

import pytest

BUNDLING_GAP = "binary does not bundle personas/skills (relative Path); fix deferred"


@pytest.mark.xfail(reason=BUNDLING_GAP, strict=False)
def test_personas_list_shows_defaults(run) -> None:
    result = run("personas", "list")
    assert result.returncode == 0
    assert "coder" in result.stdout
    assert "minimal" in result.stdout


@pytest.mark.xfail(reason=BUNDLING_GAP, strict=False)
def test_static_spawn_and_talk(daemon, run) -> None:
    # A "static" key needs no keyring secret and yields the StaticChatProvider. Keys
    # and action planes are daemon-owned, so register them through the daemon RPC
    # (the CLI's `keys add` only exposes anthropic/openai).
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
