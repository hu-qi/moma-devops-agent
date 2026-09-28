from typing import Any


def extract_nested_value(data: dict[str, Any], path: str, default: Any = None) -> Any:
    # Defect: throws KeyError when key is missing instead of returning default
    current = data
    for part in path.split("."):
        current = current[part]
    return current
