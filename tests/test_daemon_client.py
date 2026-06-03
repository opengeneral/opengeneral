from __future__ import annotations

import pytest

from opengeneral.daemon_client import DaemonClient, DaemonUnavailableError


def test_daemon_client_reports_unavailable_daemon() -> None:
    client = DaemonClient("127.0.0.1", 9)

    with pytest.raises(DaemonUnavailableError):
        client.status()
