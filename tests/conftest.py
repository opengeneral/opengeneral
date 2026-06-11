from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

import keyring
import keyring.backend
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def binary() -> str:
    """Resolve the OpenGeneral product binary for integration/installer tests.

    Order: ``$OPENGENERAL_BINARY``, else the default build output
    ``dist/opengeneral[.exe]``. Skips (not fails) when neither exists, so a plain
    unit run is unaffected while ``./packaging/build.sh && pytest`` picks the freshly
    built binary up automatically — no need to export OPENGENERAL_BINARY by hand.
    """
    env = os.environ.get("OPENGENERAL_BINARY")
    if env:
        if not Path(env).exists():
            pytest.skip(f"OPENGENERAL_BINARY does not exist: {env}")
        return str(Path(env).resolve())
    name = "opengeneral.exe" if sys.platform == "win32" else "opengeneral"
    dist = REPO_ROOT / "dist" / name
    if dist.exists():
        return str(dist.resolve())
    pytest.skip(
        "no opengeneral binary found — build it (./packaging/build.sh or make build), "
        "or set OPENGENERAL_BINARY to a binary path"
    )

try:
    import allure

    _HAS_ALLURE = True
except ImportError:
    _HAS_ALLURE = False

# Each test module maps to a product domain (Behaviors epic) and component
# (feature), so the Behaviors tab is grouped by *what* is tested. The test tier
# (how it runs) is a separate axis: the Suites tab + a tag. Anything not listed
# falls back to an "Other" domain with a title-cased module name.
_DOMAIN: dict[str, tuple[str, str]] = {
    # Daemon & services
    "daemon": ("Daemon & services", "Daemon core"),
    "daemon_client": ("Daemon & services", "Daemon RPC client"),
    "daemon_lifecycle": ("Daemon & services", "Daemon lifecycle"),
    "service_journey": ("Daemon & services", "Service journey"),
    "service_systemd": ("Daemon & services", "systemd backend"),
    "service_launchd": ("Daemon & services", "launchd backend"),
    "service_windows": ("Daemon & services", "Windows SCM backend"),
    # Providers & API keys
    "providers": ("Providers & API keys", "Providers (LiteLLM)"),
    "key_config": ("Providers & API keys", "Key config"),
    # Personas, skills & prompts
    "personas": ("Personas, skills & prompts", "Personas"),
    "usage_personas": ("Personas, skills & prompts", "Personas"),
    "skills": ("Personas, skills & prompts", "Skills"),
    "manifest": ("Personas, skills & prompts", "Manifest"),
    "prompt": ("Personas, skills & prompts", "Prompt assembly"),
    # Agent runtime
    "agent": ("Agent runtime", "Agent"),
    "agent_factory": ("Agent runtime", "Agent"),
    "runtime": ("Agent runtime", "Runtime"),
    "runner": ("Agent runtime", "Chat runner"),
    "action_plane": ("Agent runtime", "Action plane"),
    # CLI & config
    "cli_smoke": ("CLI & config", "CLI"),
    # Installation
    "install_script": ("Installation", "Installer script"),
}


def _tier_for(parts: tuple[str, ...]) -> str:
    if "e2e" in parts:
        return "Service journey"
    if "integration" in parts:
        return "Binary usage"
    if "installer" in parts:
        return "Installer"
    return "Unit"


@pytest.fixture(autouse=True)
def _allure_metadata(request: pytest.FixtureRequest) -> None:
    # Both report trees lead with the OS, so per-platform results (especially skips
    # and xfails that differ by OS) read at a glance:
    #   Behaviors tab -> OS / product domain (epic) / component (feature): what is tested.
    #   Suites tab    -> OS / tier / component: how it runs.
    # Plus tags (tier, OS) for filtering and an `os` parameter so history is kept
    # per platform. No-op without allure-pytest / --alluredir.
    if not _HAS_ALLURE:
        return
    path = request.path
    tier = _tier_for(path.parts)
    stem = path.stem
    key = stem[len("test_"):] if stem.startswith("test_") else stem
    epic, feature = _DOMAIN.get(key, ("Other", key.replace("_", " ").capitalize()))
    os_name = platform.system()
    try:
        allure.dynamic.label("os", os_name)  # top-level grouping in the Behaviors tree
        allure.dynamic.epic(epic)
        allure.dynamic.feature(feature)
        allure.dynamic.label("parentSuite", os_name)  # Suites tree: OS / tier / component
        allure.dynamic.label("suite", tier)
        allure.dynamic.label("subSuite", feature)
        allure.dynamic.tag(tier.lower().replace(" ", "-"))
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
