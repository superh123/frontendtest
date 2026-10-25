"""Reproducible comparison of three isolated financial futures."""

import hashlib
import json

from backend import __version__

from backend.engine import Economy
from backend.ledger import LedgerError


STRATEGIES = ("no_intervention", "bank_lending", "household_cash")


def snapshot_hash(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_comparison(source, fork_id, request):
    if source.state["entities"][request["bank_id"]]["kind"] != "bank":
        raise LedgerError("Comparison bank must be a commercial bank")
    source.audit()
    digest = snapshot_hash(source.state)
    source_tick = source.state["tick"]
    branches, worlds = [], []
    for strategy in STRATEGIES:
        branch = Economy(source.state)
        branch_id = f"{fork_id}_{strategy}"
        branch.state["simulation_id"] = branch_id
        # Inherited events belong to this isolated world's history. The source
        # checkpoint itself, including its event identities, stays untouched.
        for event in branch.state["events"]:
            event["simulation_id"] = branch_id
        branch.state["lineage"] = {"fork_id": fork_id, "parent_simulation_id": source.state["simulation_id"],
                                    "source_tick": source_tick, "snapshot_sha256": digest,
                                    "strategy": strategy}
        branch.emit("world_forked", details=branch.state["lineage"].copy())
        if strategy != "no_intervention":
            branch.intervene(f"fork:{fork_id}:{strategy}", strategy, request["budget_cents"],
                             request["bank_id"] if strategy == "bank_lending" else None)
        timeline = [branch.metrics()]
        history_length = len(branch.state["history"])
        branch.step(request["ticks"])
        timeline.extend(branch.state["history"][history_length:])
        branches.append({"strategy": strategy, "simulation_id": branch_id,
                         "metrics": branch.metrics(), "timeline": timeline, "audit": branch.audit()})
        worlds.append(branch)
    baseline = branches[0]["metrics"]
    delta_fields = ("employed_households", "employment_rate", "business_defaults", "stressed_banks",
                    "insolvent_banks", "household_cash_cents", "public_support_disbursed_cents",
                    "fiscal_transfer_cost_cents", "public_loan_outstanding_cents",
                    "trade_credit_outstanding_cents", "supplier_contract_defaults")
    for branch in branches:
        branch["delta_vs_no_intervention"] = {key: branch["metrics"][key] - baseline[key] for key in delta_fields}
    def objective(branch):
        metrics = branch["metrics"]
        return (-metrics["employed_households"], metrics["business_defaults"], metrics["insolvent_banks"],
                metrics["stressed_banks"], metrics["public_support_disbursed_cents"])
    winner = min(branches, key=objective)
    tied = [branch["strategy"] for branch in branches if objective(branch) == objective(winner)]
    result = {"fork_id": fork_id, "engine_version": __version__, "source_simulation_id": source.state["simulation_id"],
              "source_tick": source_tick, "end_tick": source_tick + request["ticks"],
              "source_event_sequence": len(source.state["events"]),
              "seed": source.state["seed"], "snapshot_sha256": digest, "request": request,
              "initial_metrics": source.metrics(), "branches": branches,
              "recommended_strategy": winner["strategy"], "tied_strategies": tied,
              "recommendation_basis": "Rule-based, not AI: maximize final employment, then minimize business defaults, "
                  "insolvent banks, stressed banks, and gross public support, in that order. Exact ties use branch order. "
                  "This ranking covers this seed and horizon only.",
              "cost_definition": "Public intervention cost is gross support disbursed, not net fiscal loss. "
                  "Outstanding public loans and fiscal transfers are reported separately."}
    return result, worlds
