import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.engine import Economy
from backend.forks import build_comparison, snapshot_hash
from backend.ledger import LedgerError
from backend.main import create_app
from backend.store import Store


def source_world():
    world = Economy.create("source", scenario="credit_crunch")
    world.shock("shock-before-fork", "bank_1")
    return world


def parameters(**changes):
    return {"request_id": "compare-1", "bank_id": "bank_1", "budget_cents": 1_000_000,
            "ticks": 12, **changes}


def test_bank_lending_creates_matching_claim_without_injecting_equity():
    world = source_world()
    before = world.ledger.sheet("bank_1")
    deposits = world.metrics()["total_deposits_cents"]
    receipt = world.intervene("rescue-1", "bank_lending", 1_000_000, "bank_1")
    after = world.ledger.sheet("bank_1")
    assert after["equity_cents"] == before["equity_cents"]
    assert after["assets"]["reserves"] == before["assets"]["reserves"] + 1_000_000
    assert after["liabilities"]["central_bank_debt"] == 1_000_000
    assert world.ledger.balance("central_bank:public_loan_bank_1") == 1_000_000
    assert world.metrics()["total_deposits_cents"] == deposits
    assert world.bank_health("bank_1")["status"] == "insolvent"
    assert world.metrics()["fiscal_transfer_cost_cents"] == 0
    state = deepcopy(world.state)
    assert world.intervene("rescue-1", "bank_lending", 1_000_000, "bank_1") == receipt
    assert world.state == state
    with pytest.raises(LedgerError, match="different contents"):
        world.intervene("rescue-1", "bank_lending", 2_000_000, "bank_1")
    assert world.state == state
    world.audit()


@pytest.mark.parametrize("amount", [1, 43, 1_000_003])
def test_household_support_distributes_every_cent_and_records_public_debt(amount):
    world = source_world()
    before = world.metrics()
    cash = {e["id"]: world.ledger.balance(e["deposit_account"])
            for e in world.state["entities"].values() if e["kind"] == "household"}
    world.intervene("cash-1", "household_cash", amount)
    allocations = [world.ledger.balance(f"{key}:deposit") - value for key, value in cash.items()]
    assert sum(allocations) == amount
    assert max(allocations) - min(allocations) <= 1
    metrics = world.metrics()
    assert metrics["household_cash_cents"] == before["household_cash_cents"] + amount
    assert metrics["total_deposits_cents"] == before["total_deposits_cents"] + amount
    assert metrics["total_bank_reserves_cents"] == before["total_bank_reserves_cents"] + amount
    assert metrics["fiscal_transfer_cost_cents"] == amount
    assert metrics["public_support_disbursed_cents"] == amount
    assert metrics["public_loan_outstanding_cents"] == amount
    assert world.ledger.sheet("government")["equity_cents"] == -amount
    assert world.ledger.balance("government:central_bank_debt") == amount
    assert world.ledger.balance("central_bank:issued_reserves") == amount
    world.audit()


def test_public_lending_audit_and_network_include_both_borrowers():
    world = source_world()
    world.intervene("bank", "bank_lending", 100, "bank_1")
    world.intervene("cash", "household_cash", 200)
    assert world.metrics()["public_support_disbursed_cents"] == 300
    assert world.metrics()["fiscal_transfer_cost_cents"] == 200
    assert world.metrics()["public_loan_outstanding_cents"] == 300
    loans = [e for e in world.network()["exposures"] if e["kind"] == "public_loan"]
    assert {e["borrower_id"] for e in loans} == {"government", "bank_1"}
    world.audit()
    world.ledger.post("corrupt-claim", [("bank_1:central_bank_debt", -1), ("bank_1:equity", 1)])
    with pytest.raises(LedgerError, match="Public loan"):
        world.audit()


def test_comparison_is_isolated_matched_and_audited():
    world = source_world()
    before = deepcopy(world.state)
    expected_baseline = Economy(world.state)
    expected_baseline.step(12)
    result, branches = build_comparison(world, "fork_test", parameters())
    assert world.state == before
    assert result["snapshot_sha256"] == snapshot_hash(before)
    assert result["initial_metrics"] == world.metrics()
    assert branches[0].ledger.state == expected_baseline.ledger.state
    assert result["branches"][0]["metrics"] == expected_baseline.metrics()
    assert result["source_tick"] == 0 and result["end_tick"] == 12
    assert result["source_event_sequence"] == len(before["events"])
    for summary, branch in zip(result["branches"], branches):
        assert [point["simulation_tick"] for point in summary["timeline"]] == list(range(13))
        assert summary["audit"]["public_counterparties_match"]
        assert branch.state["seed"] == world.state["seed"]
        assert branch.state["lineage"]["snapshot_sha256"] == result["snapshot_sha256"]
        assert all(event["simulation_id"] == branch.state["simulation_id"] for event in branch.state["events"])
    assert result["branches"][0]["metrics"]["public_support_disbursed_cents"] == 0
    assert result["branches"][1]["metrics"]["public_support_disbursed_cents"] == 1_000_000
    assert result["branches"][2]["metrics"]["public_support_disbursed_cents"] == 1_000_000
    assert "not AI" in result["recommendation_basis"]
    original = deepcopy(branches[0].state)
    branches[1].step()
    assert branches[0].state == original
    assert world.state == before


def test_fork_replays_from_nonzero_tick_without_resetting_or_reshocking():
    source = source_world()
    source.step(3)
    first, worlds = build_comparison(source, "fork_a", parameters(ticks=4))
    second, _ = build_comparison(source, "fork_b", parameters(ticks=4))
    assert first["source_tick"] == 3 and first["end_tick"] == 7
    assert [b["timeline"] for b in first["branches"]] == [b["timeline"] for b in second["branches"]]
    assert all(len([e for e in world.state["events"] if e["event_type"] == "bank_asset_loss"]) == 1
               for world in worlds)


