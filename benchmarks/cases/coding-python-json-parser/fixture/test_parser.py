import pytest
from parser import extract_nested_value


def test_extract_existing():
    data = {"a": {"b": {"c": 123}}}
    assert extract_nested_value(data, "a.b.c") == 123


def test_extract_missing_default():
    data = {"a": {}}
    # Unfixed code raises KeyError, fixed code should return "fallback"
    assert extract_nested_value(data, "a.b.missing", default="fallback") == "fallback"
