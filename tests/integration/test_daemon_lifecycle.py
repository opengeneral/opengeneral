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


def test_daemon_stops_cleanly_via_rpc(daemon) -> None:
    code = daemon.stop()
    assert code == 0
