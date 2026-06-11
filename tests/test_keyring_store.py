from __future__ import annotations

import os
import stat
import sys

import keyring
import keyring.backends.fail
import pytest

from opengeneral import keyring_store


@pytest.fixture
def no_keyring(monkeypatch: pytest.MonkeyPatch, tmp_path):
    # Simulate a headless box with no usable OS keyring (the fail backend raises on
    # every operation), and isolate the file store under tmp_path.
    keyring.set_keyring(keyring.backends.fail.Keyring())
    secrets_file = tmp_path / "secrets.json"
    monkeypatch.setattr(keyring_store, "_SECRETS_FILE", secrets_file)
    return secrets_file


def test_falls_back_to_file_when_no_keyring(no_keyring) -> None:
    keyring_store.set_secret("k1", "s3cr3t")
    assert no_keyring.exists()
    assert keyring_store.get_secret("k1") == "s3cr3t"


def test_file_fallback_is_locked_down(no_keyring) -> None:
    keyring_store.set_secret("k1", "s3cr3t")
    if sys.platform != "win32":  # Windows does not honor POSIX mode bits
        assert stat.S_IMODE(os.stat(no_keyring).st_mode) == 0o600


def test_delete_removes_the_file_secret(no_keyring) -> None:
    keyring_store.set_secret("k1", "s3cr3t")
    keyring_store.delete_secret("k1")
    with pytest.raises(RuntimeError):
        keyring_store.get_secret("k1")


def test_get_missing_secret_raises(no_keyring) -> None:
    with pytest.raises(RuntimeError):
        keyring_store.get_secret("nope")


def test_uses_keyring_when_available() -> None:
    # The autouse isolated_keyring fixture installs an in-memory backend, so the OS
    # keyring path is taken and nothing touches the file store.
    keyring_store.set_secret("k1", "s3cr3t")
    assert keyring_store.get_secret("k1") == "s3cr3t"
    assert keyring.get_password(keyring_store.KEYRING_SERVICE, "k1") == "s3cr3t"
