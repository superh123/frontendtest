"""Explicit public-sector money creation; proposals never bypass the ledger."""

from backend.ledger import LedgerError


class InterventionRules:
    def intervene(self, transaction_id, kind, amount_cents, bank_id=None):
        self.positive_amount(amount_cents)
        if kind not in ("bank_lending", "household_cash"):
            raise LedgerError("Unknown intervention kind")
        if (kind == "bank_lending") != (bank_id is not None):
            raise LedgerError("Only bank lending requires a bank_id")
        request = {"type": "public_intervention", "kind": kind,
                   "amount_cents": amount_cents, "bank_id": bank_id}
        previous = self.existing(transaction_id, request)
        if previous is not None:
            return previous
        if kind == "bank_lending":
            if self.state["entities"][bank_id]["kind"] != "bank":
                raise LedgerError("Intervention target must be a commercial bank")
            asset = self.ledger.account("central_bank", f"public_loan_{bank_id}", "asset")
            debt = self.ledger.account(bank_id, "central_bank_debt", "liability")
            reserves = self.ledger.account("central_bank", "issued_reserves", "liability")
            lines = [(asset, amount_cents), (reserves, -amount_cents),
                     (f"{bank_id}:reserves", amount_cents), (debt, -amount_cents)]
            details = {"kind": kind, "bank_id": bank_id, "equity_injected_cents": 0}
        else:
            households = sorted((e for e in self.state["entities"].values() if e["kind"] == "household"),
                                key=lambda entity: entity["id"])
            if not households:
                raise LedgerError("No households to support")
            asset = self.ledger.account("central_bank", "public_loan_government", "asset")
            debt = self.ledger.account("government", "central_bank_debt", "liability")
            reserves = self.ledger.account("central_bank", "issued_reserves", "liability")
            lines = [(asset, amount_cents), (reserves, -amount_cents), (debt, -amount_cents),
                     ("government:equity", amount_cents)]
            each, remainder = divmod(amount_cents, len(households))
            allocations = []
            for index, household in enumerate(households):
                amount = each + (index < remainder)
                if not amount:
                    continue
                bank = household["bank_id"]
                lines += [(household["deposit_account"], amount), (household["equity_account"], -amount),
                          (f"{bank}:reserves", amount), (f"{bank}:deposit_{household['id']}", -amount)]
                allocations.append({"household_id": household["id"], "amount_cents": amount})
            details = {"kind": kind, "allocations": allocations}
        receipt = self.ledger.post(transaction_id, lines,
                                    {"type": "public_intervention", "tick": self.state["tick"],
                                     "request": request, "kind": kind, "amount_cents": amount_cents})
        self.emit("intervention_settled", "central_bank" if kind == "bank_lending" else "government",
                  bank_id, amount_cents, transaction_id, details)
        self.refresh_banks()
        self.audit()
        return receipt

    def public_metrics(self):
        disbursed = sum(entry["metadata"]["amount_cents"] for entry in self.ledger.state["journal"]
                        if entry["metadata"].get("type") == "public_intervention")
        fiscal = sum(entry["metadata"]["amount_cents"] for entry in self.ledger.state["journal"]
                     if entry["metadata"].get("type") == "public_intervention"
                     and entry["metadata"]["kind"] == "household_cash")
        outstanding = sum(self.ledger.balance(key) for key, account in self.ledger.state["accounts"].items()
                          if account["owner_id"] == "central_bank" and account["kind"] == "asset"
                          and account["name"].startswith("public_loan_"))
        return {"public_intervention_cost_cents": disbursed,
                "public_support_disbursed_cents": disbursed,
                "fiscal_transfer_cost_cents": fiscal, "public_loan_outstanding_cents": outstanding}

    def audit_public(self):
        for key, account in self.ledger.state["accounts"].items():
            if account["owner_id"] == "central_bank" and account["name"].startswith("public_loan_"):
                debtor = account["name"].removeprefix("public_loan_")
                if self.ledger.balance(key) != self.ledger.balance(f"{debtor}:central_bank_debt"):
                    raise LedgerError("Public loan asset does not match borrower debt")
        reserve_account = "central_bank:issued_reserves"
        if reserve_account in self.ledger.state["accounts"]:
            if self.ledger.balance(reserve_account) != self.public_metrics()["public_loan_outstanding_cents"]:
                raise LedgerError("Issued public reserves do not match public lending")
