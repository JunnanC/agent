import secrets


def make_public_id(prefix: str) -> str:
    normalized = prefix.replace("_", "").replace("-", "")
    if not prefix or not normalized.isalnum():
        raise ValueError("prefix must be a non-empty alphanumeric identifier")
    return f"{prefix}_{secrets.token_urlsafe(24)}"
