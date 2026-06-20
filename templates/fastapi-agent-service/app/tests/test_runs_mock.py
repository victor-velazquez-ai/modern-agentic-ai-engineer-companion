"""The run + SSE-stream paths work in MOCK mode — no API key, no spend.

These tests rely on ``COMPANION_MOCK`` defaulting to True. They use FastAPI's
``TestClient`` (no network) and assert the canned mock output flows through both
the synchronous and streaming endpoints.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    # AUTH_SECRET is unset in tests, so the auth stub allows requests through.
    return TestClient(create_app())


def test_create_run_returns_mock_output() -> None:
    client = _client()
    resp = client.post("/v1/runs", json={"input": "hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "[mock]" in body["output"]
    assert body["id"].startswith("run_")


def test_create_run_rejects_empty_input() -> None:
    client = _client()
    resp = client.post("/v1/runs", json={"input": ""})
    assert resp.status_code == 422  # Pydantic validation at the boundary.


def test_stream_run_emits_sse_events() -> None:
    client = _client()
    with client.stream(
        "GET", "/v1/runs/run_test/stream", params={"input": "hello"}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())

    # Collect the JSON payloads from each `data:` line.
    payloads = [
        json.loads(line[len("data:") :].strip())
        for line in body.splitlines()
        if line.startswith("data:")
    ]
    types = [p["type"] for p in payloads]
    assert types[0] == "start"
    assert types[-1] == "end"
    assert "token" in types

    streamed = "".join(p["token"] for p in payloads if p.get("token"))
    assert "[mock]" in streamed
