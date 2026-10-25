import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import agents
from backend.agents import DemoModel
from backend.engine import Economy
from backend.forks import snapshot_hash
from backend.main import create_app
from backend.provider import NebiusModel, ProviderError, ProviderNotConfigured


def call(name, arguments):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call-1", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}


class ScriptedModel:
    provider = "test_provider"
    model = "mock-Nemotron"

    def __init__(self, steps):
        self.steps = iter(steps)

    def complete(self, messages, tools):
        step = next(self.steps)
        return step(messages) if callable(step) else step


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "agents.sqlite3")) as instance:
        yield instance


def world(client, crisis=True):
    created = client.post("/api/worlds", json={"scenario": "credit_crunch" if crisis else "standard"}).json()
    base = f"/api/worlds/{created['simulation_id']}"
    if crisis:
        assert client.post(base + "/shocks", json={"transaction_id": "shock", "bank_id": "bank_1"}).status_code == 200
    return base


def request(**changes):
    return {"request_id": "agent-demo", "mode": "demo", "budget_cap_cents": 1_000_000,
            "ticks": 12, "max_experiments": 2, **changes}


def recommend_last(messages):
    comparisons = [json.loads(m["content"]) for m in messages if m["role"] == "tool"
                   and "fork_id" in json.loads(m["content"])]
    return call("recommend_intervention", {"fork_id": comparisons[-1]["fork_id"],
                                           "strategy": "household_cash", "rationale": "Support household liquidity using the tested allocation."})


def test_demo_observes_tests_revises_and_persists_without_touching_source(client):
    base = world(client)
    before = client.get(base).json()
    response = client.post(base + "/agent-runs", json=request())
    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "completed"
    assert report["provider"] == "deterministic_demo"
    assert [step["tool"] for step in report["trace"]] == ["inspect_economy", "compare_interventions",
                                                         "compare_interventions", "recommend_intervention"]
    assert len(report["comparison_ids"]) == 2
    assert report["recommendation"]["amount_cents"] <= 1_000_000
    assert client.get(base).json() == before
    assert client.post(base + "/agent-runs", json=request()).json() == report
    assert client.post(base + "/agent-runs", json=request(ticks=1)).status_code == 409
    assert client.get(f"/api/agent-runs/{report['run_id']}").json() == report
    assert len(client.get(base + "/agent-runs").json()) == 1
    for fork_id in report["comparison_ids"]:
        comparison = client.get(f"/api/forks/{fork_id}").json()
        assert comparison["snapshot_sha256"] == report["snapshot_sha256"]
    reopened = create_app(client.app.state.store.path)
    assert reopened.state.store.get_agent(report["run_id"]) == report


def test_apply_settles_once_and_rejects_second_transaction_id(client):
    base = world(client)
    report = client.post(base + "/agent-runs", json=request()).json()
    assert report["recommendation"]["strategy"] == "household_cash"
    before = client.get(base).json()["metrics"]
    endpoint = f"/api/agent-runs/{report['run_id']}/apply"
    result = client.post(endpoint, json={"transaction_id": "apply-1"})
    assert result.status_code == 200
    assert result.json()["audit"]["public_counterparties_match"]
    after = client.get(base).json()["metrics"]
    assert after["public_support_disbursed_cents"] - before["public_support_disbursed_cents"] == report["recommendation"]["amount_cents"]
    assert client.post(endpoint, json={"transaction_id": "apply-1"}).json() == result.json()
    assert client.post(endpoint, json={"transaction_id": "apply-2"}).status_code == 409


def test_apply_refuses_stale_snapshot(client):
    base = world(client)
    report = client.post(base + "/agent-runs", json=request(ticks=1, max_experiments=1)).json()
    client.post(base + "/step", json={"ticks": 1})
    before = client.get(base).json()
    result = client.post(f"/api/agent-runs/{report['run_id']}/apply", json={"transaction_id": "apply-stale"})
    assert result.status_code == 409 and "changed" in result.json()["detail"]
    assert client.get(base).json() == before


def test_no_intervention_application_is_audited_and_duplicate_id_is_refused(client):
    base = world(client, crisis=False)
    client.post(base + "/interventions", json={"transaction_id": "used", "kind": "household_cash", "amount_cents": 1})
    report = client.post(base + "/agent-runs", json=request(ticks=1, max_experiments=1)).json()
    assert report["recommendation"]["strategy"] == "no_intervention"
    before = client.get(base).json()["metrics"]
    endpoint = f"/api/agent-runs/{report['run_id']}/apply"
    assert client.post(endpoint, json={"transaction_id": "used"}).status_code == 409
    assert client.post(endpoint, json={"transaction_id": "no-action"}).status_code == 200
    assert client.get(base).json()["metrics"] == before


