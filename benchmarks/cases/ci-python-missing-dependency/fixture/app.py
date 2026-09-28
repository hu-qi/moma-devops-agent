try:
    import non_existent_fast_accelerator as accelerator  # type: ignore
except ImportError:
    # Defect: raises error instead of falling back to built-in pure python implementation
    raise ImportError("Required acceleration module missing")


def compute(data: list[int]) -> int:
    return sum(data)
