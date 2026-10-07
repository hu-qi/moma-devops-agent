"""Packaged responsive UI for the real delivery console."""

from importlib.resources import files


def get_dashboard_ui_html() -> str:
    return files("devopspilot.web").joinpath("console.html").read_text(encoding="utf-8")
