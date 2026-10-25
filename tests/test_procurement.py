import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend import procurement
from backend.engine import Economy
from backend.forks import build_comparison
from backend.ledger import LedgerError
from backend.main import create_app
from backend.procurement import DemoSupplyModel
from backend.supply_policy import supplier_facts


def contract(source, transaction_id="down", contract_id="invoice", **changes):
    params = {"buyer_id": "business_1", "supplier_id": "business_2", "quantity": 20,
              "unit_price_cents": 500, "down_payment_bps": 2000, "due_in_ticks": 2, **changes}
    return source.create_contract(transaction_id, contract_id, **params)


def test_delivery_creates_inventory_trade_credit_and_balanced_down_payment():
    source = Economy.create("test")
    before = source.metrics()
    buyer_cash = source.ledger.balance("business_1:deposit")
    bank_reserves = source.ledger.balance("bank_1:reserves")
    created = contract(source)
    invoice = created["contract"]
    assert invoice["total_cents"] == 10_000 and invoice["outstanding_cents"] == 8000
    assert source.ledger.balance("business_1:deposit") == buyer_cash - 2000
    assert source.ledger.balance("bank_1:reserves") == bank_reserves - 2000
    assert source.ledger.balance("business_1:payable_invoice") == source.ledger.balance("business_2:receivable_invoice") == 8000
    assert source.material_cost("business_1") == 10_000
    assert source.state["entities"]["business_1"]["materials_units"] == 1020
    assert source.state["entities"]["business_2"]["materials_units"] == 980
    assert source.metrics()["total_deposits_cents"] == before["total_deposits_cents"]
    assert source.metrics()["total_bank_reserves_cents"] == before["total_bank_reserves_cents"]
    state = deepcopy(source.state)
    assert contract(source)["receipt"] == created["receipt"]
    assert source.state == state
    source.audit()


def test_balance_payment_extinguishes_claim_without_second_revenue_or_delivery():
    source = Economy.create("test")
    contract(source)
    equity = source.ledger.sheet("business_2")["equity_cents"]
    stock = source.state["entities"]["business_1"]["materials_units"]
    receipt = source.pay_contract("balance", "invoice")
    assert source.state["contracts"]["invoice"]["status"] == "paid"
    assert source.ledger.balance("business_1:payable_invoice") == source.ledger.balance("business_2:receivable_invoice") == 0
    assert source.ledger.sheet("business_2")["equity_cents"] == equity
    assert source.state["entities"]["business_1"]["materials_units"] == stock
    assert source.pay_contract("balance", "invoice") == receipt
    with pytest.raises(LedgerError):
        source.pay_contract("second-balance", "invoice")
    source.audit()


def test_failed_contract_creation_is_fully_atomic_including_accounts_and_inventory():
    source = Economy.create("test")
    before = deepcopy(source.state)
    with pytest.raises(LedgerError, match="Insufficient"):
        contract(source, unit_price_cents=10**9)
    assert source.state == before
    with pytest.raises(LedgerError, match="stock"):
        contract(source, quantity=1001)
    assert source.state == before


def test_material_cost_basis_transfers_and_is_expensed_on_consumption():
    source = Economy.create("test")
    contract(source)
    stock = source.state["entities"]["business_1"]["materials_units"]
    old_cost = source.material_cost("business_1")
    sold_cost = old_cost * 20 // stock
    contract(source, "resale", "resale_invoice", buyer_id="business_3", supplier_id="business_1", unit_price_cents=600)
    assert source.material_cost("business_1") == old_cost - sold_cost
    assert source.material_cost("business_3") == 12_000
    business = source.state["entities"]["business_1"]
    before_cost = source.material_cost("business_1")
    used_cost = before_cost * len(business["employees"]) // business["materials_units"]
    source.state["tick"] = 1
    source.material_consumption(business)
    assert source.material_cost("business_1") == before_cost - used_cost
    source.audit()


def test_due_tick_settles_once_and_default_writes_off_supplier_and_bank_claims():
    source = Economy.create("test")
    source.loan("working-capital", "business_1", 1000)
    contract(source, due_in_ticks=1)
    cash = source.ledger.balance("business_1:deposit")
    source.pay("drain", "business_1", "business_3", cash)
    source.state["tick"] = 1
    source.settle_due_contracts()
    assert source.state["contracts"]["invoice"]["status"] == "overdue"
    source.settle_due_contracts()
    assert source.state["contracts"]["invoice"]["missed_payment_ticks"] == 1
    source.state["tick"] = 2
    source.settle_due_contracts()
    invoice = source.state["contracts"]["invoice"]
    assert invoice["status"] == "defaulted" and invoice["written_off_cents"] == 8000
    assert source.state["entities"]["business_1"]["status"] == "defaulted"
    assert source.ledger.balance("business_1:loan") == 0
    assert source.ledger.balance("business_2:receivable_invoice") == 0
    assert source.audit()["supplier_counterparties_match"]


