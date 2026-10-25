"""Two supplier offers, one counteroffer round, and buyer selection."""

import json

from backend.credit_agents import tools_for, tool_call
from backend.ledger import LedgerError
from backend.models import InspectArguments, QuoteTerms, ContinueBusiness, CounterOffer, SelectOffer
from backend.provider import NebiusModel, ProviderError
from backend.supply_policy import supplier_facts, validate_terms, make_offer, offer_eligibility
from backend.tool_loop import tool_session


SUPPLIER_TOOLS = tools_for([
    ("inspect_supplier", "Inspect fulfillable stock and supplier policy.", InspectArguments),
    ("quote_offer", "Quote price, initial payment, and deferred-payment term.", QuoteTerms),
    ("decline_offer", "Decline this supply request.", ContinueBusiness)])
COUNTER_TOOLS = tools_for([
    ("inspect_counteroffer", "Review buyer terms and whether they meet supplier policy.", InspectArguments),
    ("accept_counteroffer", "Accept the exact buyer terms if policy permits.", ContinueBusiness),
    ("decline_offer", "Decline the counteroffer; the original offer remains available.", ContinueBusiness)])
BUYER_TOOLS = tools_for([
    ("inspect_offers", "Compare real offers, full costs, down payments, and settlement eligibility.", InspectArguments),
    ("negotiate_offer", "Request one revised price/payment/term from an existing supplier.", CounterOffer),
    ("select_offer", "Accept one existing eligible offer, including its future obligation.", SelectOffer),
    ("decline_offer", "End without buying.", ContinueBusiness)])
FINAL_BUYER_TOOLS = [tool for tool in BUYER_TOOLS if tool["function"]["name"] != "negotiate_offer"]


