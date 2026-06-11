"""Black-box smoke tests of the built binary's CLI (no daemon)."""

from __future__ import annotations


def test_help_lists_commands(run) -> None:
    result = run("--help")
    assert result.returncode == 0
    assert "spawn" in result.stdout
    assert "daemon" in result.stdout


def test_keys_list_without_daemon_reports_unavailable(run) -> None:
    # Keys are daemon-owned now, so `keys list` goes through the daemon; with none
    # running the CLI reports that rather than reading a local file.
    result = run("keys", "list")
    assert result.returncode != 0
    assert "daemon is not running" in result.stdout.lower()


def test_unknown_command_fails(run) -> None:
    result = run("definitely-not-a-command")
    assert result.returncode != 0
