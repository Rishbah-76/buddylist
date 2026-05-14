"""Minimal user-lookup helper used by the orders service tests."""

_USERS = {
    "usr_001": {"name": "Alice", "email": "alice@example.test"},
    "usr_002": {"name": "Bob", "email": "bob@example.test"},
}


def lookup(user_id: str) -> dict[str, str] | None:
    return _USERS.get(user_id)
