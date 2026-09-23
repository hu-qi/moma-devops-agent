from range_sum import sum_to


def main() -> None:
    assert sum_to(0) == 0
    assert sum_to(1) == 1
    assert sum_to(3) == 6
    assert sum_to(10) == 55


if __name__ == "__main__":
    main()
