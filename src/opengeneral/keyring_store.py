from __future__ import annotations

import json
import os

import keyring

from opengeneral.config import OPENGENERAL_HOME

KEYRING_SERVICE = "opengeneral"

# Fallback secret store for environments with no usable OS keyring: headless Linux
# servers and containers, where there is no Secret Service / D-Bus session and a
# boot-started service has no interactive login to unlock a keyring. The daemon owns
# this file (mode 0600) in its config home, so the secret is written and read by the
# same process — exactly like the keyring path. The OS keyring is still preferred
# wherever it works (Windows, macOS, desktop Linux); the file is only a fallback.
_SECRETS_FILE = OPENGENERAL_HOME / "secrets.json"


def _read_file_secrets() -> dict[str, str]:
    try:
        return json.loads(_SECRETS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write_file_secrets(secrets: dict[str, str]) -> None:
    _SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _SECRETS_FILE.with_name(_SECRETS_FILE.name + ".tmp")
    # Create 0600 from the start so the secret is never briefly world-readable, then
    # atomically swap it into place.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        json.dump(secrets, file)
    os.replace(tmp, _SECRETS_FILE)


def set_secret(name: str, secret: str) -> None:
    try:
        keyring.set_password(KEYRING_SERVICE, name, secret)
        return
    except Exception:
        # No usable OS keyring (or it failed at runtime) — fall back to the file store.
        pass
    secrets = _read_file_secrets()
    secrets[name] = secret
    _write_file_secrets(secrets)


def get_secret(name: str) -> str:
    secret: str | None = None
    try:
        secret = keyring.get_password(KEYRING_SERVICE, name)
    except Exception:
        secret = None
    if not secret:
        secret = _read_file_secrets().get(name)
    if not secret:
        raise RuntimeError(f"No secret stored for key: {name}")
    return secret


def delete_secret(name: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, name)
    except Exception:
        pass
    secrets = _read_file_secrets()
    if secrets.pop(name, None) is not None:
        _write_file_secrets(secrets)
