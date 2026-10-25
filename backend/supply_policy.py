from backend.ledger import LedgerError


def supplier_facts(source, buyer_id, supplier_id, quantity):
    buyer, supplier = source.customer(buyer_id), source.customer(supplier_id)
    if buyer_id == supplier_id or buyer["kind"] != "business" or supplier["kind"] != "business":
        raise LedgerError("Procurement requires different buyer and supplier businesses")
    stock = supplier.get("materials_units", 0)
    reference = max(1, supplier["price_cents"] // 2)
    cost = source.material_cost(supplier_id)
    floor = max(1, reference * 80 // 100, (cost + stock - 1) // stock if stock else 1)
    return {"supplier_id": supplier_id, "buyer_id": buyer_id, "quantity": quantity,
            "available_units": stock, "reference_unit_price_cents": reference,
            "minimum_unit_price_cents": floor, "minimum_down_payment_bps": 2000, "maximum_due_in_ticks": 10,
            "can_supply": buyer["status"] == "active" and supplier["status"] == "active" and stock >= quantity}


def validate_terms(facts, terms):
    if not facts["can_supply"]:
        raise LedgerError("Supplier cannot fulfill this request from active stock")
    if terms["unit_price_cents"] < facts["minimum_unit_price_cents"]:
        raise LedgerError("Price is below the supplier's cost and pricing floor")
    if terms["down_payment_bps"] < facts["minimum_down_payment_bps"]:
        raise LedgerError("Down payment is below the supplier's policy minimum")
    if terms["due_in_ticks"] > facts["maximum_due_in_ticks"]:
        raise LedgerError("Deferred term exceeds the supplier's maximum")


def make_offer(supplier_id, quantity, terms, version):
    total = quantity * terms["unit_price_cents"]
    return {**terms, "offer_id": f"offer:{supplier_id}:{version}", "supplier_id": supplier_id,
            "quantity": quantity, "total_cents": total,
            "down_payment_cents": (total * terms["down_payment_bps"] + 9999) // 10000}


def offer_eligibility(source, buyer_id, request, offer):
    if offer["total_cents"] > request["max_total_cents"]:
        return {"can_settle": False, "reason": "Total obligation exceeds the authorized budget"}
    try:
        candidate = type(source)(source.state)
        candidate.create_contract("procurement:preview", "preview", buyer_id, offer["supplier_id"],
                                  offer["quantity"], offer["unit_price_cents"],
                                  offer["down_payment_bps"], offer["due_in_ticks"])
    except LedgerError as error:
        return {"can_settle": False, "reason": str(error)}
    return {"can_settle": True, "reason": None}
