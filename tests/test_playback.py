import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request as HTTPRequest

from backend.engine import Economy
from backend.ledger import LedgerError
from backend.main import create_app
from backend.store import Store
from backend.streaming import stream_events


@pytest.fixture
def store(tmp_path):
    instance = Store(tmp_path / "playback.sqlite3")
    instance.create(Economy.create("world", seed=7, households=8, businesses=2, banks=2))
    return instance


def test_concurrent_schedulers_tick_once_and_preserve_determinism(store):
    expected = store.get("world")
    expected.step(3)
    store.control_playback("world", "running", 1000, now=10)
    assert store.advance_due(now=10.9) == 0
    for now in (11, 12, 13):
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(lambda _: store.advance_due(now=now), range(4))) == 1
    assert store.get("world").state == expected.state
    assert store.world_view("world")["status"] == "running"
    with pytest.raises(LedgerError, match="Pause"):
        store.step_paused("world", 1)
    store.control_playback("world", "paused", now=13)
    assert store.advance_due(now=100) == 0
    assert store.step_paused("world", 1)["simulation_tick"] == 4


def test_play_retries_speed_change_and_restarts(store):
    store.control_playback("world", "running", 1000, now=10)
    store.control_playback("world", "running", 1000, now=10.9)
    assert store.advance_due(now=11) == 1
    store.control_playback("world", "running", 250, now=11)
    restarted = Store(store.path)
    assert restarted.advance_due(now=11.25) == 1
    # A long server outage advances one tick on return, with no catch-up burst.
    assert restarted.advance_due(now=1000) == 1
    assert restarted.advance_due(now=1000) == 0
    assert restarted.playback_status("world")["interval_ms"] == 250


def test_failed_tick_rolls_back_and_pauses(store, monkeypatch):
    before = store.get("world").state
    original = Economy.step
    def fail(world, ticks=1):
        original(world, ticks)
        raise RuntimeError("private diagnostic")
    monkeypatch.setattr(Economy, "step", fail)
    store.control_playback("world", "running", 1000, now=10)
    assert store.advance_due(now=11) == 0
    assert store.get("world").state == before
    status = store.playback_status("world")
    assert status["status"] == "paused"
    assert "rolled back" in status["error"]
    assert "private diagnostic" not in status["error"]


def test_reset_is_atomic_retry_safe_and_preserves_history(store):
    store.step_paused("world", 2)
    before = store.get("world").state
    store.control_playback("world", "running", 1000, now=10)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.reset_world("world", "reset-1"), range(4)))
    assert all(result == results[0] for result in results)
    target = results[0]["simulation_id"]
    assert target != "world"
    fresh = store.get(target)
    assert fresh.state == Economy.create(target, **before["config"]).state
    assert store.get("world").state == before
    assert store.playback_status("world")["status"] == "paused"
    assert store.playback_status(target)["status"] == "paused"
    assert store.advance_due(now=20) == 0
    assert store.reset_world("world", "reset-2")["simulation_id"] != target


def test_reset_failure_does_not_pause_or_publish(store, monkeypatch):
    store.control_playback("world", "running", 1000, now=10)
    def fail(*args, **kwargs):
        raise RuntimeError("creation failed")
    monkeypatch.setattr(Economy, "create", fail)
    with pytest.raises(RuntimeError):
        store.reset_world("world", "reset-1")
    assert store.playback_status("world")["status"] == "running"
    with store.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM worlds").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM resets").fetchone()[0] == 0


def test_sse_order_reconnect_heartbeat_and_disconnect(store):
    class Request:
        disconnected = False
        async def is_disconnected(self):
            return self.disconnected
    async def exercise():
        request = Request()
        stream = stream_events(request, store, "world", 0)
        first = await anext(stream)
        assert "event: economy_event\n" in first
        event = json.loads(first.split("data: ", 1)[1])
        assert event["sequence"] == 1 and event["simulation_id"] == "world"
        await stream.aclose()
        store.step_paused("world", 1)
        stream = stream_events(request, store, "world", 1)
        second = await anext(stream)
        assert second.startswith("id: 2\n")
        await stream.aclose()
        latest = len(store.get("world").state["events"])
        stream = stream_events(request, store, "world", latest)
        assert await anext(stream) == ": heartbeat\n\n"
        await stream.aclose()
        request.disconnected = True
        stream = stream_events(request, store, "world", latest)
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
    asyncio.run(exercise())


def test_controls_validation_and_real_background_runner(tmp_path):
    with TestClient(create_app(tmp_path / "api.sqlite3")) as client:
        world = client.post("/api/worlds", json={"households": 8, "businesses": 2, "banks": 2}).json()
        base = f"/api/worlds/{world['simulation_id']}"
        assert client.get(base + "/playback").json()["status"] == "paused"
        for value in (0, 249, 10001, True, 250.5):
            assert client.post(base + "/play", json={"interval_ms": value}).status_code == 422
        assert client.post(base + "/play", json={"interval_ms": 250}).status_code == 200
        assert client.get(base).json()["status"] == "running"
        assert client.post(base + "/step", json={"ticks": 1}).status_code == 409
        deadline = time.monotonic() + 5
        while client.get(base).json()["simulation_tick"] == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert client.get(base).json()["simulation_tick"] > 0
        assert client.post(base + "/pause").json()["status"] == "paused"
        paused = client.get(base).json()
        time.sleep(0.35)
        assert client.get(base).json() == paused
        assert client.get(base + "/audit").json()["balanced"]
        reset = client.post(base + "/reset", json={"request_id": "ui-reset"}).json()
        assert client.get(f"/api/worlds/{reset['simulation_id']}").json()["simulation_tick"] == 0
        assert client.get(base + "/events/stream?after=999999").status_code == 409
        for cursor in ("-1", "abc", "1.2", "999999999999999999999"):
            assert client.get(base + "/events/stream", headers={"Last-Event-ID": cursor}).status_code == 422
        assert client.get("/api/worlds/missing/events/stream").status_code == 404
        assert client.post("/api/worlds/missing/play", json={}).status_code == 404


def test_sse_route_honors_reconnect_header_over_query(store):
    store.step_paused("world", 1)
    app = create_app(store.path)
    endpoint = next(route.endpoint for route in app.routes
                    if getattr(route, "path", "") == "/api/worlds/{simulation_id}/events/stream")
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    request = HTTPRequest({"type": "http", "headers": [(b"last-event-id", b"1")]}, receive)
    response = endpoint("world", request, after=0)
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
    async def exercise():
        assert (await anext(response.body_iterator)).startswith("id: 2\n")
        await response.body_iterator.aclose()
    asyncio.run(exercise())
