import pytest
from devopspilot.utils.model_text import (
    extract_json_payload,
    sanitize_file_content,
    strip_think_tags,
)


def test_strip_think_tags():
    raw = """<think>
Some internal reasoning about the task.
Multi-line reasoning...
</think>
Actual output content."""
    cleaned = strip_think_tags(raw)
    assert cleaned == "Actual output content."


def test_strip_unclosed_think():
    raw = "<think>\nUnclosed reasoning that got truncated mid-way"
    cleaned = strip_think_tags(raw)
    assert cleaned == ""


def test_sanitize_file_content_strips_nested_think_and_json():
    # Model mistakenly puts a JSON string inside the file content
    raw = """<think>I should write this file</think>
{
  "summary": "something",
  "files": [
    {"path": "main.py", "content": "print('hello world')"}
  ]
}"""
    cleaned = sanitize_file_content(raw, file_path="main.py")
    assert "<think>" not in cleaned
    assert "print('hello world')" in cleaned
    assert '{\n  "summary"' not in cleaned


def test_sanitize_file_content_unwraps_code_fences_for_source_files():
    raw = "```python\ndef add(a, b):\n    return a + b\n```"
    cleaned = sanitize_file_content(raw, file_path="math.py")
    assert cleaned == "def add(a, b):\n    return a + b"


def test_sanitize_file_content_preserves_fences_for_markdown():
    raw = "```python\ndef add(a, b):\n    return a + b\n```"
    cleaned = sanitize_file_content(raw, file_path="README.md")
    assert "```python" in cleaned
