from __future__ import annotations

import platform

import keyring
import keyring.backend
import pytest

try:
    import allure

    _HAS_ALLURE = True
except ImportError:
    _HAS_ALLURE = False


@pytest.fixture(autouse=True)
def _allure_os_parameter() -> None:
    # Tag every test with the OS as an Allure parameter so the merged report keeps
    # a distinct pass/fail history per platform (history keys off parameters, not
    # labels). No-op when allure-pytest isn't installed or --alluredir isn't used.
    if _HAS_ALLURE:
        try:
            allure.dynamic.parameter("os", platform.system())
        except Exception:
            pass


class _InMemoryKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.store.pop((service, username), None)


@pytest.fixture(autouse=True)
def isolated_keyring() -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(_InMemoryKeyring())
    yield
    keyring.set_keyring(previous)
