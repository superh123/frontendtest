"""Deterministic economy rules. One tick is one simulated day."""

import random
from copy import deepcopy

from backend.ledger import Ledger, LedgerError
from backend.crisis import CrisisRules
from backend.interventions import InterventionRules
from backend.contracts import ContractRules


class Economy(CrisisRules, InterventionRules, ContractRules):
    def __init__(self, state):
        self.state = deepcopy(state)
        self.ledger = Ledger(self.state["ledger"])
        self.state["ledger"] = self.ledger.state

    @classmethod
    def create(cls, simulation_id, seed=42, households=40, businesses=8, banks=5, scenario="standard"):
        if scenario not in ("standard", "credit_crunch"):
            raise LedgerError("Unknown starting scenario")
        rng = random.Random(seed)
        world = cls({"simulation_id": simulation_id, "seed": seed, "tick": 0,
                     "config": {"seed": seed, "households": households,
                                "businesses": businesses, "banks": banks, "scenario": scenario},
                     "entities": {}, "ledger": {"accounts": {}, "journal": []},
                     "events": [], "history": []})
        for i in range(banks):
            entity = world.add_entity(f"bank_{i+1}", f"Bank {i+1}", "bank")
            reserves = world.ledger.account(entity["id"], "reserves", "asset")
            world.ledger.post(f"genesis:{entity['id']}",
                              [(reserves, 10_000_000), (entity["equity_account"], -10_000_000)],
                              {"type": "opening_endowment", "tick": 0})
        world.add_entity("government", "Government", "government")
        world.add_entity("central_bank", "Central Bank", "central_bank")
        for i in range(businesses):
            entity = world.add_customer(f"business_{i+1}", f"Business {i+1}", "business",
                                        f"bank_{i % banks + 1}", rng.randint(500_000, 900_000))
            entity["employees"] = []
            entity["price_cents"] = rng.randint(800, 1400)
            entity["materials_units"] = 1000
            world.ledger.account(entity["id"], "materials", "asset")
        for i in range(households):
            entity = world.add_customer(f"household_{i+1}", f"Household {i+1}", "household",
                                        f"bank_{rng.randrange(banks)+1}", rng.randint(50_000, 150_000))
            entity["employer_id"] = f"business_{i % businesses + 1}"
            entity["wage_cents"] = rng.randint(6000, 10_000)
            entity["consumption_budget_cents"] = rng.randint(5000, 8500)
            world.state["entities"][entity["employer_id"]]["employees"].append(entity["id"])
        world.initialize_financial_network(scenario)
        world.emit("world_created", details={"seed": seed, "households": households,
                                              "businesses": businesses, "banks": banks})
        world.state["history"].append(world.metrics())
        world.audit()
        return world

    def add_entity(self, entity_id, name, kind):
        entity = {"id": entity_id, "name": name, "kind": kind, "status": "active",
                  "equity_account": self.ledger.account(entity_id, "equity", "equity")}
        self.state["entities"][entity_id] = entity
        return entity

    def add_customer(self, entity_id, name, kind, bank_id, opening_cents):
        entity = self.add_entity(entity_id, name, kind)
        entity["bank_id"] = bank_id
        entity["deposit_account"] = self.ledger.account(entity_id, "deposit", "asset")
        entity["debt_account"] = self.ledger.account(entity_id, "loan", "liability")
        liability = self.ledger.account(bank_id, f"deposit_{entity_id}", "liability")
        self.ledger.account(bank_id, f"loan_{entity_id}", "asset")
        # Explicit genesis endowments: initial deposits are backed by newly
        # endowed reserves. These entries only occur when creating the world.
        self.ledger.post(f"genesis:{entity_id}",
                         [(entity["deposit_account"], opening_cents),
                          (entity["equity_account"], -opening_cents),
                          (f"{bank_id}:reserves", opening_cents), (liability, -opening_cents)],
                         {"type": "opening_endowment", "tick": 0})
        return entity

    def customer(self, entity_id):
        entity = self.state["entities"].get(entity_id)
        if entity is None:
            raise KeyError(entity_id)
        if "deposit_account" not in entity:
            raise LedgerError("This operation requires a household or business")
        return entity

    def emit(self, event_type, agent_id=None, counterparty_id=None, amount_cents=None,
             transaction_id=None, details=None):
        event = {"sequence": len(self.state["events"]) + 1,
                 "simulation_id": self.state["simulation_id"], "simulation_tick": self.state["tick"],
                 "event_type": event_type, "agent_id": agent_id,
                 "counterparty_id": counterparty_id, "amount_cents": amount_cents,
                 "transaction_id": transaction_id, "details": details or {}}
        self.state["events"].append(event)
        return event

    def existing(self, transaction_id, request):
        previous = self.ledger._transactions.get(transaction_id)
        if previous is not None:
            if previous["metadata"].get("request") != request:
                raise LedgerError("Transaction ID already used with different contents")
            return previous

    @staticmethod
    def positive_amount(amount):
        if type(amount) is not int or amount <= 0:
            raise LedgerError("Amount must be a positive integer in cents")

    def pay(self, transaction_id, payer_id, receiver_id, amount_cents, purpose="payment"):
        self.positive_amount(amount_cents)
        if payer_id == receiver_id:
            raise LedgerError("Payer and receiver must differ")
        request = {"type": purpose, "payer_id": payer_id, "receiver_id": receiver_id,
                   "amount_cents": amount_cents}
        previous = self.existing(transaction_id, request)
        if previous is not None:
            return previous
        payer, receiver = self.customer(payer_id), self.customer(receiver_id)
        payer_bank, receiver_bank = payer["bank_id"], receiver["bank_id"]
        if payer["status"] != "active" or receiver["status"] != "active":
            raise LedgerError("Defaulted businesses cannot make or receive trading payments")
        if self.bank_health(payer_bank)["status"] == "insolvent":
            raise LedgerError("Deposits at an insolvent bank are frozen")
        lines = [(payer["deposit_account"], -amount_cents), (payer["equity_account"], amount_cents),
                 (receiver["deposit_account"], amount_cents), (receiver["equity_account"], -amount_cents),
                 (f"{payer_bank}:deposit_{payer_id}", amount_cents),
                 (f"{receiver_bank}:deposit_{receiver_id}", -amount_cents)]
        if payer_bank != receiver_bank:
            lines += [(f"{payer_bank}:reserves", -amount_cents),
                      (f"{receiver_bank}:reserves", amount_cents)]
        entry = self.ledger.post(transaction_id, lines,
                                 {"type": purpose, "tick": self.state["tick"], "request": request})
        self.emit(purpose, payer_id, receiver_id, amount_cents, transaction_id)
        return entry

    def loan(self, transaction_id, borrower_id, amount_cents, repay=False):
        """Principal-only bank credit; no interest or maturity model yet."""
        self.positive_amount(amount_cents)
        kind = "loan_repayment" if repay else "loan_issued"
        request = {"type": kind, "borrower_id": borrower_id, "amount_cents": amount_cents}
        previous = self.existing(transaction_id, request)
        if previous is not None:
            return previous
        borrower = self.customer(borrower_id)
        bank = borrower["bank_id"]
        if not repay:
            self.lending_check(borrower_id, amount_cents)
        elif self.bank_health(bank)["status"] == "insolvent":
            raise LedgerError("Deposits at an insolvent bank are frozen")
        previous_debt = self.ledger.balance(borrower["debt_account"])
        sign = -1 if repay else 1
        entry = self.ledger.post(transaction_id,
                                 [(borrower["deposit_account"], sign * amount_cents),
                                  (borrower["debt_account"], -sign * amount_cents),
                                  (f"{bank}:loan_{borrower_id}", sign * amount_cents),
                                  (f"{bank}:deposit_{borrower_id}", -sign * amount_cents)],
                                 {"type": kind, "tick": self.state["tick"], "request": request})
        self.emit(kind, borrower_id, bank, amount_cents, transaction_id)
        if borrower["kind"] == "business":
            if not repay and previous_debt == 0:
                borrower["loan_due_tick"] = self.state["tick"] + 5
            elif repay and self.ledger.balance(borrower["debt_account"]) == 0:
                borrower["loan_due_tick"] = None
        return entry

    def step(self, ticks=1):
        for _ in range(ticks):
            self.state["tick"] += 1
            tick = self.state["tick"]
            self.settle_interbank()
            self.refresh_banks()
            self.settle_due_contracts()
            # Independent per-tick RNG makes future snapshot branches comparable.
            rng = random.Random(f"{self.state['seed']}:{tick}:consumption")
            households = [e for e in self.state["entities"].values() if e["kind"] == "household"]
            businesses = [e for e in self.state["entities"].values() if e["kind"] == "business"]
            for business in businesses:
                self.material_consumption(business)
                self.prepare_business(business)
            failed_employers = set()
            for household in households:
                if household["employer_id"] is None:
                    continue
                try:
                    self.pay(f"tick:{tick}:salary:{household['id']}", household["employer_id"],
                             household["id"], household["wage_cents"], "salary")
                except LedgerError as error:
                    failed_employers.add(household["employer_id"])
                    self.emit("payment_rejected", household["employer_id"], household["id"],
                              household["wage_cents"], details={"purpose": "salary", "reason": str(error)})
            for business in businesses:
                if business["status"] == "active":
                    business["missed_payroll_ticks"] = (business.get("missed_payroll_ticks", 0) + 1
                                                        if business["id"] in failed_employers else 0)
                    if business["missed_payroll_ticks"] >= 2:
                        self.default_business(business, "Two consecutive days of incomplete payroll")
            for household in households:
                seller = rng.choice(businesses)
                if seller["status"] != "active":
                    continue
                available = self.ledger.balance(household["deposit_account"])
                budget = min(available, household["consumption_budget_cents"])
                if household["employer_id"] is None:
                    budget = min(budget, available // 10)
                amount = budget // seller["price_cents"] * seller["price_cents"]
                if amount:
                    try:
                        self.pay(f"tick:{tick}:purchase:{household['id']}", household["id"],
                                 seller["id"], amount, "purchase")
                    except LedgerError as error:
                        self.emit("payment_rejected", household["id"], seller["id"], amount,
                                  details={"purpose": "purchase", "reason": str(error)})
            self.refresh_banks()
            self.state["history"].append(self.metrics())
            self.emit("tick_completed", details={"metrics": self.metrics()})
        self.audit()

    def metrics(self):
        households = [e for e in self.state["entities"].values() if e["kind"] == "household"]
        businesses = [e for e in self.state["entities"].values() if e["kind"] == "business"]
        banks = [e for e in self.state["entities"].values() if e["kind"] == "bank"]
        employed = sum(e["employer_id"] is not None for e in households)
        bank_sheets = [self.ledger.sheet(e["id"]) for e in banks]
        return {"simulation_tick": self.state["tick"], "households": len(households),
                "businesses": len(businesses), "banks": len(banks), "employed_households": employed,
                "employment_rate": employed / len(households),
                "household_cash_cents": sum(self.ledger.balance(e["deposit_account"]) for e in households),
                "business_cash_cents": sum(self.ledger.balance(e["deposit_account"]) for e in businesses),
                "total_deposits_cents": sum(self.ledger.balance(e["deposit_account"])
                                             for e in households + businesses),
                "total_bank_reserves_cents": sum(s["assets"]["reserves"] for s in bank_sheets),
                "total_loans_cents": sum(self.ledger.balance(e["debt_account"]) for e in households + businesses),
                "business_defaults": sum(e["status"] == "defaulted" for e in businesses),
                "stressed_banks": sum(self.bank_health(b["id"])["status"] != "active" for b in banks),
                "insolvent_banks": sum(s["equity_cents"] <= 0 for s in bank_sheets),
                "trade_credit_outstanding_cents": sum(c["outstanding_cents"] for c in self.state.get("contracts", {}).values()),
                "supplier_contract_defaults": sum(c["status"] == "defaulted" for c in self.state.get("contracts", {}).values()),
                **self.public_metrics()}

    def entity_view(self, entity_id):
        entity = self.state["entities"][entity_id]
        view = {**{k: v for k, v in entity.items() if not k.endswith("_account")},
                "balance_sheet": self.ledger.sheet(entity_id)}
        if entity["kind"] == "bank":
            view.update(self.bank_health(entity_id))
        return view

    def view(self):
        return {"simulation_id": self.state["simulation_id"], "seed": self.state["seed"],
                "simulation_tick": self.state["tick"], "status": "paused",
                "config": self.state["config"], "metrics": self.metrics(), "lineage": self.state.get("lineage"),
                "entities": [self.entity_view(key) for key in self.state["entities"]],
                "latest_event_sequence": len(self.state["events"])}

    def audit(self):
        result = self.ledger.audit()
        for entity in self.state["entities"].values():
            if "deposit_account" in entity:
                bank = entity["bank_id"]
                if self.ledger.balance(entity["deposit_account"]) != self.ledger.balance(f"{bank}:deposit_{entity['id']}"):
                    raise LedgerError("Customer deposit does not match bank liability")
                if self.ledger.balance(entity["debt_account"]) != self.ledger.balance(f"{bank}:loan_{entity['id']}"):
                    raise LedgerError("Customer debt does not match bank asset")
        for obligation in self.state.get("interbank_obligations", []):
            debtor, creditor = obligation["borrower_id"], obligation["lender_id"]
            if (self.ledger.balance(f"{debtor}:interbank_debt_{creditor}") != obligation["amount_cents"]
                    or self.ledger.balance(f"{creditor}:interbank_asset_{debtor}") != obligation["amount_cents"]):
                raise LedgerError("Interbank obligation and ledger disagree")
        self.audit_public()
        self.audit_contracts()
        return {**result, "bank_counterparties_match": True, "interbank_counterparties_match": True,
                "public_counterparties_match": True, "supplier_counterparties_match": True}