def test_live_without_credentials_never_silently_falls_back(client, monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_MODEL", raising=False)
    base = world(client)
    response = client.post(base + "/agent-runs", json=request(mode="live"))
    assert response.status_code == 503
    assert client.get(base + "/agent-runs").json() == []
    assert client.get("/api/agents/status").json()["live_configured"] is False


def test_rejected_tools_feed_back_and_live_driver_recovers(client, monkeypatch):
    model = ScriptedModel([
        call("settle_payment", {}),
        call("compare_interventions", {"bank_id": "bank_1", "budget_cents": 100}),
        call("inspect_economy", {}),
        call("compare_interventions", {"bank_id": "bank_1", "budget_cents": 1_000_001}),
        call("compare_interventions", {"bank_id": "bank_1", "budget_cents": 100_000}),
        call("recommend_intervention", {"fork_id": "invented", "strategy": "household_cash", "rationale": "Invalid evidence"}),
        recommend_last,
    ])
    monkeypatch.setattr(agents, "build_model", lambda body: model)
    base = world(client)
    before = client.get(base).json()
    report = client.post(base + "/agent-runs", json=request(mode="live")).json()
    assert report["status"] == "completed"
    assert len([item for item in report["trace"] if item["status"] == "rejected"]) == 4
    assert len(report["comparison_ids"]) == 1
    assert report["recommendation"]["amount_cents"] == 100_000
    assert client.get(base).json() == before


def test_source_may_advance_but_every_agent_trial_uses_captured_snapshot(client, monkeypatch):
    base = world(client)
    simulation_id = client.get(base).json()["simulation_id"]
    original = client.app.state.store.get(simulation_id)
    def advance_then_inspect(messages):
        client.app.state.store.mutate(simulation_id, lambda source: source.step())
        return call("inspect_economy", {})
    model = ScriptedModel([advance_then_inspect,
                           call("compare_interventions", {"bank_id": "bank_1", "budget_cents": 100_000}),
                           recommend_last])
    monkeypatch.setattr(agents, "build_model", lambda body: model)
    report = client.post(base + "/agent-runs", json=request(mode="live", ticks=1)).json()
    assert report["status"] == "completed"
    assert report["snapshot_sha256"] == snapshot_hash(original.state)
    comparison = client.get(f"/api/forks/{report['comparison_ids'][0]}").json()
    assert comparison["source_tick"] == 0
    assert comparison["snapshot_sha256"] == report["snapshot_sha256"]
    assert client.get(base).json()["simulation_tick"] == 1


@pytest.mark.parametrize("message", [{}, {"tool_calls": ["bad"]}, {"tool_calls": []}])
def test_malformed_model_calls_fail_cleanly_and_remain_inspectable(client, monkeypatch, message):
    monkeypatch.setattr(agents, "build_model", lambda body: ScriptedModel([message]))
    base = world(client)
    report = client.post(base + "/agent-runs", json=request(mode="live")).json()
    assert report["status"] == "failed" and report["recommendation"] is None
    assert report["error"]
    assert client.post(base + "/agent-runs", json=request(mode="live")).json() == report
    assert client.post(f"/api/agent-runs/{report['run_id']}/apply", json={"transaction_id": "invalid"}).status_code == 409


def test_turn_limit_bounds_rejected_actions(client, monkeypatch):
    model = ScriptedModel([call("unknown_tool", {})] * 10)
    monkeypatch.setattr(agents, "build_model", lambda body: model)
    base = world(client)
    report = client.post(base + "/agent-runs", json=request(mode="live")).json()
    assert report["status"] == "failed"
    assert len(report["trace"]) == 10
    assert not report["comparison_ids"]


def test_claim_prevents_duplicate_running_models_and_validates_inputs(client):
    base = world(client)
    simulation_id = client.get(base).json()["simulation_id"]
    report, _ = client.app.state.store.claim_agent(simulation_id, request(), DemoModel(request()))
    assert client.post(base + "/agent-runs", json=request()).status_code == 409
    assert client.get(f"/api/agent-runs/{report['run_id']}").json()["status"] == "running"
    for changes in [{"budget_cap_cents": True}, {"max_experiments": 4}, {"mode": "fake"}, {"ticks": 0}]:
        assert client.post(base + "/agent-runs", json=request(**changes)).status_code == 422


def test_provider_posts_tool_schema_without_exposing_credentials(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-secret-not-a-real-key")
    monkeypatch.setenv("NEBIUS_MODEL", "test-Nemotron-model")
    monkeypatch.delenv("NEBIUS_BASE_URL", raising=False)
    original = httpx.Client
    def handle(request):
        assert request.headers["authorization"] == "Bearer test-secret-not-a-real-key"
        body = json.loads(request.content)
        assert body["tool_choice"] == "required"
        assert "test-secret" not in json.dumps(body)
        return httpx.Response(200, json={"choices": [{"message": call("inspect_economy", {})}]})
    monkeypatch.setattr("backend.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    message = NebiusModel().complete([{"role": "system", "content": "Inspect"}], agents.TOOLS)
    assert message["tool_calls"][0]["function"]["name"] == "inspect_economy"


@pytest.mark.parametrize("invalid_base", ["http://untrusted.example/v1", "https://[invalid", "https://example.com:invalid/v1"])
def test_provider_sanitizes_upstream_errors_and_refuses_unsafe_url(monkeypatch, invalid_base):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-secret-not-a-real-key")
    monkeypatch.setenv("NEBIUS_MODEL", "test-Nemotron-model")
    monkeypatch.setenv("NEBIUS_BASE_URL", invalid_base)
    with pytest.raises(ProviderNotConfigured):
        NebiusModel()
    monkeypatch.setenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
    original = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(401, text="test-secret-not-a-real-key"))
    monkeypatch.setattr("backend.provider.httpx.Client", lambda **kwargs: original(transport=transport, **kwargs))
    with pytest.raises(ProviderError) as failure:
        NebiusModel().complete([], agents.TOOLS)
    assert "401" in str(failure.value)
    assert "test-secret" not in str(failure.value)
