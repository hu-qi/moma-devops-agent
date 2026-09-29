from date_parser import parse_date


def main() -> None:
    assert parse_date("2024-1-5") == (2024, 1, 5)
    assert parse_date("2024-12-25") == (2024, 12, 25)
    assert parse_date("2024-03-15") == (2024, 3, 15)
    assert parse_date("2000-01-01") == (2000, 1, 1)
    assert parse_date("1999-09-09") == (1999, 9, 9)

    try:
        parse_date("not-a-date")
        raise AssertionError("should have raised ValueError")
    except ValueError:
        pass


if __name__ == "__main__":
    main()
