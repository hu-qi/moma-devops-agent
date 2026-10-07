"""Tests for DevOpsPilot Web Management Console (server, API, and UI)."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from devopspilot.web.api import register_dashboard_apis
from devopspilot.web.server import create_dashboard_server
from devopspilot.web.ui import get_dashboard_ui_html


@pytest.fixture
def dashboard_server(tmp_path: Path):
    """Run an ephemeral DashboardServer in a background thread."""
    db_file = tmp_path / "test_state.db"
    server = create_dashboard_server(
        host="127.0.0.1",
        port=0,
        db_path=db_file,
        html_provider=get_dashboard_ui_html,
    )
    register_dashboard_apis(
        server.api_router, db_path=db_file, trajectory_dir=tmp_path / "trajectories"
    )
    server.start_background()
    yield server
    server.stop()


def test_dashboard_ui_serves_html(dashboard_server):
    port = dashboard_server.server_address[1]
    url = f"http://127.0.0.1:{port}/"

    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type", "")
        body = resp.read().decode("utf-8")
        assert "DevOpsPilot" in body
        assert "Web Console" in body
        assert "DevOpsBench" in body
        assert "概览仪表盘" in body


def test_api_status_endpoint(dashboard_server):
    port = dashboard_server.server_address[1]
    url = f"http://127.0.0.1:{port}/api/status"

    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        assert "application/json" in resp.headers.get("Content-Type", "")
        assert resp.headers.get("Access-Control-Allow-Origin") is None
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "OPERATIONAL"
        assert "python_version" in data
        assert "commit_sha" in data
        assert data["counts"]["benchmark_cases"] == 24


def test_api_deliveries_empty(dashboard_server):
    port = dashboard_server.server_address[1]
    url = f"http://127.0.0.1:{port}/api/deliveries"

    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "items" in data
        assert isinstance(data["items"], list)


def test_api_rules_endpoint(dashboard_server):
    port = dashboard_server.server_address[1]
    url = f"http://127.0.0.1:{port}/api/rules"

    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["total_packs"] >= 2
        pack_ids = [p["pack_id"] for p in data["packs"]]
        assert (
            "devopspilot-industry-finance" in pack_ids
            or "devopspilot-industry-government" in pack_ids
        )


def test_api_benchmarks_endpoint(dashboard_server):
    port = dashboard_server.server_address[1]
    url = f"http://127.0.0.1:{port}/api/benchmarks"

    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["total"] == 24
        assert data["holdout_count"] == 6
        assert data["categories"]["coding"] == 8
        assert data["categories"]["code-review"] == 8
        assert data["categories"]["ci-debug"] == 8


def test_api_not_found(dashboard_server):
    port = dashboard_server.server_address[1]
    url = f"http://127.0.0.1:{port}/api/unknown_route"

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url, timeout=5)
    assert exc_info.value.code == 404


def test_api_create_delivery_validation(dashboard_server):
    port = dashboard_server.server_address[1]
    url = f"http://127.0.0.1:{port}/api/deliveries"

    # Missing repo/issue should return validation error
    req = urllib.request.Request(
        url,
        data=json.dumps({"provider": "atomgit"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["success"] is False
        assert "required" in data["error"]


def test_api_trajectory_path_traversal_blocked(dashboard_server):
    port = dashboard_server.server_address[1]
    # Attempting directory traversal should be safely rejected
    url = f"http://127.0.0.1:{port}/api/trajectories/.._.._etc_passwd"

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url, timeout=5)
    assert exc_info.value.code == 404


def test_cross_origin_delivery_write_rejected(dashboard_server):
    port = dashboard_server.server_address[1]
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/deliveries",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "Origin": "https://untrusted.example",
        },
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 403


def test_json_array_is_rejected(dashboard_server):
    port = dashboard_server.server_address[1]
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/deliveries",
        data=b"[]",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 400


@pytest.mark.parametrize(
    "endpoint", ["projects", "runtime", "jobs", "schedules", "knowledge", "chat"]
)
def test_console_navigation_api_available(dashboard_server, endpoint):
    port = dashboard_server.server_address[1]
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/api/{endpoint}", timeout=5
    ) as resp:
        assert isinstance(json.loads(resp.read()), dict)


def test_cancel_missing_worker_is_validation_error(dashboard_server):
    port = dashboard_server.server_address[1]
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/jobs/cancel",
        data=b'{"job_id":"missing"}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 400
