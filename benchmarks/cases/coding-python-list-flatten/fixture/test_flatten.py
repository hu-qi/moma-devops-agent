from flatten import flatten


def main() -> None:
    assert flatten([]) == []
    assert flatten([1, 2, 3]) == [1, 2, 3]
    assert flatten([1, [2, 3]]) == [1, 2, 3]
    assert flatten([1, [2, [3, 4], 5]]) == [1, 2, 3, 4, 5]
    assert flatten([[1, [2]], [3, [4, [5]]]]) == [1, 2, 3, 4, 5]
    assert flatten([[], [1], [[2]]]) == [1, 2]


if __name__ == "__main__":
    main()
