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

import json
import os
from pathlib import Path

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


@pytest.mark.xfail(reason=BUNDLING_GAP, strict=False)
def test_spawn_and_talk_via_service(service) -> None:
    # The service-managed daemon reads the default config home; write the static key
    # there (a static key needs no keyring secret and yields the StaticChatProvider).
    home = Path(os.environ.get("OPENGENERAL_HOME", "~/.opengeneral")).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    (home / "keys.json").write_text(
        json.dumps({"keys": {"static": {"type": "static"}}}), encoding="utf-8"
    )
    assert service.cli(
        "action-planes", "add", "default", "--endpoint", "http://127.0.0.1:4767/mcp"
    ).returncode == 0

    spawned = service.cli(
        "spawn", "--persona", "coder", "--name", "s1", "--key", "static", "--model", "static/none"
    )
    assert spawned.returncode == 0, spawned.stdout + spawned.stderr

    talked = service.cli("talk", "s1", stdin="hi\n/exit\n")
    assert "I'm ready to work on that." in talked.stdout
