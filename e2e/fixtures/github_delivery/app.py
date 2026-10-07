def status() -> str:
    """Return the current fixture status."""
    return "fixed"

def status_metadata() -> dict[str, str]:
    """Return fixture status metadata."""
    return {
        "status": status(),
        "source": "devopspilot"
    }