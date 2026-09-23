"""Sanitized MoMA OpenAI-compatible model catalog probe."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    base = required("MOMA_API_BASE").rstrip("/")
    key = required("MOMA_API_KEY")
    url = base + "/models"

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "DevOpsPilot-MoMA-Catalog-Probe",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"MoMA model catalog returned HTTP {exc.code}: "
            f"{body[:500]}"
        ) from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise RuntimeError(
            "MoMA /models response did not expose an OpenAI-compatible data list"
        )

    ids = sorted({
        str(item.get("id")).strip()
        for item in data
        if isinstance(item, dict) and item.get("id")
    })
    if not ids:
        raise RuntimeError("MoMA /models returned no model ids")

    print("MOMA_MODEL_CATALOG_OK")
    print(f"MODEL_COUNT={len(ids)}")
    for model_id in ids:
        print(f"MODEL_ID={model_id}")


if __name__ == "__main__":
    main()
