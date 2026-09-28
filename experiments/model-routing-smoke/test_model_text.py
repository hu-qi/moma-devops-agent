"""Unit tests for model output stripping, JSON extraction, and content sanitization."""

import pytest
from devopspilot.utils.model_text import (
    extract_json_payload,
    sanitize_file_content,
    strip_think_tags,
)


def test_strip_think_tags_basic():
    raw = "<think>Let me analyze the problem first...</think>Hello, world!"
    assert strip_think_tags(raw) == "Hello, world!"


def test_strip_think_tags_multiline_and_case():
    raw = """<THINK>
Line 1 of thought
Line 2 of thought
</THINK>
Final response here."""
    assert strip_think_tags(raw) == "Final response here."


def test_strip_think_tags_truncated():
    raw = "<think>Still thinking and truncated..."
    assert strip_think_tags(raw) == ""


def test_extract_json_payload_with_think():
    raw = """<think>
I need to output JSON now.
</think>
{
  "summary": "Fix issue",
  "files": [
    {"path": "a.py", "content": "print('ok')"}
  ]
}"""
    parsed = extract_json_payload(raw)
    assert parsed["summary"] == "Fix issue"
    assert len(parsed["files"]) == 1
    assert parsed["files"][0]["path"] == "a.py"


def test_extract_json_payload_with_markdown_fences():
    raw = """<think>Let's do this</think>
```json
{
  "summary": "From markdown fence",
  "files": []
}
```"""
    parsed = extract_json_payload(raw)
    assert parsed["summary"] == "From markdown fence"


def test_extract_json_payload_with_trailing_commas():
    raw = """{
  "summary": "Trailing comma test",
  "files": [
    {"path": "b.txt", "content": "text",},
  ],
}"""
    parsed = extract_json_payload(raw)
    assert parsed["summary"] == "Trailing comma test"


def test_sanitize_file_content_strips_think():
    content = "<think>Thought process</think>def foo(): return 1"
    assert sanitize_file_content(content) == "def foo(): return 1"


def test_sanitize_file_content_unwraps_accidental_json():
    accidental_json = '{"files": [{"path": "README.md", "content": "# Hello World"}]}'
    assert sanitize_file_content(accidental_json) == "# Hello World"
