"""Branding and navigation link configuration loaded strictly from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def _ensure_env_loaded() -> None:
    """Best-effort loader for .env if not yet loaded into os.environ."""
    # Offline/test guard (C01): never inject credentials into test/smoke processes
    if os.environ.get("DEVOPSPILOT_NO_DOTENV", "").strip() == "1":
        return
    candidates = [
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
        Path(__file__).resolve().parents[3] / ".env",
    ]
    for cand in candidates:
        if cand.is_file():
            try:
                for line in cand.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    if k and k not in os.environ:
                        os.environ[k] = v
                break
            except Exception:
                pass


@dataclass(frozen=True, slots=True)
class BrandConfig:
    """Configurable brand names and promotional portal URLs loaded from environment.

    No URLs are hardcoded in source. If a URL is unset or empty, it will NOT be
    rendered as a markdown hyperlink and falls back cleanly to plain text.
    """

    devopspilot_name: str = "DevOpsPilot"
    devopspilot_url: str = ""
    moma_name: str = "MoMA"
    moma_url: str = ""
    enable_links: bool = True

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> BrandConfig:
        if env is None:
            _ensure_env_loaded()
            lookup = os.environ
        else:
            lookup = env

        devops_url = (
            lookup.get("DEVOPSPILOT_URL")
            or lookup.get("DEVOPSPILOT_HOME_URL")
            or ""
        ).strip()

        moma_portal = (
            lookup.get("MOMA_URL")
            or lookup.get("MOMA_PORTAL_URL")
            or ""
        ).strip()

        enable_raw = lookup.get("DEVOPSPILOT_ENABLE_BRAND_LINKS", "true").strip().lower()
        enable_links = enable_raw in {"1", "true", "yes", "on"}

        devops_name = lookup.get("DEVOPSPILOT_BRAND_NAME", "DevOpsPilot").strip() or "DevOpsPilot"
        moma_brand = lookup.get("MOMA_BRAND_NAME", "MoMA").strip() or "MoMA"

        return cls(
            devopspilot_name=devops_name,
            devopspilot_url=devops_url,
            moma_name=moma_brand,
            moma_url=moma_portal,
            enable_links=enable_links,
        )

    @property
    def devopspilot_markdown(self) -> str:
        """Render markdown link if URL configured and links enabled; else plain text."""
        if self.enable_links and self.devopspilot_url:
            return f"[{self.devopspilot_name}]({self.devopspilot_url})"
        return self.devopspilot_name

    @property
    def moma_markdown(self) -> str:
        """Render markdown link if URL configured and links enabled; else plain text."""
        if self.enable_links and self.moma_url:
            return f"[{self.moma_name}]({self.moma_url})"
        return self.moma_name

    def format_issue_footer(self) -> str:
        return (
            "\n\n---\n"
            f"*🤖 Answer generated automatically by {self.devopspilot_markdown} "
            f"on China Mobile Cloud ({self.moma_markdown}) platform.*"
        )

    def format_pr_footer(self) -> str:
        return (
            "\n\n---\n"
            f"*Delivered by {self.devopspilot_markdown} "
            f"powered by China Mobile Cloud {self.moma_markdown}.*"
        )
