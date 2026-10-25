"""Bounded observe–test–revise agent, with persisted public decision traces."""

import json

from pydantic import ValidationError

from backend.ledger import LedgerError
from backend.models import CompareArguments, InspectArguments, RecommendArguments
from backend.provider import NebiusModel, ProviderError


TOOLS = [{"type": "function", "function": {"name": name, "description": description,
                                           "parameters": schema.model_json_schema()}}
         for name, description, schema in [
             ("inspect_economy", "Inspect the captured financial world before testing policies.", InspectArguments),
             ("compare_interventions", "Test all three strategies from the same snapshot at this budget and target bank.", CompareArguments),
             ("recommend_intervention", "Finish with a strategy from one of this run's tested comparisons and a concise public rationale.", RecommendArguments)]]


def observations(source):
    banks = []
    for entity in source.state["entities"].values():
        if entity["kind"] == "bank":
            sheet = source.ledger.sheet(entity["id"])
            banks.append({"bank_id": entity["id"], **source.bank_health(entity["id"]),
                          "equity_cents": sheet["equity_cents"], "assets_cents": sheet["assets_cents"],
                          "reserves_cents": sheet["assets"].get("reserves", 0)})
    return {"metrics": source.metrics(), "banks": banks,
            "warning": "Liquidity loans add debt; they do not restore equity. Household support may remain frozen at insolvent banks."}


def compact_comparison(result):
    return {"fork_id": result["fork_id"], "snapshot_sha256": result["snapshot_sha256"],
            "request": result["request"], "recommended_strategy": result["recommended_strategy"],
            "branches": [{"strategy": branch["strategy"], "metrics": branch["metrics"],
                          "delta_vs_no_intervention": branch["delta_vs_no_intervention"]}
                         for branch in result["branches"]]}


class DemoModel:
    provider = "deterministic_demo"
    model = "demo-policy-v1"

    def __init__(self, request):
        self.request = request

    def complete(self, messages, tools):
        results = [json.loads(message["content"]) for message in messages if message["role"] == "tool"]
        if not results:
            name, args = "inspect_economy", {}
        else:
            compared = [result for result in results if "fork_id" in result]
            if len(compared) < self.request["max_experiments"]:
                bank = min(results[0]["banks"], key=lambda item: item["capital_ratio"])["bank_id"]
                budget = max(1, self.request["budget_cap_cents"] // (2 ** len(compared)))
                name, args = "compare_interventions", {"bank_id": bank, "budget_cents": budget}
            else:
                choices = [(report, branch) for report in compared for branch in report["branches"]]
                def rank(choice):
                    metrics = choice[1]["metrics"]
                    return (-metrics["employed_households"], metrics["business_defaults"],
                            metrics["insolvent_banks"], metrics["stressed_banks"], metrics["public_support_disbursed_cents"])
                report, branch = min(choices, key=rank)
                name, args = "recommend_intervention", {
                    "fork_id": report["fork_id"], "strategy": branch["strategy"],
                    "rationale": "Deterministic demo: compare tested budgets by employment, defaults, bank stress, and gross support. This is not an AI-generated recommendation."}
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": f"demo_{len(results)}", "type": "function",
                                "function": {"name": name, "arguments": json.dumps(args)}}]}


def build_model(request):
    return DemoModel(request) if request["mode"] == "demo" else NebiusModel()


