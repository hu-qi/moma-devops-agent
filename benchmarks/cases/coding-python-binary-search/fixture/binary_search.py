from typing import List


def search(arr: List[int], target: int) -> int:
    """Return the index of target in a sorted list, or -1 if not found.

    Example
    -------
    >>> search([1, 3, 5, 7, 9], 7)
    3
    """
    lo = 0
    # BUG: should be len(arr) - 1; using len(arr) - 2 misses the last element
    hi = len(arr) - 2
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
