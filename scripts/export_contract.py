"""Run from the project root: python -m scripts.export_contract."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.engine import Economy
from backend.forks import build_comparison
from backend.main import app
from backend.models import Entity, EventPage, World, Network, ForkComparison
from backend.models import AgentReport, CreditReport, ProcurementReport
from backend.agents import run_agent
from backend.credit_agents import run_credit
from backend.procurement import run_procurement
from backend.store import Store


def main():
    destination = Path(__file__).resolve().parent.parent / "docs"
    destination.mkdir(exist_ok=True)
    world = Economy.create("world_example", seed=42, households=6, businesses=2, banks=2)
    world.step()
    examples = {
        "create_world_request": {"seed": 42, "households": 6, "businesses": 2, "banks": 2},
        "world_after_one_tick": World.model_validate(world.view()).model_dump(),
        "business_detail": Entity.model_validate(world.entity_view("business_1")).model_dump(),
        "events": EventPage.model_validate({"events": world.state["events"],
                                           "next_after": len(world.state["events"]),
                                           "has_more": False}).model_dump(),
        "audit": world.audit(),
    }
    baseline = Economy.create("world_crisis_example", scenario="credit_crunch")
    shocked = Economy(baseline.state)
    before_network = Network.model_validate(shocked.network()).model_dump()
    shock_request = {"transaction_id": "demo-shock-1", "bank_id": "bank_1", "loss_bps": 4000}
    receipt = shocked.shock(**shock_request)
    baseline.step(12)
    shocked.step(12)
    crisis = {"create_world_request": {"seed": 42, "scenario": "credit_crunch"},
              "shock_request": shock_request, "shock_receipt": receipt,
              "network_before": before_network,
              "baseline_metrics": baseline.metrics(), "shocked_metrics": shocked.metrics(),
              "world_after_crisis": World.model_validate(shocked.view()).model_dump(),
              "network_after": Network.model_validate(shocked.network()).model_dump(),
              "crisis_events": [event for event in shocked.state["events"]
                                if event["event_type"] in {"bank_asset_loss", "bank_status_changed",
                                  "business_default", "loan_default", "interbank_default", "job_lost"}],
              "audit": shocked.audit()}
    fork_source = Economy.create("world_fork_example", scenario="credit_crunch")
    fork_source.shock("fork-example-shock", "bank_1")
    comparison, _ = build_comparison(fork_source, "fork_example",
                                    {"request_id": "comparison-example", "bank_id": "bank_1",
                                     "budget_cents": 1_000_000, "ticks": 12})
    with TemporaryDirectory() as example_directory:
        store = Store(Path(example_directory) / "example.sqlite3")
        agent_source = Economy.create("world_agent_example", scenario="credit_crunch")
        agent_source.shock("agent-example-shock", "bank_1")
        store.create(agent_source)
        agent_example = run_agent(store, "world_agent_example",
                                  {"request_id": "example", "mode": "demo", "budget_cap_cents": 1_000_000,
                                   "ticks": 12, "max_experiments": 2})
        if agent_example["status"] != "completed":
            raise RuntimeError("Example agent failed; do not export an incomplete trace")
        # Stable illustrative IDs keep regenerated documentation readable.
        encoded = json.dumps(agent_example).replace(agent_example["run_id"], "agent_example")
        for index, fork_id in enumerate(agent_example["comparison_ids"], start=1):
            encoded = encoded.replace(fork_id, f"fork_agent_example_{index}")
        agent_example = AgentReport.model_validate(json.loads(encoded)).model_dump()
        credit_examples = {}
        for label in ("settled", "declined"):
            credit_source = Economy.create(f"world_credit_{label}_example",
                                            scenario="standard" if label == "settled" else "credit_crunch")
            if label == "settled":
                cash = credit_source.ledger.balance("business_1:deposit")
                credit_source.pay("setup-expense", "business_1", "business_2", cash)
            else:
                credit_source.shock("credit-example-shock", "bank_1")
            store.create(credit_source)
            credit_example = run_credit(store, credit_source.state["simulation_id"], "business_1",
                                         {"request_id": "credit-example", "mode": "demo",
                                          "max_amount_cents": 500_000, "auto_settle": True})
            if credit_example["status"] != label:
                raise RuntimeError(f"Expected credit example to be {label}")
            encoded = json.dumps(credit_example).replace(credit_example["run_id"], f"credit_{label}_example")
            credit_examples[label] = CreditReport.model_validate(json.loads(encoded)).model_dump()
        supply_source = Economy.create("world_procurement_example")
        store.create(supply_source)
        supply_run = run_procurement(store, "world_procurement_example", "business_1",
            {"request_id": "supplier-example", "mode": "demo", "supplier_ids": None,
             "quantity": 20, "max_total_cents": 100_000, "auto_settle": True})
        if supply_run["status"] != "contracted":
            raise RuntimeError("Supplier example did not create a contract")
        due_tick = supply_run["settlement"]["contract"]["due_tick"]
        store.mutate("world_procurement_example", lambda source: source.step(due_tick))
        completed_supply = store.get("world_procurement_example")
        supply_example = {"run": ProcurementReport.model_validate(supply_run).model_dump(),
            "contract_after_due_tick": completed_supply.state["contracts"][supply_run["contract_id"]],
            "audit_after_due_tick": completed_supply.audit(),
            "payment_events": [event for event in completed_supply.state["events"]
                               if event["event_type"] in ("supplier_down_payment", "supplier_balance_paid")]}
        supply_example = json.loads(json.dumps(supply_example).replace(supply_run["run_id"], "supply_example"))
    for name, value in [("openapi.json", app.openapi()), ("examples.json", examples),
                        ("crisis_demo.json", crisis),
                        ("fork_demo.json", ForkComparison.model_validate(comparison).model_dump()),
                        ("agent_demo.json", agent_example), ("credit_demo.json", credit_examples),
                        ("procurement_demo.json", supply_example)]:
        (destination / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote docs/{name}")


if __name__ == "__main__":
    main()
