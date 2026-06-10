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

# Nicely-named features per test module (key = module name minus the "test_"
# prefix); anything not listed falls back to a title-cased module name.
_FEATURE_NAMES = {
    "service_systemd": "Systemd backend",
    "service_launchd": "Launchd backend",
    "service_windows": "Windows SCM backend",
    "daemon": "Daemon",
    "daemon_client": "Daemon client",
    "providers": "Providers",
    "provider_config": "Providers",
    "key_config": "Keys & config",
    "agent": "Agent",
    "agent_factory": "Agent",
    "manifest": "Manifest",
    "personas": "Personas",
    "prompt": "Prompt assembly",
    "runner": "Chat runner",
    "runtime": "Runtime",
    "skills": "Skills",
    "action_plane": "Action plane",
    "cli_smoke": "CLI",
    "daemon_lifecycle": "Daemon lifecycle",
    "usage_personas": "Personas",
    "install_script": "Installer script",
}


def _epic_for(parts: tuple[str, ...]) -> str:
    if "integration" in parts:
        return "Binary usage"
    if "installer" in parts:
        return "Installer"
    return "Unit"


@pytest.fixture(autouse=True)
def _allure_metadata(request: pytest.FixtureRequest) -> None:
    # Organize the report: group each test under an Epic (tier) and Feature
    # (component) so the Behaviors tab is a tidy tree, tag it by tier + OS for
    # filtering, and record the OS as a parameter so history is tracked per
    # platform. No-op without allure-pytest / --alluredir.
    if not _HAS_ALLURE:
        return
    path = request.path
    epic = _epic_for(path.parts)
    stem = path.stem
    key = stem[len("test_"):] if stem.startswith("test_") else stem
    feature = _FEATURE_NAMES.get(key, key.replace("_", " ").capitalize())
    os_name = platform.system()
    try:
        allure.dynamic.epic(epic)
        allure.dynamic.feature(feature)
        allure.dynamic.tag(epic.lower().replace(" ", "-"))
        allure.dynamic.tag(os_name.lower())
        allure.dynamic.parameter("os", os_name)
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