@pytest.mark.parametrize("seed", [1, 7, 99])
def test_matched_comparisons_audit_across_different_seeds(seed):
    source = Economy.create("source", seed=seed, households=12, businesses=3, banks=3,
                            scenario="credit_crunch")
    source.shock("shock", "bank_1")
    before = deepcopy(source.state)
    first, _ = build_comparison(source, "fork_first", parameters(ticks=6, budget_cents=10_003))
    second, _ = build_comparison(source, "fork_replay", parameters(ticks=6, budget_cents=10_003))
    assert [b["timeline"] for b in first["branches"]] == [b["timeline"] for b in second["branches"]]
    assert all(b["audit"]["balanced"] for b in first["branches"])
    assert source.state == before


def test_healthy_world_can_recommend_no_support_and_inherits_prior_public_costs():
    source = Economy.create("source", households=8, businesses=2, banks=2)
    source.intervene("prior-support", "household_cash", 123)
    result, _ = build_comparison(source, "fork_healthy", parameters(ticks=1, budget_cents=1000))
    assert result["recommended_strategy"] == "no_intervention"
    assert [b["metrics"]["public_support_disbursed_cents"] for b in result["branches"]] == [123, 1123, 1123]
    assert result["branches"][1]["delta_vs_no_intervention"]["public_support_disbursed_cents"] == 1000


def test_fork_api_retry_restart_and_immutable_report(tmp_path):
    path = tmp_path / "forks.sqlite3"
    with TestClient(create_app(path)) as client:
        world = client.post("/api/worlds", json={"scenario": "credit_crunch"}).json()
        base = f"/api/worlds/{world['simulation_id']}"
        client.post(base + "/shocks", json={"transaction_id": "shock", "bank_id": "bank_1"})
        before = client.get(base).json()
        response = client.post(base + "/forks", json=parameters())
        assert response.status_code == 200
        result = response.json()
        assert client.get(base).json() == before
        assert client.post(base + "/forks", json=parameters()).json() == result
        assert client.post(base + "/forks", json=parameters(ticks=1)).status_code == 409
        assert len(client.get(base + "/forks").json()) == 1
        branch_id = result["branches"][1]["simulation_id"]
        assert client.get(f"/api/worlds/{branch_id}").json()["lineage"]["fork_id"] == result["fork_id"]
        assert client.post(f"/api/worlds/{branch_id}/step", json={"ticks": 1}).status_code == 200
        assert client.get(f"/api/forks/{result['fork_id']}").json() == result
    with TestClient(create_app(path)) as restarted:
        assert restarted.get(f"/api/forks/{result['fork_id']}").json() == result
        assert restarted.post(base + "/forks", json=parameters()).json() == result


def test_concurrent_fork_retries_publish_only_one_set(tmp_path):
    store = Store(tmp_path / "concurrent.sqlite3")
    world = source_world()
    store.create(world)
    request = parameters(ticks=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.fork("source", request), range(2)))
    assert results[0] == results[1]
    with store.connection() as connection:
        assert connection.execute("SELECT count(*) FROM worlds").fetchone()[0] == 4
        assert connection.execute("SELECT count(*) FROM forks").fetchone()[0] == 1
        snapshot = json.loads(connection.execute("SELECT snapshot FROM forks").fetchone()[0])
    assert snapshot == world.state


def test_failure_during_publication_rolls_back_all_branch_worlds(tmp_path):
    store = Store(tmp_path / "atomic.sqlite3")
    world = source_world()
    store.create(world)
    with store.connection() as connection:
        connection.execute("""CREATE TRIGGER fail_second_branch BEFORE INSERT ON worlds
            WHEN NEW.id LIKE '%_bank_lending'
            BEGIN SELECT RAISE(ABORT, 'simulated publication failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="publication failure"):
        store.fork("source", parameters(ticks=1))
    with store.connection() as connection:
        assert connection.execute("SELECT count(*) FROM worlds").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM forks").fetchone()[0] == 0
    assert store.get("source").state == world.state


def test_intervention_api_validation_idempotency_and_errors(tmp_path):
    with TestClient(create_app(tmp_path / "validation.sqlite3")) as client:
        world = client.post("/api/worlds", json={}).json()
        base = f"/api/worlds/{world['simulation_id']}"
        body = {"transaction_id": "support", "kind": "household_cash", "amount_cents": 101}
        result = client.post(base + "/interventions", json=body)
        assert result.status_code == 200
        assert client.post(base + "/interventions", json=body).json() == result.json()
        assert client.post(base + "/interventions", json={**body, "amount_cents": 102}).status_code == 409
        for change in [{"kind": "unknown"}, {"amount_cents": True}, {"amount_cents": 0},
                       {"kind": "bank_lending"}, {"bank_id": "bank_1"}, {"transaction_id": "fork:reserved"}]:
            assert client.post(base + "/interventions", json={**body, **change}).status_code == 422
        bad_bank = {**body, "transaction_id": "badbank", "kind": "bank_lending", "bank_id": "government"}
        assert client.post(base + "/interventions", json=bad_bank).status_code == 409
        for change in [{"ticks": 0}, {"ticks": 101}, {"budget_cents": 0}, {"budget_cents": True}]:
            assert client.post(base + "/forks", json=parameters(**change)).status_code == 422
        assert client.post(base + "/forks", json=parameters(bank_id="missing")).status_code == 404
        assert client.post(base + "/forks", json=parameters(bank_id="government")).status_code == 409
        assert client.get("/api/forks/missing").status_code == 404
