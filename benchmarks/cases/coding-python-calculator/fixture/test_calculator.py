import pytest
from calculator import add, divide


def test_add():
    assert add(1.5, 2.5) == 4.0


def test_divide_normal():
    assert divide(10.0, 2.0) == 5.0


def test_divide_by_zero():
    # Expect safe fallback or ValueError, ZeroDivisionError will fail this assertion
    with pytest.raises(ValueError):
        divide(10.0, 0.0)
