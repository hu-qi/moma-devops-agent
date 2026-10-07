from typing import Any, List


def flatten(lst: List[Any]) -> List[Any]:
    """Recursively flatten an arbitrarily nested list of values.

    Example
    -------
    >>> flatten([1, [2, [3, 4], 5]])
    [1, 2, 3, 4, 5]
    """
    result: List[Any] = []
    for item in lst:
        # BUG: only flattens one level of nesting
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result
