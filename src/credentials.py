import keyring
import keyring.errors

_SERVICE = "HiworksTimeWidget"
_USER_KEY = "__username__"
_DOMAIN_KEY = "__domain__"


def save(username: str, password: str, domain: str) -> None:
    keyring.set_password(_SERVICE, _USER_KEY, username)
    keyring.set_password(_SERVICE, username, password)
    keyring.set_password(_SERVICE, _DOMAIN_KEY, domain)


def load() -> tuple | None:
    """Returns (username, password, domain) or None if not set."""
    username = keyring.get_password(_SERVICE, _USER_KEY)
    if not username:
        return None
    password = keyring.get_password(_SERVICE, username)
    if not password:
        return None
    domain = keyring.get_password(_SERVICE, _DOMAIN_KEY) or ""
    return username, password, domain


def clear() -> None:
    username = keyring.get_password(_SERVICE, _USER_KEY)
    if not username:
        return
    for key in (username, _USER_KEY, _DOMAIN_KEY):
        try:
            keyring.delete_password(_SERVICE, key)
        except keyring.errors.PasswordDeleteError:
            pass
