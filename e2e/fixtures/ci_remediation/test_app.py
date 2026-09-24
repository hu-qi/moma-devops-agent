from app import status


def main() -> None:
    assert status() == "fixed"


if __name__ == "__main__":
    main()
