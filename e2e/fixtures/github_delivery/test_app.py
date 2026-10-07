from app import status, status_metadata


def main() -> None:
    assert status() == "fixed"
    assert status_metadata() == {"status": "fixed", "source": "devopspilot"}


if __name__ == "__main__":
    main()
