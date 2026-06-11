"""The default end-user journey: installed binary + OS-managed service.

Runs against a real service-managed daemon (see conftest `service`), so it proves
the binary works the way most users run it — installed, with the daemon supervised
by the OS service manager rather than launched by hand.

One documented known-failure rides along:
  * spawn/talk — the binary loads default personas/skills via a relative path and
    bundles no data files, so spawn finds no persona; xfail on every OS until that
    bundling gap is fixed.

The service path runs for real on all three OSes, including Windows (a dedicated tiny
host binary, opengeneral-svc.exe, hosts the SCM dispatcher and supervises the daemon).
"""

from __future__ import annotations

import pytest

BUNDLING_GAP = "binary does not bundle personas/skills (relative Path); fix deferred"


def test_service_reports_running(service) -> None:
    resp = service.rpc("daemon.status")
    assert resp["ok"] is True
    assert resp["result"]["status"] == "running"
    assert resp["result"]["agents"] == 0


def test_service_lists_no_agents(service) -> None:
    resp = service.rpc("agent.list")
    assert resp["ok"] is True
    assert resp["result"] == []


def test_keys_are_managed_by_the_service(service) -> None:
    # The point of daemon-owned keys: the service daemon stores the secret under its
    # OWN account, so this works even when the service runs as a system account (the
    # Windows LocalSystem keyring gap). Add a key with a secret via the daemon, then
    # confirm the CLI sees it back through the same daemon.
    added = service.rpc(
        "keys.add", {"name": "svc-managed", "type": "anthropic", "secret": "sk-test-secret"}
    )
    assert added["ok"] is True, added
    try:
        listed = service.cli("keys", "list")
        assert listed.returncode == 0, listed.stdout + listed.stderr
        assert "svc-managed" in listed.stdout
    finally:
        service.rpc("keys.remove", {"name": "svc-managed"})


@pytest.mark.xfail(reason=BUNDLING_GAP, strict=False)
def test_spawn_and_talk_via_service(service) -> None:
    # Keys + action planes are daemon-owned; register them through the service daemon
    # (a static key needs no keyring secret and yields the StaticChatProvider). This is
    # exactly the point of daemon-owned storage — the secret is written and read by the
    # same principal, so it works even though the service runs as a system account.
    assert service.rpc("keys.add", {"name": "static", "type": "static"})["ok"]
    assert service.rpc(
        "action_planes.add", {"name": "default", "endpoint": "http://127.0.0.1:4767/mcp"}
    )["ok"]

    spawned = service.cli(
        "spawn", "--persona", "coder", "--name", "s1", "--key", "static", "--model", "static/none"
    )
    assert spawned.returncode == 0, spawned.stdout + spawned.stderr

    talked = service.cli("talk", "s1", stdin="hi\n/exit\n")
    assert "I'm ready to work on that." in talked.stdout

