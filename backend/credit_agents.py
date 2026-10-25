"""Business request → bank underwriting → business acceptance → validated loan."""

import json

from pydantic import ValidationError

from backend.credit_policy import assess_credit
from backend.ledger import LedgerError
from backend.models import (InspectArguments, CreditProposal, ContinueBusiness,
                            AssessCreditArguments, BankDecision)
from backend.provider import NebiusModel, ProviderError


def tools_for(definitions):
    return [{"type": "function", "function": {"name": name, "description": description,
                                               "parameters": schema.model_json_schema()}}
            for name, description, schema in definitions]


BUSINESS_TOOLS = tools_for([
    ("inspect_business", "Observe deposits, payroll shortfall, debt, and bank health.", InspectArguments),
    ("request_credit", "Propose payroll financing within the observed gap and caller cap.", CreditProposal),
    ("continue_without_credit", "End without requesting a loan and explain why.", ContinueBusiness)])
BANK_TOOLS = tools_for([
    ("inspect_credit", "Review the business proposal and captured financial facts.", InspectArguments),
    ("assess_credit", "Test principal against deterministic lending and post-issuance constraints.", AssessCreditArguments),
    ("decide_credit", "Approve only previously assessed eligible principal, or decline with zero principal.", BankDecision)])
ACCEPTANCE_TOOLS = tools_for([
    ("review_offer", "Inspect the bank's approved offer and payroll coverage.", InspectArguments),
    ("accept_offer", "Accept the bank's exact offered principal and recorded maturity.", ContinueBusiness),
    ("decline_offer", "Reject the offer without borrowing.", ContinueBusiness)])


def tool_call(name, args, sequence):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": f"credit_demo_{sequence}", "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}]}


class DemoCreditModel:
    provider = "deterministic_demo"
    model = "demo-credit-v1"

    def __init__(self, role, request):
        self.role, self.request = role, request

    def complete(self, messages, tools):
        results = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        names = {tool["function"]["name"] for tool in tools}
        if not results:
            name = "inspect_business" if "inspect_business" in names else (
                "inspect_credit" if "inspect_credit" in names else "review_offer")
            return tool_call(name, {}, 0)
        if "request_credit" in names:
            facts = results[0]
            amount = min(self.request["max_amount_cents"], facts["payroll_shortfall_cents"])
            if amount and facts["status"] == "active":
                name, args = "request_credit", {"amount_cents": amount, "rationale": "Deterministic demo: request only the observed payroll gap within the authorized cap."}
            else:
                name, args = "continue_without_credit", {"rationale": "Deterministic demo: no payroll financing requested because there is no shortfall or the business is closed."}
        elif "assess_credit" in names:
            if len(results) == 1:
                requested = results[0]["proposal"]["amount_cents"]
                headroom = results[0]["facts"]["credit_headroom_cents"]
                amount = min(requested, headroom) if headroom else requested
                name, args = "assess_credit", {"amount_cents": amount}
            else:
                assessment = results[-1]
                name, args = "decide_credit", {"approved": assessment["eligible"],
                    "amount_cents": assessment["amount_cents"] if assessment["eligible"] else 0,
                    "rationale": "Deterministic demo: approve only principal passing recorded credit, capital, and liquidity constraints."}
        else:
            covered = results[0]["payroll_fully_covered"]
            name = "accept_offer" if covered else "decline_offer"
            args = {"rationale": "Deterministic demo: accept only an offer covering the full observed payroll shortfall."}
        return tool_call(name, args, len(results))


def credit_models(request):
    return {role: DemoCreditModel(role, request) if request["mode"] == "demo" else NebiusModel()
            for role in ("business", "bank")}


def role_loop(store, report, role, model, tools, handler, instruction):
    messages = [{"role": "system", "content": instruction +
                 " Use only the supplied function tools. Give concise public rationales, not hidden reasoning. "
                 "Balances, eligibility, and terms are determined by the tools, never by model assertions."}]
    for _ in range(8):
        message = model.complete(messages, tools)
        calls = message.get("tool_calls") if isinstance(message, dict) else None
        if not isinstance(calls, list) or not 1 <= len(calls) <= 4:
            raise ProviderError("Credit model returned an invalid function-call batch")
        for call in calls:
            if (not isinstance(call, dict) or not isinstance(call.get("id"), str) or not call["id"]
                    or not isinstance(call.get("function"), dict)
                    or not isinstance(call["function"].get("name"), str)
                    or not isinstance(call["function"].get("arguments"), str)):
                raise ProviderError("Credit model returned a malformed function call")
        messages.append(message)
        for call in calls:
            name = call["function"]["name"]
            args = {}
            done = False
            try:
                args = json.loads(call["function"]["arguments"])
                if not isinstance(args, dict):
                    raise ValueError("Arguments must be an object")
                result, done = handler(name, args)
                status = "accepted"
            except (LedgerError, ValueError, ValidationError, KeyError, TypeError) as error:
                status = "rejected"
                result = {"error": str(error) if isinstance(error, LedgerError) else "Arguments do not match the tool schema"}
                if not isinstance(args, dict):
                    args = {}
            report["trace"].append({"sequence": len(report["trace"]) + 1,
                                    "role": role, "actor_id": report["business_id"] if role == "business" else report["bank_id"],
                                    "tool": name, "arguments": args, "status": status, "result": result})
            store.save_credit(report)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
            if done:
                return
    raise ProviderError("Credit agent turn limit reached without a validated decision")


