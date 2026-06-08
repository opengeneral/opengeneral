from __future__ import annotations

import keyring

KEYRING_SERVICE = "opengeneral"


def set_secret(name: str, secret: str) -> None:
    keyring.set_password(KEYRING_SERVICE, name, secret)


def get_secret(name: str) -> str:
    secret = keyring.get_password(KEYRING_SERVICE, name)
    if not secret:
        raise RuntimeError(f"No secret stored for key: {name}")
    return secret


def delete_secret(name: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass
