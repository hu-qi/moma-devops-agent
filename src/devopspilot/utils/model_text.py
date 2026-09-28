"""Utility functions for cleaning and safely extracting LLM model outputs.

Guards against reasoning/thought tags (<think>...</think>) leakage and ensures robust
JSON and file content parsing.
"""

from __future__ import annotations

import json
import re
from typing import Any


_THINK_PATTERNS = [
    re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE),
    re.compile(r"<thought>[\s\S]*?</thought>", re.IGNORECASE),
    re.compile(r"<reasoning>[\s\S]*?</reasoning>", re.IGNORECASE),
]

_TRAILING_COMMA_RE = re.compile(r",\s*([\]}])")


def strip_think_tags(text: str) -> str:
    """Remove thinking/reasoning blocks (e.g. <think>...</think>) from model outputs."""
    if not text:
        return ""

    cleaned = text
    for pattern in _THINK_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # In case the model output was truncated while still inside a <think> tag
    if "<think>" in cleaned.lower() and "</think>" not in cleaned.lower():
        idx = cleaned.lower().find("<think>")
        cleaned = cleaned[:idx]

    return cleaned.strip()


def extract_json_payload(text: str) -> dict[str, Any]:
    """Extract and parse a JSON dictionary safely from model output.

    Handles thinking tags, Markdown code fences (```json ... ```), surrounding prose,
    and trailing commas. Raises ValueError if no valid JSON dictionary can be parsed.
    """
    clean = strip_think_tags(text)

    def _parse_candidate(candidate_str: str) -> dict[str, Any] | None:
        for s in (candidate_str, _TRAILING_COMMA_RE.sub(r"\1", candidate_str)):
            try:
                v = json.loads(s, strict=False)
                if isinstance(v, dict):
                    return v
            except Exception:
                pass
        return None

    # 1. Try markdown code fences first
    if "```json" in clean:
        snippet = clean.split("```json", 1)[1].split("```", 1)[0].strip()
        parsed = _parse_candidate(snippet)
        if parsed is not None:
            return parsed

    if "```" in clean:
        parts = clean.split("```")
        for i in range(1, len(parts), 2):
            snippet = parts[i].strip()
            if snippet.lower().startswith("json"):
                snippet = snippet[4:].strip()
            parsed = _parse_candidate(snippet)
            if parsed is not None:
                return parsed

    # 2. Try greedy/balanced brace extraction
    start_brace = clean.find("{")
    end_brace = clean.rfind("}")
    if start_brace != -1 and end_brace > start_brace:
        candidate = clean[start_brace : end_brace + 1].strip()
        parsed = _parse_candidate(candidate)
        if parsed is not None:
            return parsed

    # 3. Direct attempt
    parsed = _parse_candidate(clean)
    if parsed is not None:
        return parsed

    raise ValueError("Failed to extract valid JSON payload from model response.")


def sanitize_file_content(content: str, file_path: str = "") -> str:
    """Ensure written file content does not contain thinking leakage or unintended JSON wrappers.
    
    If the target file is a source code file (e.g. .py, .go, .ts) and the content is
    accidentally wrapped inside a markdown code block (```python ... ```), automatically
    unwrap it.
    """
    stripped = strip_think_tags(content)

    # Double check if the content is an accidentally stringified JSON object with 'files' or 'summary'
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                if "files" in parsed:
                    files = parsed.get("files")
                    if isinstance(files, list) and files:
                        inner_content = files[0].get("content")
                        if isinstance(inner_content, str):
                            stripped = strip_think_tags(inner_content)
                elif "content" in parsed and isinstance(parsed["content"], str):
                    stripped = strip_think_tags(parsed["content"])
        except Exception:
            pass

    # If the file is not markdown (.md/.markdown) but wrapped in markdown code fence, unwrap it
    lower_path = file_path.lower()
    is_markdown_file = lower_path.endswith((".md", ".markdown", ".mdown", ".mkd"))
    if not is_markdown_file and stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()

    return stripped
