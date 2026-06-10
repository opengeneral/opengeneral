"""Black-box smoke tests of the built binary's CLI (no daemon, no keyring)."""

from __future__ import annotations


def test_help_lists_commands(run) -> None:
    result = run("--help")
    assert result.returncode == 0
    assert "spawn" in result.stdout
    assert "daemon" in result.stdout


def test_keys_list_empty(run) -> None:
    result = run("keys", "list")
    assert result.returncode == 0
    assert "(none)" in result.stdout


def test_action_planes_add_and_list(run) -> None:
    added = run("action-planes", "add", "default", "--endpoint", "http://127.0.0.1:4767/mcp")
    assert added.returncode == 0

    listed = run("action-planes", "list")
    assert listed.returncode == 0
    assert "default" in listed.stdout
    assert "http://127.0.0.1:4767/mcp" in listed.stdout


def test_unknown_command_fails(run) -> None:
    result = run("definitely-not-a-command")
    assert result.returncode != 0
