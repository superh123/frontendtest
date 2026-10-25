import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend import credit_agents
from backend.credit_agents import DemoCreditModel
from backend.credit_policy import assess_credit, business_facts
from backend.engine import Economy
from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "credit.sqlite3")) as instance:
        yield instance


def request(**changes):
    return {"request_id": "credit-test", "mode": "demo", "max_amount_cents": 500_000,
            "auto_settle": False, **changes}


def setup(client, scenario="standard", drain=True):
    world = client.post("/api/worlds", json={"scenario": scenario}).json()
    base = f"/api/worlds/{world['simulation_id']}"
    if drain:
        cash = client.get(base + "/entities/business_1").json()["balance_sheet"]["assets"]["deposit"]
        assert client.post(base + "/payments", json={"transaction_id": "supplier-expense",
            "payer_id": "business_1", "receiver_id": "business_2", "amount_cents": cash}).status_code == 200
    return base, base + "/businesses/business_1/credit-runs"


def test_complete_request_underwrite_accept_and_settle_flow(client):
    base, endpoint = setup(client)
    before = client.get(base).json()
    result = client.post(endpoint, json=request())
    assert result.status_code == 200
    report = result.json()
    assert report["status"] == "approved" and report["business_accepted"]
    assert report["providers"] == {"business": "deterministic_demo", "bank": "deterministic_demo"}
    assert [item["tool"] for item in report["trace"]] == ["inspect_business", "request_credit", "inspect_credit",
        "assess_credit", "decide_credit", "review_offer", "accept_offer"]
    assert client.get(base).json() == before
    assert client.post(endpoint, json=request()).json() == report
    settle = f"/api/credit-runs/{report['run_id']}/settle"
    paid = client.post(settle, json={"transaction_id": "credit-manual-1"})
    assert paid.status_code == 200 and paid.json()["audit"]["balanced"]
    assert paid.json()["amount_cents"] == report["facts"]["payroll_shortfall_cents"]
    assert client.post(settle, json={"transaction_id": "credit-manual-1"}).json() == paid.json()
    assert client.post(settle, json={"transaction_id": "credit-manual-2"}).status_code == 409
    assert client.get(f"/api/credit-runs/{report['run_id']}").json()["status"] == "settled"
    client.post(base + "/step", json={"ticks": 1})
    events = client.get(base + "/events?limit=1000").json()["events"]
    wages = [event for event in events if event["event_type"] == "salary" and event["agent_id"] == "business_1"]
    assert sum(event["amount_cents"] for event in wages) == report["facts"]["payroll_cents"]


def test_auto_settlement_is_authorized_and_retry_safe(client):
    base, endpoint = setup(client)
    report = client.post(endpoint, json=request(auto_settle=True)).json()
    assert report["status"] == "settled"
    assert report["settlement"]["transaction_id"] == f"credit:{report['run_id']}"
    before = client.get(base).json()
    assert client.post(endpoint, json=request(auto_settle=True)).json() == report
    assert client.get(base).json() == before
    assert client.post(endpoint, json=request(auto_settle=False)).status_code == 409
    assert len(client.get(endpoint).json()) == 1


def test_no_shortfall_requests_no_credit_and_does_not_invoke_bank(client):
    base, endpoint = setup(client, drain=False)
    before = client.get(base).json()
    report = client.post(endpoint, json=request(auto_settle=True)).json()
    assert report["status"] == "not_requested"
    assert report["proposal"] is None and report["settlement"] is None
    assert all(item["role"] == "business" for item in report["trace"])
    assert client.get(base).json() == before


def test_insolvent_bank_declines_credit_without_mutating_balances(client):
    base, endpoint = setup(client, scenario="credit_crunch", drain=False)
    client.post(base + "/shocks", json={"transaction_id": "shock", "bank_id": "bank_1"})
    before = client.get(base).json()
    report = client.post(endpoint, json=request(auto_settle=True)).json()
    assert report["status"] == "declined"
    assert not report["decision"]["approved"]
    assert not report["decision"]["assessment"]["eligible"]
    assert report["facts"]["available_deposit_cents"] == 0
    assert client.get(base).json() == before
    assert client.post(f"/api/credit-runs/{report['run_id']}/settle", json={"transaction_id": "forbidden"}).status_code == 409


