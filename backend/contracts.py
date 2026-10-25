"""Delivered materials, trade-credit claims, and due-date settlement."""

from copy import deepcopy

from backend.ledger import LedgerError


class ContractRules:
    def material_cost(self, business_id):
        key = f"{business_id}:materials"
        return self.ledger.balance(key) if key in self.ledger.state["accounts"] else 0

    def material_consumption(self, business):
        stock = business.get("materials_units", 0)
        used = min(stock, len(business["employees"])) if business["status"] == "active" else 0
        if not used:
            return
        cost = self.material_cost(business["id"]) * used // stock
        if cost:
            transaction_id = f"tick:{self.state['tick']}:materials:{business['id']}"
            self.ledger.post(transaction_id, [(f"{business['id']}:materials", -cost),
                                              (business["equity_account"], cost)],
                             {"type": "materials_consumed", "tick": self.state["tick"], "quantity": used})
            self.emit("materials_consumed", business["id"], amount_cents=cost, transaction_id=transaction_id,
                      details={"quantity": used})
        business["materials_units"] -= used

    def transfer_lines(self, buyer, supplier, amount):
        payer_bank, receiver_bank = buyer["bank_id"], supplier["bank_id"]
        lines = [(f"{payer_bank}:deposit_{buyer['id']}", amount),
                 (f"{receiver_bank}:deposit_{supplier['id']}", -amount)]
        if payer_bank != receiver_bank:
            lines += [(f"{payer_bank}:reserves", -amount), (f"{receiver_bank}:reserves", amount)]
        return lines

    def create_contract(self, transaction_id, contract_id, buyer_id, supplier_id, quantity,
                        unit_price_cents, down_payment_bps, due_in_ticks):
        for amount in (quantity, unit_price_cents, due_in_ticks):
            self.positive_amount(amount)
        if type(down_payment_bps) is not int or not 1000 <= down_payment_bps <= 10000:
            raise LedgerError("Down payment must be between 1000 and 10000 basis points")
        request = {"type": "supplier_contract", "contract_id": contract_id, "buyer_id": buyer_id,
                   "supplier_id": supplier_id, "quantity": quantity, "unit_price_cents": unit_price_cents,
                   "down_payment_bps": down_payment_bps, "due_in_ticks": due_in_ticks}
        previous = self.existing(transaction_id, request)
        if previous is not None:
            return {"contract": deepcopy(self.state["contracts"][contract_id]), "receipt": previous}
        if contract_id in self.state.get("contracts", {}):
            raise LedgerError("Contract ID already exists")
        buyer, supplier = self.customer(buyer_id), self.customer(supplier_id)
        if buyer_id == supplier_id or buyer["kind"] != "business" or supplier["kind"] != "business":
            raise LedgerError("Supplier contracts require two different businesses")
        if buyer["status"] != "active" or supplier["status"] != "active":
            raise LedgerError("Closed businesses cannot create supplier contracts")
        if quantity > supplier.get("materials_units", 0):
            raise LedgerError("Supplier has insufficient material stock")
        if self.bank_health(buyer["bank_id"])["status"] == "insolvent":
            raise LedgerError("Buyer deposits are frozen")
        # Build on a copy so even failed direct engine calls leave no accounts,
        # inventory changes, or partial financial state behind.
        candidate = type(self)(self.state)
        buyer, supplier = candidate.customer(buyer_id), candidate.customer(supplier_id)
        total = quantity * unit_price_cents
        down = (total * down_payment_bps + 9999) // 10000
        remaining = total - down
        payable = candidate.ledger.account(buyer_id, f"payable_{contract_id}", "liability")
        receivable = candidate.ledger.account(supplier_id, f"receivable_{contract_id}", "asset")
        materials = candidate.ledger.account(buyer_id, "materials", "asset")
        supplier_materials = candidate.ledger.account(supplier_id, "materials", "asset")
        cost = candidate.material_cost(supplier_id) * quantity // supplier["materials_units"]
        lines = [(materials, total), (buyer["deposit_account"], -down), (payable, -remaining),
                 (supplier["deposit_account"], down), (receivable, remaining), (supplier["equity_account"], -total),
                 (supplier_materials, -cost), (supplier["equity_account"], cost)]
        lines += candidate.transfer_lines(buyer, supplier, down)
        receipt = candidate.ledger.post(transaction_id, lines,
                                         {"type": "supplier_contract", "tick": self.state["tick"], "request": request})
        buyer["materials_units"] = buyer.get("materials_units", 0) + quantity
        supplier["materials_units"] -= quantity
        contract = {"contract_id": contract_id, "buyer_id": buyer_id, "supplier_id": supplier_id,
                    "quantity": quantity, "unit_price_cents": unit_price_cents, "total_cents": total,
                    "down_payment_cents": down, "paid_cents": down, "outstanding_cents": remaining,
                    "written_off_cents": 0, "created_tick": self.state["tick"],
                    "due_tick": self.state["tick"] + due_in_ticks, "missed_payment_ticks": 0,
                    "status": "open" if remaining else "paid", "creation_transaction_id": transaction_id}
        candidate.state.setdefault("contracts", {})[contract_id] = contract
        candidate.emit("supplier_contract_created", buyer_id, supplier_id, total, transaction_id,
                       {"contract_id": contract_id, "quantity": quantity, "down_payment_cents": down,
                        "outstanding_cents": remaining, "due_tick": contract["due_tick"]})
        candidate.emit("supplier_down_payment", buyer_id, supplier_id, down, transaction_id,
                       {"contract_id": contract_id})
        candidate.audit()
        self.state, self.ledger = candidate.state, candidate.ledger
        return {"contract": deepcopy(contract), "receipt": receipt}

    def pay_contract(self, transaction_id, contract_id):
        request = {"type": "supplier_balance_payment", "contract_id": contract_id}
        previous = self.existing(transaction_id, request)
        if previous is not None:
            return previous
        contract = self.state.get("contracts", {})[contract_id]
        if contract["status"] not in ("open", "overdue"):
            raise LedgerError("Contract has no payable outstanding balance")
        buyer, supplier = self.customer(contract["buyer_id"]), self.customer(contract["supplier_id"])
        if buyer["status"] != "active" or self.bank_health(buyer["bank_id"])["status"] == "insolvent":
            raise LedgerError("Buyer is closed or its deposits are frozen")
        amount = contract["outstanding_cents"]
        receipt = self.ledger.post(transaction_id,
            [(buyer["deposit_account"], -amount), (f"{buyer['id']}:payable_{contract_id}", amount),
             (supplier["deposit_account"], amount), (f"{supplier['id']}:receivable_{contract_id}", -amount)]
            + self.transfer_lines(buyer, supplier, amount),
            {"type": "supplier_balance_payment", "tick": self.state["tick"], "request": request})
        contract["paid_cents"] += amount
        contract["outstanding_cents"] = 0
        contract["status"] = "paid"
        self.emit("supplier_balance_paid", buyer["id"], supplier["id"], amount, transaction_id,
                  {"contract_id": contract_id})
        return receipt

    def default_buyer_contracts(self, buyer_id):
        for contract in self.state.get("contracts", {}).values():
            if contract["buyer_id"] == buyer_id and contract["outstanding_cents"]:
                amount = contract["outstanding_cents"]
                supplier_id = contract["supplier_id"]
                transaction_id = f"tick:{self.state['tick']}:contract_writeoff:{contract['contract_id']}"
                self.ledger.post(transaction_id,
                    [(f"{buyer_id}:payable_{contract['contract_id']}", amount), (f"{buyer_id}:equity", -amount),
                     (f"{supplier_id}:receivable_{contract['contract_id']}", -amount), (f"{supplier_id}:equity", amount)],
                    {"type": "supplier_default", "tick": self.state["tick"], "contract_id": contract["contract_id"]})
                contract["outstanding_cents"] = 0
                contract["written_off_cents"] += amount
                contract["status"] = "defaulted"
                self.emit("supplier_contract_default", buyer_id, supplier_id, amount, transaction_id,
                          {"contract_id": contract["contract_id"]})

    def settle_due_contracts(self):
        for contract in list(self.state.get("contracts", {}).values()):
            if contract["status"] not in ("open", "overdue") or contract["due_tick"] > self.state["tick"]:
                continue
            if contract.get("last_attempt_tick") == self.state["tick"]:
                continue
            contract["last_attempt_tick"] = self.state["tick"]
            try:
                self.pay_contract(f"tick:{self.state['tick']}:contract_pay:{contract['contract_id']}", contract["contract_id"])
            except LedgerError as error:
                contract["status"] = "overdue"
                contract["missed_payment_ticks"] += 1
                self.emit("supplier_payment_rejected", contract["buyer_id"], contract["supplier_id"],
                          contract["outstanding_cents"], details={"contract_id": contract["contract_id"], "reason": str(error)})
                if contract["missed_payment_ticks"] >= 2:
                    self.default_business(self.customer(contract["buyer_id"]), "Two consecutive unpaid supplier bills")

    def audit_contracts(self):
        for contract_id, contract in self.state.get("contracts", {}).items():
            remaining = contract["outstanding_cents"]
            if (self.ledger.balance(f"{contract['buyer_id']}:payable_{contract_id}") != remaining
                    or self.ledger.balance(f"{contract['supplier_id']}:receivable_{contract_id}") != remaining
                    or contract["paid_cents"] + remaining + contract["written_off_cents"] != contract["total_cents"]):
                raise LedgerError("Supplier contract and ledger claims disagree")
        for business in self.state["entities"].values():
            if business["kind"] == "business":
                units = business.get("materials_units", 0)
                if type(units) is not int or units < 0 or (units == 0 and self.material_cost(business["id"])):
                    raise LedgerError("Material units and carrying value disagree")
