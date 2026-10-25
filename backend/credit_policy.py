"""Deterministic underwriting facts; agent opinions never override this policy."""

from backend.engine import Economy
from backend.ledger import LedgerError


def business_facts(source, business_id):
    business = source.customer(business_id)
    if business["kind"] != "business":
        raise LedgerError("Credit workflow requires a business")
    cash = source.ledger.balance(business["deposit_account"])
    debt = source.ledger.balance(business["debt_account"])
    payroll = source.payroll(business)
    bank_health = source.bank_health(business["bank_id"])
    available = 0 if bank_health["status"] == "insolvent" else cash
    sales, wages = 0, 0
    for entry in source.ledger.state["journal"]:
        metadata = entry["metadata"]
        if metadata.get("tick", 0) < max(1, source.state["tick"] - 4):
            continue
        request = metadata.get("request", {})
        if metadata.get("type") == "purchase" and request.get("receiver_id") == business_id:
            sales += request["amount_cents"]
        if metadata.get("type") == "salary" and request.get("payer_id") == business_id:
            wages += request["amount_cents"]
    bank = business["bank_id"]
    sheet = source.ledger.sheet(bank)
    contracts = [contract for contract in source.state.get("contracts", {}).values() if contract["outstanding_cents"]]
    return {"business_id": business_id, "bank_id": bank, "status": business["status"],
            "deposit_cents": cash, "available_deposit_cents": available, "debt_cents": debt, "payroll_cents": payroll,
            "payroll_shortfall_cents": max(0, payroll - available), "credit_headroom_cents": max(0, 500_000 - debt),
            "loan_due_tick": business.get("loan_due_tick"),
            "recorded_sales_last_5_ticks_cents": sales, "recorded_wages_last_5_ticks_cents": wages,
            "trade_payables_cents": sum(c["outstanding_cents"] for c in contracts if c["buyer_id"] == business_id),
            "trade_receivables_cents": sum(c["outstanding_cents"] for c in contracts if c["supplier_id"] == business_id),
            "next_supplier_due_tick": min((c["due_tick"] for c in contracts if c["buyer_id"] == business_id), default=None),
            "bank": {**source.bank_health(bank), "equity_cents": sheet["equity_cents"],
                     "reserves_cents": sheet["assets"].get("reserves", 0)}}


def assess_credit(source, business_id, amount_cents):
    source.positive_amount(amount_cents)
    facts = business_facts(source, business_id)
    reasons = []
    if amount_cents > facts["payroll_shortfall_cents"]:
        reasons.append("Requested principal exceeds the observed payroll shortfall")
    if facts["loan_due_tick"] is not None and facts["loan_due_tick"] <= source.state["tick"] and facts["debt_cents"]:
        reasons.append("Existing business debt is already due; refinance before new payroll credit")
    projected = None
    try:
        candidate = Economy(source.state)
        transaction_id = f"credit:assessment:{len(candidate.ledger.state['journal'])}"
        while transaction_id in candidate.ledger._transactions:
            transaction_id += ":next"
        candidate.loan(transaction_id, business_id, amount_cents)
        projected = candidate.bank_health(facts["bank_id"])
        if not projected["lending_available"]:
            reasons.append("Loan would breach the bank's post-issuance capital or liquidity limits")
    except LedgerError as error:
        reasons.append(str(error))
    return {"eligible": not reasons, "amount_cents": amount_cents, "bank_id": facts["bank_id"],
            "due_tick": facts["loan_due_tick"] if facts["debt_cents"] else source.state["tick"] + 5,
            "projected_bank_health": projected, "reasons": reasons,
            "terms": "Principal-only; an existing loan maturity is preserved. No collateral or interest is modeled."}
