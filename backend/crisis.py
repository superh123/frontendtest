"""Crisis rules shared by the simulation engine. All losses use ledger entries."""

from backend.clearing import clear_payments
from backend.ledger import LedgerError


class CrisisRules:
    def bank_health(self, bank_id):
        bank = self.state["entities"][bank_id]
        sheet = self.ledger.sheet(bank_id)
        deposits = sum(value for name, value in sheet["liabilities"].items() if name.startswith("deposit_"))
        capital_ratio = sheet["equity_cents"] / sheet["assets_cents"] if sheet["assets_cents"] else 0
        liquidity_ratio = sheet["assets"].get("reserves", 0) / deposits if deposits else 1
        status = ("insolvent" if sheet["equity_cents"] <= 0 else
                  "stressed" if capital_ratio < 0.08 or liquidity_ratio < 0.10
                  or bank.get("interbank_default", False) else "active")
        return {"status": status, "capital_ratio": capital_ratio, "liquidity_ratio": liquidity_ratio,
                "lending_available": status == "active"}

    def refresh_banks(self):
        for bank in self.state["entities"].values():
            if bank["kind"] == "bank":
                status = self.bank_health(bank["id"])["status"]
                previous = bank["status"]
                bank["status"] = status
                if previous != status:
                    self.emit("bank_status_changed", bank["id"],
                              details={"previous_status": previous, **self.bank_health(bank["id"])})

    def lending_check(self, borrower_id, additional_cents=0):
        borrower = self.customer(borrower_id)
        bank = borrower["bank_id"]
        if borrower["status"] != "active":
            raise LedgerError("Defaulted businesses cannot borrow")
        if not self.bank_health(bank)["lending_available"]:
            raise LedgerError("Bank capital or liquidity constraints prevent lending")
        sheet = self.ledger.sheet(bank)
        loans = sum(value for name, value in sheet["assets"].items() if name.startswith("loan_"))
        if loans + additional_cents > sheet["equity_cents"] * 5:
            raise LedgerError("Bank capital lending limit exceeded")
        if self.ledger.balance(borrower["debt_account"]) + additional_cents > 500_000:
            raise LedgerError("Borrower credit limit exceeded")

    def initialize_financial_network(self, scenario):
        banks = [e for e in self.state["entities"].values() if e["kind"] == "bank"]
        if scenario == "credit_crunch":
            households = [e for e in self.state["entities"].values() if e["kind"] == "household"]
            businesses = [e for e in self.state["entities"].values() if e["kind"] == "business"]
            for index, business in enumerate(businesses):
                payroll = self.payroll(business)
                principal = min(300_000, max(10_000, payroll * 2))
                self.loan(f"genesis:credit:{business['id']}", business["id"], principal)
                cash = self.ledger.balance(business["deposit_account"])
                setup_cost = max(0, cash - max(10_000, payroll * 3 // 2))
                if setup_cost:
                    self.pay(f"genesis:setup:{business['id']}", business["id"],
                             households[index % len(households)]["id"], setup_cost, "startup_cost")
            # A disclosed starting-capital assumption, not a shock or rescue.
            for bank in banks:
                deposits = sum(value for name, value in self.ledger.sheet(bank["id"])["liabilities"].items()
                               if name.startswith("deposit_"))
                target = max(100_000, deposits // 6)
                loans = sum(value for name, value in self.ledger.sheet(bank["id"])["assets"].items()
                            if name.startswith("loan_"))
                target = max(target, loans - deposits * 80 // 100 + 100_000)
                adjustment = self.ledger.sheet(bank["id"])["equity_cents"] - target
                self.ledger.post(f"genesis:capital:{bank['id']}",
                                 [(f"{bank['id']}:reserves", -adjustment),
                                  (bank["equity_account"], adjustment)],
                                 {"type": "opening_capital_adjustment", "tick": 0})
        self.state["interbank_obligations"] = []
        if len(banks) > 1:
            amount = min(self.ledger.balance(f"{bank['id']}:reserves") for bank in banks) // 2
            lines = []
            for index, lender in enumerate(banks):
                borrower = banks[(index + 1) % len(banks)]
                asset = self.ledger.account(lender["id"], f"interbank_asset_{borrower['id']}", "asset")
                debt = self.ledger.account(borrower["id"], f"interbank_debt_{lender['id']}", "liability")
                lines += [(asset, amount), (f"{lender['id']}:reserves", -amount),
                          (f"{borrower['id']}:reserves", amount), (debt, -amount)]
                self.state["interbank_obligations"].append({"borrower_id": borrower["id"],
                                                           "lender_id": lender["id"],
                                                           "amount_cents": amount, "due_tick": 5})
            # Simultaneous opening settlement avoids order-dependent liquidity.
            self.ledger.post("genesis:interbank", lines, {"type": "interbank_origination", "tick": 0})
        for bank in banks:
            reserves = self.ledger.balance(f"{bank['id']}:reserves")
            deposits = sum(value for name, value in self.ledger.sheet(bank["id"])["liabilities"].items()
                           if name.startswith("deposit_"))
            amount = max(0, reserves - max(reserves * 20 // 100, deposits * 15 // 100))
            asset = self.ledger.account(bank["id"], "risky_assets", "asset")
            self.ledger.post(f"genesis:portfolio:{bank['id']}",
                             [(f"{bank['id']}:reserves", -amount), (asset, amount)],
                             {"type": "opening_portfolio_allocation", "tick": 0})
        self.refresh_banks()

    def shock(self, transaction_id, bank_id, loss_bps=4000, asset_category="risky_assets"):
        if type(loss_bps) is not int or not 1 <= loss_bps <= 10_000:
            raise LedgerError("Loss must be between 1 and 10000 basis points")
        if asset_category != "risky_assets":
            raise LedgerError("Only the risky_assets category can be shocked")
        request = {"type": "bank_asset_shock", "bank_id": bank_id,
                   "loss_bps": loss_bps, "asset_category": asset_category}
        previous = self.existing(transaction_id, request)
        if previous is not None:
            return previous
        bank = self.state["entities"][bank_id]
        if bank["kind"] != "bank":
            raise LedgerError("Shock target must be a commercial bank")
        account = f"{bank_id}:{asset_category}"
        if account not in self.ledger.state["accounts"]:
            raise LedgerError("This legacy world has no risky portfolio; create a new world")
        loss = self.ledger.balance(account) * loss_bps // 10_000
        if loss == 0:
            raise LedgerError("Shock rounds to zero cents or the asset category is empty")
        entry = self.ledger.post(transaction_id, [(account, -loss), (bank["equity_account"], loss)],
                                 {"type": "bank_asset_shock", "tick": self.state["tick"], "request": request})
        self.emit("bank_asset_loss", bank_id, amount_cents=loss, transaction_id=transaction_id,
                  details={"loss_bps": loss_bps, "asset_category": asset_category})
        self.refresh_banks()
        self.audit()
        return entry

    def settle_interbank(self):
        obligations = [o for o in self.state.get("interbank_obligations", [])
                       if o["amount_cents"] and o["due_tick"] <= self.state["tick"]]
        if not obligations:
            return
        banks = [e for e in self.state["entities"].values() if e["kind"] == "bank"]
        liquid, protected = {}, {}
        for bank in banks:
            sheet = self.ledger.sheet(bank["id"])
            liquid[bank["id"]] = sheet["assets"]["reserves"] + sheet["assets"].get("risky_assets", 0)
            protected[bank["id"]] = sum(value for name, value in sheet["liabilities"].items()
                                         if name.startswith("deposit_"))
        nominal = {(o["borrower_id"], o["lender_id"]): o["amount_cents"] for o in obligations}
        clearing = clear_payments(nominal, liquid, protected)
        payments = clearing["payments"]
        lines = []
        for bank in banks:
            bank_id = bank["id"]
            outgoing = sum(paid for (debtor, _), paid in payments.items() if debtor == bank_id)
            incoming = sum(paid for (_, creditor), paid in payments.items() if creditor == bank_id)
            shortfall = max(0, outgoing - incoming - self.ledger.balance(f"{bank_id}:reserves"))
            if shortfall:
                lines += [(f"{bank_id}:risky_assets", -shortfall), (f"{bank_id}:reserves", shortfall)]
        for obligation in obligations:
            debtor, creditor, amount = obligation["borrower_id"], obligation["lender_id"], obligation["amount_cents"]
            paid = payments[debtor, creditor]
            loss = amount - paid
            lines += [(f"{debtor}:reserves", -paid), (f"{debtor}:interbank_debt_{creditor}", amount),
                      (f"{debtor}:equity", -loss), (f"{creditor}:reserves", paid),
                      (f"{creditor}:interbank_asset_{debtor}", -amount), (f"{creditor}:equity", loss)]
        transaction_id = f"tick:{self.state['tick']}:interbank_clearing"
        self.ledger.post(transaction_id, lines, {"type": "interbank_clearing", "tick": self.state["tick"],
                                                "iterations": clearing["iterations"]})
        for obligation in obligations:
            debtor, creditor, amount = obligation["borrower_id"], obligation["lender_id"], obligation["amount_cents"]
            paid = payments[debtor, creditor]
            obligation["amount_cents"] = 0
            self.emit("interbank_payment", debtor, creditor, paid, transaction_id,
                      {"due_cents": amount, "unpaid_cents": amount - paid})
            if paid < amount:
                self.state["entities"][debtor]["interbank_default"] = True
                self.emit("interbank_default", debtor, creditor, amount - paid, transaction_id,
                          {"due_cents": amount, "paid_cents": paid})
        self.emit("interbank_cleared", transaction_id=transaction_id,
                  details={"iterations": clearing["iterations"],
                           "unpaid_cents": sum(nominal[edge] - paid for edge, paid in payments.items())})
        self.refresh_banks()

    def payroll(self, business):
        return sum(self.state["entities"][worker]["wage_cents"] for worker in business["employees"])

    def prepare_business(self, business):
        if business["status"] != "active":
            return
        tick = self.state["tick"]
        debt = self.ledger.balance(business["debt_account"])
        if debt and business.get("loan_due_tick", tick + 1) <= tick:
            cash = self.ledger.balance(business["deposit_account"])
            repayment = min(debt, max(0, cash - self.payroll(business)))
            if repayment:
                try:
                    self.loan(f"tick:{tick}:repay:{business['id']}", business["id"], repayment, repay=True)
                except LedgerError as error:
                    self.emit("payment_rejected", business["id"], business["bank_id"], repayment,
                              details={"purpose": "loan_repayment", "reason": str(error)})
            remaining = self.ledger.balance(business["debt_account"])
            if remaining:
                try:
                    self.lending_check(business["id"])
                    business["loan_due_tick"] = tick + 5
                    business["missed_debt_ticks"] = 0
                    self.emit("loan_refinanced", business["id"], business["bank_id"], remaining,
                              details={"due_tick": tick + 5})
                except LedgerError as error:
                    business["missed_debt_ticks"] = business.get("missed_debt_ticks", 0) + 1
                    self.emit("credit_rejected", business["id"], business["bank_id"], remaining,
                              details={"purpose": "refinancing", "reason": str(error)})
                    if business["missed_debt_ticks"] >= 2:
                        self.default_business(business, "Unable to refinance matured debt")
                        return
            else:
                business["missed_debt_ticks"] = 0
        gap = max(0, self.payroll(business) - self.ledger.balance(business["deposit_account"]))
        if gap:
            try:
                self.loan(f"tick:{tick}:payroll_credit:{business['id']}", business["id"], gap)
            except LedgerError as error:
                self.emit("credit_rejected", business["id"], business["bank_id"], gap,
                          details={"purpose": "payroll", "reason": str(error)})

    def default_business(self, business, reason):
        if business["status"] == "defaulted":
            return
        debt = self.ledger.balance(business["debt_account"])
        transaction_id = None
        if debt:
            transaction_id = f"tick:{self.state['tick']}:writeoff:{business['id']}"
            self.ledger.post(transaction_id,
                             [(business["debt_account"], debt), (business["equity_account"], -debt),
                              (f"{business['bank_id']}:loan_{business['id']}", -debt),
                              (f"{business['bank_id']}:equity", debt)],
                             {"type": "loan_writeoff", "tick": self.state["tick"]})
            self.emit("loan_default", business["id"], business["bank_id"], debt, transaction_id)
        business["status"] = "defaulted"
        self.default_buyer_contracts(business["id"])
        business["loan_due_tick"] = None
        workers = business["employees"][:]
        business["employees"] = []
        for worker_id in workers:
            self.state["entities"][worker_id]["employer_id"] = None
            self.emit("job_lost", worker_id, business["id"])
        self.emit("business_default", business["id"], business["bank_id"], debt, transaction_id,
                  {"reason": reason, "jobs_lost": len(workers)})
        self.refresh_banks()

    def network(self):
        exposures = [{**o, "kind": "interbank"} for o in self.state.get("interbank_obligations", [])
                     if o["amount_cents"]]
        exposures += [{"kind": "trade_credit", "borrower_id": c["buyer_id"], "lender_id": c["supplier_id"],
                       "amount_cents": c["outstanding_cents"], "due_tick": c["due_tick"]}
                      for c in self.state.get("contracts", {}).values() if c["outstanding_cents"]]
        for entity in self.state["entities"].values():
            if "debt_account" in entity:
                debt = self.ledger.balance(entity["debt_account"])
                if debt:
                    exposures.append({"kind": "customer_loan", "borrower_id": entity["id"],
                                      "lender_id": entity["bank_id"], "amount_cents": debt,
                                      "due_tick": entity.get("loan_due_tick")})
        for key, account in self.ledger.state["accounts"].items():
            if account["owner_id"] == "central_bank" and account["name"].startswith("public_loan_"):
                amount = self.ledger.balance(key)
                if amount:
                    exposures.append({"kind": "public_loan", "lender_id": "central_bank",
                                      "borrower_id": account["name"].removeprefix("public_loan_"),
                                      "amount_cents": amount, "due_tick": None})
        return {"simulation_id": self.state["simulation_id"], "simulation_tick": self.state["tick"],
                "exposures": exposures}
