import hmac
import secrets


def verify_token(provided_token: str, expected_token: str) -> bool:
    """Clean, timing-attack resistant authentication check."""
    if not provided_token or not expected_token:
        return False
    return secrets.compare_digest(provided_token.encode("utf-8"), expected_token.encode("utf-8"))
