from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.clearing import clear_payments
from backend.engine import Economy
from backend.ledger import LedgerError
from backend.main import create_app


def test_clearing_propagates_counterparty_shortfalls():
    result = clear_payments({("a", "b"): 100, ("b", "c"): 100},
                            {"a": 40, "b": 0, "c": 0}, {})
    assert result["payments"] == {("a", "b"): 40, ("b", "c"): 40}
    assert result["iterations"] == 3


def test_clearing_protects_customer_deposits_and_never_mints_fractional_cents():
    result = clear_payments({("a", "b"): 100, ("b", "c"): 100},
                            {"a": 100, "b": 10, "c": 0}, {"a": 60, "b": 20})
    assert result["payments"] == {("a", "b"): 40, ("b", "c"): 30}
    rounded = clear_payments({("a", "b"): 1, ("a", "c"): 2},
                             {"a": 2, "b": 0, "c": 0}, {})
    assert rounded["payments"] == {("a", "b"): 0, ("a", "c"): 1}


def test_clearing_full_cyclic_netting_and_convergence_guard():
    cycle = {("a", "b"): 100, ("b", "a"): 100}
    assert clear_payments(cycle, {"a": 0, "b": 0}, {})["payments"] == cycle
    with pytest.raises(LedgerError, match="converge"):
        clear_payments({("a", "b"): 100}, {"a": 1, "b": 0}, {}, max_iterations=1)
    with pytest.raises(LedgerError, match="counterparty"):
        clear_payments({("a", "a"): 1}, {"a": 1}, {})


def test_shock_writes_down_assets_and_equity_without_destroying_deposits():
    world = Economy.create("shock", scenario="credit_crunch")
    before = world.ledger.sheet("bank_1")
    deposits = world.metrics()["total_deposits_cents"]
    reserves = world.metrics()["total_bank_reserves_cents"]
    receipt = world.shock("shock-1", "bank_1", 4000)
    loss = before["assets"]["risky_assets"] * 4000 // 10_000
    after = world.ledger.sheet("bank_1")
    assert after["assets_cents"] == before["assets_cents"] - loss
    assert after["equity_cents"] == before["equity_cents"] - loss
    assert world.metrics()["total_deposits_cents"] == deposits
    assert world.metrics()["total_bank_reserves_cents"] == reserves
    assert world.bank_health("bank_1")["status"] == "insolvent"
    state = deepcopy(world.state)
    assert world.shock("shock-1", "bank_1", 4000) == receipt
    assert world.state == state
    with pytest.raises(LedgerError, match="different contents"):
        world.shock("shock-1", "bank_1", 5000)
    assert world.state == state
    world.audit()


def test_frozen_bank_rejects_payments_and_credit_atomically():
    world = Economy.create("shock", scenario="credit_crunch")
    world.shock("shock-1", "bank_1")
    before = deepcopy(world.state)
    with pytest.raises(LedgerError, match="frozen"):
        world.pay("blocked-pay", "business_1", "household_1", 1)
    with pytest.raises(LedgerError, match="constraints"):
        world.loan("blocked-credit", "business_1", 1)
    assert world.state == before


def test_real_crisis_cascade_differs_from_unshocked_baseline_and_replays():
    baseline = Economy.create("demo", scenario="credit_crunch")
    assert baseline.metrics()["stressed_banks"] == 0
    shocked = Economy(baseline.state)
    shocked.shock("shock-1", "bank_1")
    replay = Economy(shocked.state)
    baseline.step(12)
    shocked.step(12)
    replay.step(12)
    assert replay.state == shocked.state
    assert baseline.metrics()["business_defaults"] == 0
    assert baseline.metrics()["employment_rate"] == 1
    assert shocked.metrics()["business_defaults"] > 0
    assert shocked.metrics()["employment_rate"] < baseline.metrics()["employment_rate"]
    assert any(e["event_type"] == "interbank_default" for e in shocked.state["events"])
    assert any(e["event_type"] == "credit_rejected" for e in shocked.state["events"])
    assert any(e["event_type"] == "job_lost" for e in shocked.state["events"])
    assert shocked.audit()["interbank_counterparties_match"]


