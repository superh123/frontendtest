from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.store import Store


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as instance:
        yield instance


def create(client):
    response = client.post("/api/worlds", json={"seed": 7, "households": 8, "businesses": 2, "banks": 2})
    assert response.status_code == 201
    return response.json()


def test_complete_frontend_workflow_and_persistence(client):
    world = create(client)
    base = f"/api/worlds/{world['simulation_id']}"
    assert len(world["entities"]) == 14
    stepped = client.post(base + "/step", json={"ticks": 3})
    assert stepped.status_code == 200
    assert stepped.json()["simulation_tick"] == 3
    assert client.get(base).json() == stepped.json()
    assert client.get(base + "/entities/business_1").json()["balance_sheet"]["balanced"]
    assert len(client.get(base + "/metrics").json()) == 4
    assert len(client.get(base + "/metrics?after_tick=1").json()) == 2
    page = client.get(base + "/events?limit=2").json()
    assert page["has_more"]
    following = client.get(base + f"/events?after={page['next_after']}&limit=2").json()
    assert following["events"][0]["sequence"] == 3
    assert client.get(base + "/audit").json()["balanced"]
    assert client.get(base + "/transactions?limit=1").json()["has_more"]
    # A fresh repository instance loads the checkpoint, rather than process memory.
    restored = Store(client.app.state.store.path).get(world["simulation_id"])
    assert restored.state["tick"] == 3
    restored.audit()


def test_payments_rollback_and_idempotency(client):
    world = create(client)
    base = f"/api/worlds/{world['simulation_id']}"
    body = {"transaction_id": "ui-payment", "payer_id": "business_1",
            "receiver_id": "business_2", "amount_cents": 100}
    first = client.post(base + "/payments", json=body)
    assert first.status_code == 200
    assert client.post(base + "/payments", json=body).json() == first.json()
    before = client.get(base).json()
    assert client.post(base + "/payments", json={**body, "amount_cents": 101}).status_code == 409
    assert client.post(base + "/payments", json={**body, "transaction_id": "poor", "amount_cents": 10**12}).status_code == 409
    assert client.get(base).json() == before
    assert client.post(base + "/payments", json={**body, "transaction_id": "missing", "payer_id": "missing"}).status_code == 404


def test_loans_and_validation(client):
    world = create(client)
    base = f"/api/worlds/{world['simulation_id']}"
    loan = {"transaction_id": "loan", "borrower_id": "business_1", "amount_cents": 1000}
    assert client.post(base + "/loans", json=loan).status_code == 200
    assert client.post(base + "/loan-repayments", json={**loan, "transaction_id": "repay"}).status_code == 200
    for config in [{"households": 0}, {"banks": -1}, {"seed": True}, {"businesses": 1.2}, {"unknown": 1}]:
        assert client.post("/api/worlds", json=config).status_code == 422
    assert client.post(base + "/step", json={"ticks": 101}).status_code == 422
    assert client.post(base + "/loans", json={**loan, "amount_cents": True}).status_code == 422
    assert client.post(base + "/loans", json={**loan, "transaction_id": "tick:1:salary:household_1"}).status_code == 422
    assert client.get("/api/worlds/missing").status_code == 404


def test_concurrent_replays_settle_exactly_once(client):
    world = create(client)
    base = f"/api/worlds/{world['simulation_id']}"
    body = {"transaction_id": "concurrent", "payer_id": "business_1",
            "receiver_id": "business_2", "amount_cents": 100}
    before = client.get(base + "/entities/business_1").json()["balance_sheet"]["assets"]["deposit"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(base + "/payments", json=body), range(8)))
    assert all(response.status_code == 200 for response in results)
    after = client.get(base + "/entities/business_1").json()["balance_sheet"]["assets"]["deposit"]
    assert before - after == 100
    assert client.get(base + "/audit").json()["balanced"]


def test_openapi_and_frontend_cors(client):
    schema = client.get("/openapi.json").json()
    assert "World" in schema["components"]["schemas"]
    response = client.options("/api/worlds", headers={"Origin": "http://localhost:5173",
                                                     "Access-Control-Request-Method": "POST"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_concurrent_distinct_payments_do_not_lose_updates(client):
    world = create(client)
    base = f"/api/worlds/{world['simulation_id']}"
    before = client.get(base + "/entities/business_1").json()["balance_sheet"]["assets"]["deposit"]
    def pay(index):
        return client.post(base + "/payments", json={"transaction_id": f"distinct-{index}",
                           "payer_id": "business_1", "receiver_id": "business_2", "amount_cents": 100})
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(pay, range(8)))
    assert all(response.status_code == 200 for response in results)
    after = client.get(base + "/entities/business_1").json()["balance_sheet"]["assets"]["deposit"]
    assert before - after == 800


def test_storage_rolls_back_whole_operation_after_partial_work(client):
    world = create(client)
    simulation_id = world["simulation_id"]
    store = client.app.state.store
    before = store.get(simulation_id).state
    def fail_after_payment(economy):
        economy.pay("rollback", "business_1", "business_2", 100)
        raise RuntimeError("Simulated failure after settlement")
    with pytest.raises(RuntimeError):
        store.mutate(simulation_id, fail_after_payment)
    assert store.get(simulation_id).state == before