def run_agent(store, simulation_id, request):
    previous = store.find_agent(simulation_id, request)
    if previous is not None:
        return previous
    model = build_model(request)
    report, source = store.claim_agent(simulation_id, request, model)
    comparisons = {}
    inspected = False
    messages = [{"role": "system", "content":
                 "You are the central bank in a simulated economy. First inspect_economy, then compare_interventions. "
                 "You may test revised budgets/targets within the supplied cap and experiment limit. Finish with "
                 "recommend_intervention from a comparison returned in THIS run. Use only these tools. "
                 "Do not request settlement, create money, or invent results. Distinguish solvency from liquidity. "
                 "Explain the financial tradeoff briefly using observed evidence, not hidden reasoning. "
                 "Public cost means gross disbursement, not net fiscal loss. "
                 f"Limits: {json.dumps(request)}"}]
    try:
        for _ in range(10):
            message = model.complete(messages, TOOLS)
            if not isinstance(message, dict):
                raise ProviderError("Model returned an invalid tool-call message")
            calls = message.get("tool_calls")
            if not isinstance(calls, list) or not calls or len(calls) > 4:
                raise ProviderError("Model must return between one and four tool calls per turn")
            for call in calls:
                if (not isinstance(call, dict) or not isinstance(call.get("id"), str)
                        or not call["id"] or not isinstance(call.get("function"), dict)
                        or not isinstance(call["function"].get("name"), str)
                        or not isinstance(call["function"].get("arguments"), str)):
                    raise ProviderError("Model returned a malformed function-call envelope")
            # Ordered batches remain in protocol order; final recommendation
            # stops execution before any later calls can cause side effects.
            messages.append(message)
            for call in calls:
                name = call.get("function", {}).get("name", "unknown")
                arguments = {}
                try:
                    arguments = json.loads(call["function"]["arguments"])
                    if not isinstance(arguments, dict):
                        raise ValueError("Tool arguments must be an object")
                    if name == "inspect_economy":
                        InspectArguments.model_validate(arguments)
                        result = observations(source)
                        inspected = True
                    elif name == "compare_interventions":
                        args = CompareArguments.model_validate(arguments)
                        if not inspected:
                            raise LedgerError("Inspect the economy before testing an intervention")
                        if args.budget_cents > request["budget_cap_cents"]:
                            raise LedgerError("Proposed budget exceeds the run's budget cap")
                        if len(comparisons) >= request["max_experiments"]:
                            raise LedgerError("Experiment limit reached; recommend a tested strategy")
                        params = {"request_id": f"agent:{report['run_id']}:{len(comparisons)}",
                                  "bank_id": args.bank_id, "budget_cents": args.budget_cents, "ticks": request["ticks"]}
                        comparison = store.fork(simulation_id, params, source=source)
                        comparisons[comparison["fork_id"]] = comparison
                        report["comparison_ids"].append(comparison["fork_id"])
                        result = compact_comparison(comparison)
                    elif name == "recommend_intervention":
                        args = RecommendArguments.model_validate(arguments)
                        if args.fork_id not in comparisons:
                            raise LedgerError("Recommendation must reference a comparison tested in this run")
                        comparison = comparisons[args.fork_id]
                        branch = next(b for b in comparison["branches"] if b["strategy"] == args.strategy)
                        recommendation = {"fork_id": args.fork_id, "strategy": args.strategy,
                                          "bank_id": comparison["request"]["bank_id"] if args.strategy == "bank_lending" else None,
                                          "amount_cents": 0 if args.strategy == "no_intervention" else comparison["request"]["budget_cents"],
                                          "rationale": args.rationale, "metrics": branch["metrics"],
                                          "delta_vs_no_intervention": branch["delta_vs_no_intervention"]}
                        report["recommendation"] = recommendation
                        report["status"] = "completed"
                        result = recommendation
                    else:
                        raise LedgerError("Unknown tool; only inspect, compare, and recommend are allowed")
                    status = "accepted"
                except (LedgerError, ValidationError, ValueError, KeyError, TypeError, StopIteration) as error:
                    # Validation detail is useful, but do not expose provider
                    # bodies, credentials, or arbitrary exception strings.
                    status = "rejected"
                    reason = str(error) if isinstance(error, LedgerError) else (
                        "Invalid tool arguments; match the schema and use observed bank IDs and tested comparison IDs")
                    result = {"error": reason}
                    if not isinstance(arguments, dict):
                        arguments = {}
                report["trace"].append({"sequence": len(report["trace"]) + 1, "tool": name,
                                        "arguments": arguments, "status": status, "result": result})
                store.save_agent(report)
                messages.append({"role": "tool", "tool_call_id": call.get("id", "invalid"), "content": json.dumps(result)})
                if report["status"] == "completed":
                    return report
        raise ProviderError("Agent turn limit reached without a validated recommendation")
    except ProviderError as error:
        report["status"] = "failed"
        report["error"] = str(error)
        store.save_agent(report)
        return report