def test_business_can_reject_partial_offer_even_when_bank_approves(client):
    base, endpoint = setup(client)
    before = client.get(base).json()
    report = client.post(endpoint, json=request(max_amount_cents=1, auto_settle=True)).json()
    assert report["status"] == "declined"
    assert report["decision"]["approved"] and report["decision"]["amount_cents"] == 1
    assert report["business_accepted"] is False
    assert client.get(base).json() == before


def test_bank_counteroffers_within_remaining_credit_headroom(client):
    base, endpoint = setup(client, drain=False)
    client.post(base + "/loans", json={"transaction_id": "existing-credit", "borrower_id": "business_1", "amount_cents": 499999})
    cash = client.get(base + "/entities/business_1").json()["balance_sheet"]["assets"]["deposit"]
    client.post(base + "/payments", json={"transaction_id": "spend", "payer_id": "business_1", "receiver_id": "business_2", "amount_cents": cash})
    before = client.get(base).json()
    report = client.post(endpoint, json=request(auto_settle=True)).json()
    assert report["decision"]["assessment"]["eligible"]
    assert report["decision"]["amount_cents"] == 1 < report["proposal"]["amount_cents"]
    assert report["business_accepted"] is False
    assert client.get(base).json() == before


def test_stale_approval_cannot_settle_and_existing_id_is_rejected(client):
    base, endpoint = setup(client)
    report = client.post(endpoint, json=request()).json()
    settle = f"/api/credit-runs/{report['run_id']}/settle"
    assert client.post(settle, json={"transaction_id": "supplier-expense"}).status_code == 409
    client.post(base + "/step", json={"ticks": 1})
    before = client.get(base).json()
    response = client.post(settle, json={"transaction_id": "stale"})
    assert response.status_code == 409 and "changed" in response.json()["detail"]
    assert client.get(base).json() == before


@pytest.mark.parametrize("different_ids", [False, True])
def test_concurrent_settlement_creates_exactly_one_loan(client, different_ids):
    base, endpoint = setup(client)
    report = client.post(endpoint, json=request()).json()
    settle = f"/api/credit-runs/{report['run_id']}/settle"
    before = client.get(base).json()["metrics"]["total_loans_cents"]
    def settle_once(index):
        return client.post(settle, json={"transaction_id": f"settle-{index if different_ids else 0}"})
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(settle_once, range(4)))
    assert sum(response.status_code == 200 for response in responses) == (1 if different_ids else 4)
    assert client.get(base).json()["metrics"]["total_loans_cents"] - before == report["decision"]["amount_cents"]
    stored = client.app.state.store.credit_settlement_error(report["run_id"], "late concurrent error")
    assert stored["status"] == "settled" and stored["error"] is None


def test_credit_publication_failure_rolls_back_ledger_report_and_events(client):
    base, endpoint = setup(client)
    report = client.post(endpoint, json=request()).json()
    before = client.get(base).json()
    store = client.app.state.store
    with store.connection() as connection:
        connection.execute("CREATE TRIGGER fail_credit BEFORE INSERT ON credit_settlements BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.settle_credit(report["run_id"], "rollback-credit")
    assert client.get(base).json() == before
    assert store.get_credit(report["run_id"])["status"] == "approved"
    with store.connection() as connection:
        connection.execute("DROP TRIGGER fail_credit")
    assert store.settle_credit(report["run_id"], "rollback-credit")["audit"]["balanced"]


def test_approval_survives_restart_and_existing_maturity_is_preserved(client):
    base, endpoint = setup(client, drain=False)
    client.post(base + "/loans", json={"transaction_id": "old-loan", "borrower_id": "business_1", "amount_cents": 1000})
    client.post(base + "/step", json={"ticks": 1})
    cash = client.get(base + "/entities/business_1").json()["balance_sheet"]["assets"]["deposit"]
    client.post(base + "/payments", json={"transaction_id": "spend", "payer_id": "business_1", "receiver_id": "business_2", "amount_cents": cash})
    report = client.post(endpoint, json=request()).json()
    assert report["decision"]["assessment"]["due_tick"] == 5
    reopened = create_app(client.app.state.store.path).state.store
    assert reopened.get_credit(report["run_id"]) == report
    assert reopened.settle_credit(report["run_id"], "preserve-maturity")["due_tick"] == 5


def model_call(name, args):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": "test-call", "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)}}]}


class ScriptedModel:
    provider = "offline_test"
    model = "mock-Nemotron"

    def __init__(self, steps):
        self.steps = iter(steps)

    def complete(self, messages, tools):
        step = next(self.steps)
        return step(messages) if callable(step) else step