def run_credit(store, simulation_id, business_id, request):
    previous = store.find_credit(simulation_id, business_id, request)
    if previous is not None:
        # Recovery after an interruption between approval and auto-settlement.
        if previous["status"] == "approved" and request["auto_settle"]:
            return auto_settle(store, previous)
        return previous
    models = credit_models(request)
    report, source = store.claim_credit(simulation_id, business_id, request, models)
    inspected = False
    assessments = {}

    def business_handler(name, args):
        nonlocal inspected
        if name == "inspect_business":
            InspectArguments.model_validate(args)
            inspected = True
            return report["facts"], False
        if not inspected:
            raise LedgerError("Inspect business finances before deciding")
        if name == "request_credit":
            proposal = CreditProposal.model_validate(args)
            if report["facts"]["status"] != "active":
                raise LedgerError("Closed businesses cannot request credit")
            if proposal.amount_cents > min(request["max_amount_cents"], report["facts"]["payroll_shortfall_cents"]):
                raise LedgerError("Proposal exceeds the authorized cap or observed payroll shortfall")
            report["proposal"] = proposal.model_dump()
            return report["proposal"], True
        if name == "continue_without_credit":
            decision = ContinueBusiness.model_validate(args)
            report["business_rationale"] = decision.rationale
            report["status"] = "not_requested"
            return {"requested": False, **decision.model_dump()}, True
        raise LedgerError("Tool is not available to the business role")

    def bank_handler(name, args):
        nonlocal inspected
        if name == "inspect_credit":
            InspectArguments.model_validate(args)
            inspected = True
            return {"proposal": report["proposal"], "facts": report["facts"]}, False
        if not inspected:
            raise LedgerError("Inspect the credit request before underwriting")
        if name == "assess_credit":
            amount = AssessCreditArguments.model_validate(args).amount_cents
            if amount > report["proposal"]["amount_cents"]:
                raise LedgerError("Counteroffer cannot exceed the business proposal")
            assessment = assess_credit(source, business_id, amount)
            assessments[amount] = assessment
            return assessment, False
        if name == "decide_credit":
            decision = BankDecision.model_validate(args)
            if not assessments:
                raise LedgerError("Assess the request before making a bank decision")
            assessment = assessments.get(decision.amount_cents)
            if decision.approved and (assessment is None or not assessment["eligible"]):
                raise LedgerError("Approval requires the exact principal to pass underwriting")
            if not decision.approved:
                assessment = list(assessments.values())[-1]
            report["decision"] = {**decision.model_dump(), "assessment": assessment}
            if not decision.approved:
                report["status"] = "declined"
            return report["decision"], True
        raise LedgerError("Tool is not available to the bank role")

    def acceptance_handler(name, args):
        nonlocal inspected
        if name == "review_offer":
            InspectArguments.model_validate(args)
            inspected = True
            return {"decision": report["decision"], "proposal": report["proposal"],
                    "payroll_shortfall_cents": report["facts"]["payroll_shortfall_cents"],
                    "payroll_fully_covered": report["decision"]["amount_cents"] >= report["facts"]["payroll_shortfall_cents"]}, False
        if not inspected:
            raise LedgerError("Review the bank offer before accepting or declining")
        if name in ("accept_offer", "decline_offer"):
            decision = ContinueBusiness.model_validate(args)
            report["business_accepted"] = name == "accept_offer"
            report["business_rationale"] = decision.rationale
            report["status"] = "approved" if report["business_accepted"] else "declined"
            return {"accepted": report["business_accepted"], "amount_cents": report["decision"]["amount_cents"],
                    "rationale": decision.rationale}, True
        raise LedgerError("Tool is not available during business acceptance")

    try:
        role_loop(store, report, "business", models["business"], BUSINESS_TOOLS, business_handler,
                  f"You manage {business_id}. Inspect payroll needs, then request only useful payroll credit or continue without it. "
                  f"The caller authorizes at most {request['max_amount_cents']} cents. Do not request settlement.")
        if report["proposal"] is not None:
            inspected = False
            role_loop(store, report, "bank", models["bank"], BANK_TOOLS, bank_handler,
                      f"You manage {report['bank_id']}. Inspect the proposal, assess eligibility, then approve tested principal or decline. "
                      "A lower principal is a counteroffer; collateral and interest are not modeled.")
            if report["decision"]["approved"]:
                inspected = False
                role_loop(store, report, "business", models["business"], ACCEPTANCE_TOOLS, acceptance_handler,
                          "Review the approved bank offer. Accept the exact terms only if useful for your payroll, otherwise decline.")
    except ProviderError as error:
        report["status"] = "failed"
        report["error"] = str(error)
        store.save_credit(report)
        return report
    # The terminal tool already persisted the result. Do not overwrite a
    # concurrent settlement with this older in-memory approval.
    return auto_settle(store, report) if request["auto_settle"] and report["status"] == "approved" else store.get_credit(report["run_id"])


def auto_settle(store, report):
    try:
        store.settle_credit(report["run_id"], f"credit:{report['run_id']}")
    except LedgerError as error:
        # Approval remains inspectable; a stale source must be re-reviewed.
        return store.credit_settlement_error(report["run_id"], str(error))
    return store.get_credit(report["run_id"])
