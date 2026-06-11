"""Drive the real daemon via `daemon run` foreground + RPC, then stop it cleanly.

This is the OS-agnostic daemon test — it does not touch the OS service manager,
so it is reliable on headless runners across all three platforms.
"""

from __future__ import annotations


def test_daemon_reports_running_with_no_agents(daemon) -> None:
    resp = daemon.rpc("daemon.status")
    assert resp["ok"] is True
    assert resp["result"]["status"] == "running"
    assert resp["result"]["agents"] == 0


def test_daemon_lists_no_agents(daemon) -> None:
    resp = daemon.rpc("agent.list")
    assert resp["ok"] is True
    assert resp["result"] == []


def test_action_planes_roundtrip_via_daemon(daemon, run) -> None:
    added = run("action-planes", "add", "default", "--endpoint", "http://127.0.0.1:4767/mcp")
    assert added.returncode == 0, added.stdout + added.stderr
    listed = run("action-planes", "list")
    assert listed.returncode == 0
    assert "default" in listed.stdout
    assert "http://127.0.0.1:4767/mcp" in listed.stdout


def test_keys_list_empty_via_daemon(daemon, run) -> None:
    result = run("keys", "list")
    assert result.returncode == 0
    assert "(none)" in result.stdout


def test_daemon_stops_cleanly_via_rpc(daemon) -> None:
    code = daemon.stop()
    assert code == 0