def test_interbank_settlement_conserves_reserves_and_extinguishes_claims():
    world = Economy.create("demo", scenario="credit_crunch")
    world.shock("shock-1", "bank_1")
    before = world.metrics()["total_bank_reserves_cents"]
    # Isolate the settlement from household and business activity.
    world.state["tick"] = 5
    world.settle_interbank()
    liquidation = sum(line["signed_cents"] for entry in world.ledger.state["journal"]
                      if entry["metadata"]["type"] == "interbank_clearing"
                      for line in entry["lines"] if line["account_id"].endswith(":risky_assets"))
    assert world.metrics()["total_bank_reserves_cents"] == before - liquidation
    assert all(o["amount_cents"] == 0 for o in world.state["interbank_obligations"])
    journal_length = len(world.ledger.state["journal"])
    world.settle_interbank()
    assert len(world.ledger.state["journal"]) == journal_length
    world.audit()


def test_business_default_writes_off_matching_debt_and_releases_employees_once():
    world = Economy.create("demo", scenario="credit_crunch")
    business = world.state["entities"]["business_1"]
    debt = world.ledger.balance("business_1:loan")
    bank_equity = world.ledger.sheet("bank_1")["equity_cents"]
    workers = business["employees"][:]
    world.default_business(business, "test unpaid obligations")
    assert world.ledger.balance("business_1:loan") == 0
    assert world.ledger.balance("bank_1:loan_business_1") == 0
    assert world.ledger.sheet("bank_1")["equity_cents"] == bank_equity - debt
    assert all(world.state["entities"][worker]["employer_id"] is None for worker in workers)
    before = deepcopy(world.state)
    world.default_business(business, "repeat")
    assert world.state == before
    with pytest.raises(LedgerError, match="Defaulted"):
        world.loan("no-resurrection", "business_1", 1)
    world.audit()


def test_automatic_payroll_credit_and_maturity_refinancing():
    world = Economy.create("demo", households=8, businesses=2, banks=2)
    balance = world.ledger.balance("business_1:deposit")
    world.pay("drain", "business_1", "business_2", balance)
    world.step()
    assert any(e["event_type"] == "loan_issued" and e["agent_id"] == "business_1"
               for e in world.state["events"])
    world.audit()
    credit = Economy.create("demo", scenario="credit_crunch")
    credit.step(5)
    assert any(e["event_type"] == "loan_refinanced" for e in credit.state["events"])
    credit.audit()


def test_old_saved_world_remains_loadable_without_network_or_portfolio():
    # Remove the new opening operations to represent a milestone-1 checkpoint.
    world = Economy.create("legacy", banks=1)
    entry = world.ledger.state["journal"].pop()
    assert entry["metadata"]["type"] == "opening_portfolio_allocation"
    for line in entry["lines"]:
        world.ledger.state["accounts"][line["account_id"]]["balance"] -= line["signed_cents"]
    world.ledger.state["accounts"].pop("bank_1:risky_assets")
    world.state.pop("interbank_obligations")
    world.state["config"].pop("scenario")
    legacy = Economy(world.state)
    legacy.step()
    legacy.audit()
    with pytest.raises(LedgerError, match="legacy world"):
        legacy.shock("unsupported", "bank_1")


def test_crisis_api_validation_persistence_and_network(tmp_path):
    path = tmp_path / "crisis.sqlite3"
    with TestClient(create_app(path)) as client:
        created = client.post("/api/worlds", json={"scenario": "credit_crunch"})
        assert created.status_code == 201
        base = f"/api/worlds/{created.json()['simulation_id']}"
        assert client.get(base + "/network").json()["exposures"]
        body = {"transaction_id": "ui-shock", "bank_id": "bank_1", "loss_bps": 4000}
        response = client.post(base + "/shocks", json=body)
        assert response.status_code == 200
        assert client.post(base + "/shocks", json=body).json() == response.json()
        assert client.post(base + "/shocks", json={**body, "loss_bps": 5000}).status_code == 409
        for patch in [{"loss_bps": 0}, {"loss_bps": 10001}, {"loss_bps": True},
                      {"asset_category": "deposits"}, {"transaction_id": "tick:fake"}]:
            assert client.post(base + "/shocks", json={**body, **patch}).status_code == 422
        assert client.post(base + "/shocks", json={**body, "transaction_id": "unknown", "bank_id": "missing"}).status_code == 404
        assert client.post(base + "/shocks", json={**body, "transaction_id": "notbank", "bank_id": "business_1"}).status_code == 409
        result = client.post(base + "/step", json={"ticks": 12})
        assert result.status_code == 200
        assert result.json()["metrics"]["business_defaults"] > 0
        assert client.get(base + "/audit").json()["interbank_counterparties_match"]
    with TestClient(create_app(path)) as restarted:
        assert restarted.get(base).json() == result.json()