class DemoSupplyModel:
    provider = "deterministic_demo"
    model = "demo-supply-v1"

    def complete(self, messages, tools):
        results = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        names = {tool["function"]["name"] for tool in tools}
        if not results:
            name = "inspect_supplier" if "quote_offer" in names else (
                "inspect_counteroffer" if "accept_counteroffer" in names else "inspect_offers")
            return tool_call(name, {}, 0)
        view = results[0]
        if "quote_offer" in names:
            if not view["can_supply"]:
                name, args = "decline_offer", {"rationale": "Deterministic demo: cannot fulfill active stock requirements."}
            else:
                name, args = "quote_offer", {"unit_price_cents": max(view["minimum_unit_price_cents"], view["reference_unit_price_cents"] * 110 // 100),
                    "down_payment_bps": 5000, "due_in_ticks": 3, "rationale": "Deterministic demo: quote available stock on standard terms."}
        elif "accept_counteroffer" in names:
            name = "accept_counteroffer" if view["acceptable"] else "decline_offer"
            args = {"rationale": "Deterministic demo: accept only counteroffers meeting supplier policy."}
        else:
            offers = [offer for offer in view["offers"] if offer["can_settle"]]
            if not offers:
                name, args = "decline_offer", {"rationale": "Deterministic demo: no affordable eligible supplier offer."}
            else:
                best = min(offers, key=lambda o: (o["down_payment_cents"], o["total_cents"], -o["due_in_ticks"]))
                if "negotiate_offer" in names:
                    name, args = "negotiate_offer", {"supplier_id": best["supplier_id"],
                        "unit_price_cents": max(1, best["unit_price_cents"] * 90 // 100),
                        "down_payment_bps": 2000, "due_in_ticks": 5,
                        "rationale": "Deterministic demo: request a discount, smaller down payment, and longer payment term."}
                else:
                    name, args = "select_offer", {"offer_id": best["offer_id"],
                        "rationale": "Deterministic demo: choose eligible terms minimizing immediate cash use, then full price."}
        return tool_call(name, args, len(results))


def supply_models(request, supplier_ids):
    return {actor: DemoSupplyModel() if request["mode"] == "demo" else NebiusModel()
            for actor in ("buyer", *supplier_ids)}


def choose_suppliers(source, buyer_id, request):
    buyer = source.customer(buyer_id)
    if buyer["kind"] != "business" or buyer["status"] != "active":
        raise LedgerError("Procurement requires an active buyer business")
    ids = request["supplier_ids"]
    if ids is None:
        ids = sorted(e["id"] for e in source.state["entities"].values()
                     if e["kind"] == "business" and e["id"] != buyer_id and e["status"] == "active")[:2]
    if len(ids) != 2:
        raise LedgerError("Create a world with at least three active businesses for two supplier offers")
    for supplier_id in ids:
        supplier_facts(source, buyer_id, supplier_id, request["quantity"])
    return ids


def run_procurement(store, simulation_id, buyer_id, request):
    previous = store.find_procurement(simulation_id, buyer_id, request)
    if previous is not None:
        return auto_contract(store, previous) if previous["status"] == "ready" and request["auto_settle"] else previous
    supplier_ids = choose_suppliers(store.get(simulation_id), buyer_id, request)
    models = supply_models(request, supplier_ids)
    report, source = store.claim_procurement(simulation_id, buyer_id, request, supplier_ids, models)

    def session(actor, role, tools, handler, instruction):
        def trace(name, args, status, result):
            report["trace"].append({"sequence": len(report["trace"]) + 1, "actor_id": buyer_id if role == "buyer" else actor,
                "role": role, "tool": name, "arguments": args, "status": status, "result": result})
            store.save_procurement(report)
        tool_session(models[actor], tools, handler, trace, instruction)

    try:
        for supplier_id in supplier_ids:
            facts = supplier_facts(source, buyer_id, supplier_id, request["quantity"])
            inspected = False
            def quote_handler(name, args):
                nonlocal inspected
                if name == "inspect_supplier":
                    InspectArguments.model_validate(args)
                    inspected = True
                    return facts, False
                if not inspected:
                    raise LedgerError("Inspect supplier stock before quoting")
                if name == "quote_offer":
                    terms = QuoteTerms.model_validate(args).model_dump()
                    validate_terms(facts, terms)
                    offer = make_offer(supplier_id, request["quantity"], terms, 1)
                    report["offers"].append(offer)
                    return offer, True
                if name == "decline_offer":
                    return ContinueBusiness.model_validate(args).model_dump(), True
                raise LedgerError("Tool is unavailable to the supplier")
            session(supplier_id, "supplier", SUPPLIER_TOOLS, quote_handler,
                    f"You supply materials as {supplier_id}. Inspect stock, then quote valid terms or decline. "
                    "This quote is provisional; delivery and settlement occur only after buyer selection.")

        def buyer_phase(final=False):
            inspected = False
            def buyer_handler(name, args):
                nonlocal inspected
                if name == "inspect_offers":
                    InspectArguments.model_validate(args)
                    inspected = True
                    return {"quantity": request["quantity"], "max_total_cents": request["max_total_cents"],
                        "offers": [{**offer, **offer_eligibility(source, buyer_id, request, offer)} for offer in report["offers"]],
                        "negotiation": report["negotiation"]}, False
                if not inspected:
                    raise LedgerError("Inspect offers before negotiating or selecting")
                if name == "negotiate_offer" and not final:
                    counter = CounterOffer.model_validate(args).model_dump()
                    if not any(o["supplier_id"] == counter["supplier_id"] for o in report["offers"]):
                        raise LedgerError("Counteroffer must target a supplier that actually quoted")
                    report["negotiation"] = {"request": counter, "status": "pending"}
                    return report["negotiation"], True
                if name == "select_offer":
                    selected = SelectOffer.model_validate(args)
                    offer = next((o for o in report["offers"] if o["offer_id"] == selected.offer_id), None)
                    if offer is None:
                        raise LedgerError("Choose an offer produced in this procurement run")
                    eligibility = offer_eligibility(source, buyer_id, request, offer)
                    if not eligibility["can_settle"]:
                        raise LedgerError(eligibility["reason"])
                    report["selected_offer"] = offer.copy()
                    report["buyer_rationale"] = selected.rationale
                    report["status"] = "ready"
                    return {"selected_offer": offer, "rationale": selected.rationale}, True
                if name == "decline_offer":
                    rationale = ContinueBusiness.model_validate(args).rationale
                    report["buyer_rationale"], report["status"] = rationale, "declined"
                    return {"declined": True, "rationale": rationale}, True
                raise LedgerError("Tool is unavailable in this buyer phase")
            session("buyer", "buyer", FINAL_BUYER_TOOLS if final else BUYER_TOOLS, buyer_handler,
                    f"You manage buyer {buyer_id}. Compare full obligations and initial cash needs. "
                    "Select an eligible offer, decline, or negotiate one counteroffer if that tool is available. "
                    "Accepting a contract authorizes its down payment and automatic due-date collection of its remainder.")

        buyer_phase()
        if report["negotiation"] is not None:
            counter = report["negotiation"]["request"]
            supplier_id = counter["supplier_id"]
            facts = supplier_facts(source, buyer_id, supplier_id, request["quantity"])
            terms = {key: value for key, value in counter.items() if key != "supplier_id"}
            inspected = False
            def counter_handler(name, args):
                nonlocal inspected
                if name == "inspect_counteroffer":
                    InspectArguments.model_validate(args)
                    inspected = True
                    try:
                        validate_terms(facts, terms)
                        acceptable = True
                    except LedgerError:
                        acceptable = False
                    return {"counteroffer": counter, "policy": facts, "acceptable": acceptable}, False
                if not inspected:
                    raise LedgerError("Inspect the counteroffer before deciding")
                rationale = ContinueBusiness.model_validate(args).rationale
                if name == "accept_counteroffer":
                    validate_terms(facts, terms)
                    revised = make_offer(supplier_id, request["quantity"], {**terms, "rationale": rationale}, 2)
                    report["offers"].append(revised)
                    report["negotiation"].update(status="accepted", supplier_rationale=rationale)
                    return revised, True
                if name == "decline_offer":
                    report["negotiation"].update(status="declined", supplier_rationale=rationale)
                    return report["negotiation"], True
                raise LedgerError("Tool is unavailable during counteroffer review")
            session(supplier_id, "supplier", COUNTER_TOOLS, counter_handler,
                    "Review this buyer counteroffer. Accept its exact terms only if they meet your policy, otherwise decline.")
            buyer_phase(final=True)
    except ProviderError as error:
        report["status"], report["error"] = "failed", str(error)
        store.save_procurement(report)
        return report
    return auto_contract(store, report) if report["status"] == "ready" and request["auto_settle"] else store.get_procurement(report["run_id"])


def auto_contract(store, report):
    try:
        store.settle_procurement(report["run_id"], f"procurement:{report['run_id']}")
    except LedgerError as error:
        return store.procurement_error(report["run_id"], str(error))
    return store.get_procurement(report["run_id"])