def test_closed_supplier_can_collect_existing_receivable():
    source = Economy.create("test")
    contract(source)
    source.default_business(source.customer("business_2"), "Supplier closes")
    source.pay_contract("wind-down-collection", "invoice")
    assert source.state["contracts"]["invoice"]["status"] == "paid"
    source.audit()


def test_forks_copy_contracts_and_settle_without_changing_source():
    source = Economy.create("test")
    contract(source, due_in_ticks=1)
    before = deepcopy(source.state)
    report, branches = build_comparison(source, "fork_trade", {"request_id": "test", "bank_id": "bank_1", "budget_cents": 1000, "ticks": 1})
    assert all(branch.state["contracts"]["invoice"]["status"] == "paid" for branch in branches)
    assert all(branch["audit"]["supplier_counterparties_match"] for branch in report["branches"])
    assert source.state == before


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "suppliers.sqlite3")) as instance:
        yield instance


def setup(client, businesses=8):
    world = client.post("/api/worlds", json={"businesses": businesses}).json()
    base = f"/api/worlds/{world['simulation_id']}"
    return base, base + "/businesses/business_1/procurement-runs"


def request(**changes):
    return {"request_id": "suppliers-1", "mode": "demo", "supplier_ids": None,
            "quantity": 20, "max_total_cents": 100_000, "auto_settle": False, **changes}


def test_two_offers_counteroffer_selection_contract_and_due_payment(client):
    base, endpoint = setup(client)
    before = client.get(base).json()
    report = client.post(endpoint, json=request()).json()
    assert report["status"] == "ready"
    assert len(report["supplier_ids"]) == 2 and len(report["offers"]) == 3
    assert report["negotiation"]["status"] == "accepted"
    assert client.get(base).json() == before
    assert client.post(endpoint, json=request()).json() == report
    result = client.post(f"/api/procurement-runs/{report['run_id']}/settle", json={"transaction_id": "contract-1"})
    assert result.status_code == 200
    created = result.json()
    assert created["contract"]["outstanding_cents"] > 0
    assert any(e["kind"] == "trade_credit" for e in client.get(base + "/network").json()["exposures"])
    contract_url = base + "/contracts/" + created["contract"]["contract_id"]
    assert client.get(contract_url).json()["status"] == "open"
    client.post(base + "/step", json={"ticks": created["contract"]["due_tick"]})
    assert client.get(contract_url).json()["status"] == "paid"
    assert client.get(base + "/audit").json()["supplier_counterparties_match"]
    assert len(client.get(endpoint).json()) == 1


def test_auto_creation_retries_once_and_insufficient_budget_declines(client):
    base, endpoint = setup(client)
    report = client.post(endpoint, json=request(auto_settle=True)).json()
    assert report["status"] == "contracted"
    before = client.get(base).json()
    assert client.post(endpoint, json=request(auto_settle=True)).json() == report
    assert client.get(base).json() == before
    declined = client.post(endpoint, json=request(request_id="no-budget", max_total_cents=1, auto_settle=True)).json()
    assert declined["status"] == "declined" and declined["contract_id"] is None
    assert client.get(base).json() == before


def test_stale_supplier_selection_cannot_be_settled(client):
    base, endpoint = setup(client)
    report = client.post(endpoint, json=request()).json()
    client.post(base + "/step", json={"ticks": 1})
    before = client.get(base).json()
    result = client.post(f"/api/procurement-runs/{report['run_id']}/settle", json={"transaction_id": "stale"})
    assert result.status_code == 409 and "changed" in result.json()["detail"]
    assert client.get(base).json() == before


