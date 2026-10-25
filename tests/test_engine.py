from copy import deepcopy

import pytest

from backend.engine import Economy
from backend.ledger import Ledger, LedgerError


def make_world():
    return Economy.create("test", seed=42, households=8, businesses=2, banks=2)


def test_genesis_and_ticks_are_reproducible_and_balanced():
    first, second = make_world(), make_world()
    before = first.metrics()
    first.step(10)
    second.step(10)
    assert first.state == second.state
    assert first.audit()["bank_counterparties_match"]
    assert all(first.ledger.sheet(key)["balanced"] for key in first.state["entities"])
    assert first.metrics()["total_deposits_cents"] == before["total_deposits_cents"]
    assert first.metrics()["total_bank_reserves_cents"] == before["total_bank_reserves_cents"]
    assert {event["event_type"] for event in first.state["events"]} >= {"salary", "purchase", "tick_completed"}


def test_cross_bank_payment_moves_reserves_and_deposits():
    world = make_world()
    before_a = world.ledger.balance("bank_1:reserves")
    before_b = world.ledger.balance("bank_2:reserves")
    cash = world.ledger.balance("business_1:deposit")
    total = world.metrics()["total_deposits_cents"]
    world.pay("payment-1", "business_1", "business_2", 12345)
    assert world.ledger.balance("business_1:deposit") == cash - 12345
    assert world.ledger.balance("bank_1:reserves") == before_a - 12345
    assert world.ledger.balance("bank_2:reserves") == before_b + 12345
    assert world.metrics()["total_deposits_cents"] == total
    world.audit()


def test_same_bank_payment_does_not_move_reserves():
    world = Economy.create("test", households=2, businesses=2, banks=1)
    reserves = world.ledger.balance("bank_1:reserves")
    world.pay("same-bank", "business_1", "business_2", 123)
    assert world.ledger.balance("bank_1:reserves") == reserves
    world.audit()


def test_duplicate_payment_is_idempotent_even_after_tick_advance():
    world = make_world()
    original = world.pay("payment-1", "business_1", "business_2", 100)
    world.step()
    before = deepcopy(world.state)
    assert world.pay("payment-1", "business_1", "business_2", 100) == original
    assert world.state == before
    with pytest.raises(LedgerError, match="different contents"):
        world.pay("payment-1", "business_1", "business_2", 101)
    assert world.state == before


def test_failed_payment_is_atomic():
    world = make_world()
    before = deepcopy(world.state)
    with pytest.raises(LedgerError, match="Insufficient"):
        world.pay("too-large", "business_1", "business_2", 10**12)
    assert world.state == before


def test_loan_creates_credit_and_repayment_reverses_it():
    world = make_world()
    before = world.metrics()
    world.loan("loan-1", "business_1", 100_000)
    assert world.metrics()["total_deposits_cents"] == before["total_deposits_cents"] + 100_000
    assert world.ledger.balance("business_1:loan") == 100_000
    assert world.ledger.balance("bank_1:loan_business_1") == 100_000
    assert world.metrics()["total_bank_reserves_cents"] == before["total_bank_reserves_cents"]
    world.loan("repay-1", "business_1", 100_000, repay=True)
    assert world.metrics() == before
    world.audit()


def test_loan_limits_overpayment_and_replay():
    world = make_world()
    original = world.loan("loan-1", "business_1", 100_000)
    before = deepcopy(world.state)
    assert world.loan("loan-1", "business_1", 100_000) == original
    assert world.state == before
    with pytest.raises(LedgerError, match="credit limit"):
        world.loan("too-large", "business_1", 500_000)
    with pytest.raises(LedgerError, match="overpaid"):
        world.loan("too-much", "business_1", 100_001, repay=True)
    assert world.state == before


@pytest.mark.parametrize("amount", [True, 1.2, "100", 0, -1])
def test_invalid_payment_amount(amount):
    world = make_world()
    with pytest.raises(LedgerError):
        world.pay("invalid", "business_1", "business_2", amount)


def test_ledger_rejects_unbalanced_entries_and_detects_tampering():
    ledger = Ledger()
    cash = ledger.account("a", "cash", "asset")
    equity = ledger.account("a", "equity", "equity")
    with pytest.raises(LedgerError, match="balance"):
        ledger.post("bad", [(cash, 100)])
    assert ledger.balance(cash) == 0
    ledger.post("good", [(cash, 100), (equity, -100)])
    ledger.state["accounts"][cash]["balance"] += 1
    with pytest.raises(LedgerError, match="disagree"):
        ledger.audit()


def test_failed_salary_produces_rejection_instead_of_negative_deposit():
    world = make_world()
    world.loan("max-credit", "business_1", 500_000)
    balance = world.ledger.balance("business_1:deposit")
    world.pay("drain", "business_1", "business_2", balance)
    world.step()
    assert any(e["event_type"] == "payment_rejected" and e["details"]["purpose"] == "salary"
               for e in world.state["events"])
    world.audit()
