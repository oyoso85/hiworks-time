import keyring
import keyring.errors

_SERVICE = "HiworksTimeWidget"
_USER_KEY = "__username__"


def save(username: str, password: str) -> None:
    keyring.set_password(_SERVICE, _USER_KEY, username)
    keyring.set_password(_SERVICE, username, password)


def load() -> tuple | None:
    """Returns (username, password) or None if not set."""
    username = keyring.get_password(_SERVICE, _USER_KEY)
    if not username:
        return None
    password = keyring.get_password(_SERVICE, username)
    if not password:
        return None
    return username, password


def clear() -> None:
    username = keyring.get_password(_SERVICE, _USER_KEY)
    if not username:
        return
    for key in (username, _USER_KEY):
        try:
            keyring.delete_password(_SERVICE, key)
        except keyring.errors.PasswordDeleteError:
            pass