def test_concurrent_creation_and_atomic_rollback(client):
    base, endpoint = setup(client)
    report = client.post(endpoint, json=request()).json()
    store = client.app.state.store
    before = client.get(base).json()
    with store.connection() as connection:
        connection.execute("CREATE TRIGGER fail_supply BEFORE INSERT ON procurement_settlements BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.settle_procurement(report["run_id"], "atomic")
    assert client.get(base).json() == before
    with store.connection() as connection:
        connection.execute("DROP TRIGGER fail_supply")
    def settle(_):
        return client.post(f"/api/procurement-runs/{report['run_id']}/settle", json={"transaction_id": "atomic"})
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(settle, range(4)))
    assert all(result.status_code == 200 for result in results)
    assert len(client.get(base + "/contracts").json()) == 1
    assert store.procurement_error(report["run_id"], "late error")["status"] == "contracted"
    reopened = create_app(store.path).state.store
    assert reopened.get_procurement(report["run_id"])["status"] == "contracted"


def model_call(name, args):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": "test-call", "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)}}]}


class ScriptedModel:
    provider = "offline_test"
    model = "mock-Nemotron"

    def __init__(self, steps):
        self.steps = iter(steps)

    def complete(self, messages, tools):
        return next(self.steps)


def test_model_cannot_accept_invalid_counteroffer_or_invent_selected_offer(client, monkeypatch):
    base, endpoint = setup(client)
    simulation_id = client.get(base).json()["simulation_id"]
    facts = supplier_facts(client.app.state.store.get(simulation_id), "business_1", "business_2", 20)
    buyer = ScriptedModel([model_call("select_offer", {"offer_id": "invented", "rationale": "Blind choice"}),
        model_call("inspect_offers", {}), model_call("negotiate_offer", {"supplier_id": "business_2", "unit_price_cents": 1,
            "down_payment_bps": 1000, "due_in_ticks": 30, "rationale": "Try lower terms"}),
        model_call("inspect_offers", {}), model_call("select_offer", {"offer_id": "invented", "rationale": "Invalid"}),
        model_call("select_offer", {"offer_id": "offer:business_2:1", "rationale": "Use the original eligible quote"})])
    supplier = ScriptedModel([model_call("inspect_supplier", {}), model_call("quote_offer", {
        "unit_price_cents": facts["reference_unit_price_cents"], "down_payment_bps": 5000, "due_in_ticks": 3, "rationale": "Original terms"}),
        model_call("inspect_counteroffer", {}), model_call("accept_counteroffer", {"rationale": "Invalid acceptance"}),
        model_call("decline_offer", {"rationale": "Outside the policy floor"})])
    monkeypatch.setattr(procurement, "supply_models", lambda body, ids: {"buyer": buyer, "business_2": supplier, "business_3": DemoSupplyModel()})
    report = client.post(endpoint, json=request(mode="live")).json()
    assert report["status"] == "ready" and report["negotiation"]["status"] == "declined"
    assert len(report["offers"]) == 2
    assert sum(step["status"] == "rejected" for step in report["trace"]) == 3
    assert report["selected_offer"]["offer_id"] == "offer:business_2:1"


def test_missing_credentials_input_validation_and_legacy_stock(client, monkeypatch):
    base, endpoint = setup(client)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_MODEL", raising=False)
    assert client.post(endpoint, json=request(mode="live")).status_code == 503
    for patch in [{"supplier_ids": ["business_2", "business_2"]}, {"quantity": True}, {"quantity": 0}, {"max_total_cents": 0}, {"auto_settle": 1}]:
        assert client.post(endpoint, json=request(**patch)).status_code == 422
    assert client.post(endpoint, json=request(supplier_ids=["business_1", "business_2"])).status_code == 409
    assert client.post(endpoint, json=request(supplier_ids=["missing", "business_2"])).status_code == 404
    small_base, small_endpoint = setup(client, businesses=2)
    assert client.post(small_endpoint, json=request()).status_code == 409
    simulation_id = client.get(base).json()["simulation_id"]
    def legacy_stock(source):
        for entity in source.state["entities"].values():
            entity.pop("materials_units", None)
    client.app.state.store.mutate(simulation_id, legacy_stock)
    report = client.post(endpoint, json=request()).json()
    assert report["status"] == "declined" and not report["offers"]


def test_malformed_supplier_response_fails_without_financial_changes(client, monkeypatch):
    base, endpoint = setup(client)
    before = client.get(base).json()
    monkeypatch.setattr(procurement, "supply_models", lambda body, ids: {"buyer": DemoSupplyModel(),
        **{supplier_id: ScriptedModel([{"tool_calls": ["invalid"]}]) for supplier_id in ids}})
    report = client.post(endpoint, json=request(mode="live")).json()
    assert report["status"] == "failed" and report["error"]
    assert client.get(base).json() == before