def test_live_role_driver_rejects_unauthorized_tools_and_untested_approvals(client, monkeypatch):
    base, endpoint = setup(client)
    simulation_id = client.get(base).json()["simulation_id"]
    gap = business_facts(client.app.state.store.get(simulation_id), "business_1")["payroll_shortfall_cents"]
    business = ScriptedModel([model_call("inspect_business", {}),
        model_call("request_credit", {"amount_cents": gap + 1, "rationale": "Too much"}),
        model_call("request_credit", {"amount_cents": gap, "rationale": "Cover wages"}),
        model_call("review_offer", {}), model_call("accept_offer", {"rationale": "The assessed offer covers wages"})])
    bank = ScriptedModel([model_call("request_credit", {}), model_call("inspect_credit", {}),
        model_call("decide_credit", {"approved": True, "amount_cents": gap, "rationale": "Not assessed yet"}),
        model_call("assess_credit", {"amount_cents": gap}),
        model_call("decide_credit", {"approved": True, "amount_cents": gap, "rationale": "Passed underwriting"})])
    monkeypatch.setattr(credit_agents, "credit_models", lambda request: {"business": business, "bank": bank})
    report = client.post(endpoint, json=request(mode="live", auto_settle=True)).json()
    assert report["status"] == "settled"
    assert sum(item["status"] == "rejected" for item in report["trace"]) == 3


def test_source_change_during_model_review_blocks_auto_settlement(client, monkeypatch):
    base, endpoint = setup(client)
    simulation_id = client.get(base).json()["simulation_id"]
    gap = business_facts(client.app.state.store.get(simulation_id), "business_1")["payroll_shortfall_cents"]
    def change_then_inspect(messages):
        client.app.state.store.mutate(simulation_id, lambda source: source.step())
        return model_call("inspect_business", {})
    business = ScriptedModel([change_then_inspect,
        model_call("request_credit", {"amount_cents": gap, "rationale": "Cover snapshot wages"}),
        model_call("review_offer", {}), model_call("accept_offer", {"rationale": "Accept tested offer"})])
    monkeypatch.setattr(credit_agents, "credit_models", lambda body: {"business": business, "bank": DemoCreditModel("bank", body)})
    report = client.post(endpoint, json=request(mode="live", auto_settle=True)).json()
    assert report["status"] == "approved" and report["settlement"] is None
    assert "changed" in report["error"]
    events = client.get(base + "/events?limit=1000").json()["events"]
    assert not any(event["event_type"] == "agent_credit_settled" for event in events)


def test_workflow_validation_missing_credentials_and_bounded_failure(client, monkeypatch):
    base, endpoint = setup(client)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_MODEL", raising=False)
    assert client.post(endpoint, json=request(mode="live")).status_code == 503
    for patch in [{"max_amount_cents": True}, {"max_amount_cents": 500001}, {"max_amount_cents": 0}, {"auto_settle": 1}]:
        assert client.post(endpoint, json=request(**patch)).status_code == 422
    assert client.post(base + "/businesses/household_1/credit-runs", json=request()).status_code == 409
    assert client.get("/api/credit-runs/missing").status_code == 404
    model = ScriptedModel([model_call("unauthorized", {})] * 8)
    monkeypatch.setattr(credit_agents, "credit_models", lambda body: {"business": model, "bank": DemoCreditModel("bank", body)})
    report = client.post(endpoint, json=request(mode="live")).json()
    assert report["status"] == "failed" and len(report["trace"]) == 8
    assert client.post(endpoint, json=request(mode="live")).json() == report


def test_post_issuance_capital_constraint_overrules_model_approval():
    source = Economy.create("policy", scenario="credit_crunch")
    cash = source.ledger.balance("business_1:deposit")
    source.pay("expense", "business_1", "business_2", cash)
    sheet = source.ledger.sheet("bank_1")
    loss = (100 * sheet["equity_cents"] - 8 * sheet["assets_cents"]) // 92
    source.ledger.post("near-threshold", [("bank_1:risky_assets", -loss), ("bank_1:equity", loss)])
    assert source.bank_health("bank_1")["lending_available"]
    amount = source.payroll(source.state["entities"]["business_1"])
    assessment = assess_credit(source, "business_1", amount)
    assert not assessment["eligible"]
    assert any("post-issuance" in reason for reason in assessment["reasons"])
    source.audit()
