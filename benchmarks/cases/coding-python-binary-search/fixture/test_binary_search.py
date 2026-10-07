from binary_search import search


def main() -> None:
    arr = [1, 3, 5, 7, 9]
    assert search(arr, 1) == 0
    assert search(arr, 5) == 2
    assert search(arr, 9) == 4      # last element — boundary bug hits here
    assert search(arr, 4) == -1     # not found
    assert search([], 1) == -1      # empty list
    assert search([42], 42) == 0    # single element


if __name__ == "__main__":
    main()
