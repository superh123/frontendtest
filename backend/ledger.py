"""Integer-cent, multi-entity double-entry ledger. No web dependencies."""

from collections import defaultdict
from copy import deepcopy


class LedgerError(ValueError):
    pass


class Ledger:
    def __init__(self, state=None):
        self.state = deepcopy(state) if state is not None else {"accounts": {}, "journal": []}
        self._transactions = {item["transaction_id"]: item for item in self.state["journal"]}
        self._owners = defaultdict(list)
        for key, account in self.state["accounts"].items():
            self._owners[account["owner_id"]].append(key)

    def account(self, owner, name, kind):
        key = f"{owner}:{name}"
        expected = {"owner_id": owner, "name": name, "kind": kind, "balance": 0}
        if key not in self.state["accounts"]:
            self.state["accounts"][key] = expected
            self._owners[owner].append(key)
        elif any(self.state["accounts"][key][field] != expected[field]
                 for field in ("owner_id", "name", "kind")):
            raise LedgerError("Account definition conflict")
        return key

    def balance(self, account):
        item = self.state["accounts"][account]
        return item["balance"] if item["kind"] == "asset" else -item["balance"]

    def post(self, transaction_id, lines, metadata=None):
        """Positive signed amounts are debits, negative amounts are credits.

        Validate all lines before changing any balance. An exact replay returns
        its original journal entry; reuse with different contents is rejected.
        """
        if not transaction_id or not lines:
            raise LedgerError("Transaction ID and journal lines are required")
        if any(type(amount) is not int for _, amount in lines):
            raise LedgerError("Journal amounts must be integer cents")
        candidate = {"transaction_id": transaction_id,
                     "lines": [{"account_id": key, "signed_cents": amount} for key, amount in lines],
                     "metadata": metadata or {}}
        previous = self._transactions.get(transaction_id)
        if previous is not None:
            if previous != candidate:
                raise LedgerError("Transaction ID already used with different contents")
            return previous
        changes = defaultdict(int)
        owners = defaultdict(int)
        for key, amount in lines:
            account = self.state["accounts"].get(key)
            if account is None:
                raise LedgerError(f"Unknown account: {key}")
            changes[key] += amount
            owners[account["owner_id"]] += amount
        if sum(changes.values()) != 0 or any(owners.values()):
            raise LedgerError("Debits and credits must balance for every entity")
        for key, amount in changes.items():
            account = self.state["accounts"][key]
            after = account["balance"] + amount
            if account["kind"] == "asset" and after < 0:
                raise LedgerError(f"Insufficient funds or assets: {key}")
            if account["kind"] == "liability" and after > 0:
                raise LedgerError(f"Liability cannot be overpaid: {key}")
        for key, amount in changes.items():
            self.state["accounts"][key]["balance"] += amount
        self.state["journal"].append(candidate)
        self._transactions[transaction_id] = candidate
        return candidate

    def sheet(self, owner):
        groups = {"asset": {}, "liability": {}, "equity": {}}
        for key in self._owners.get(owner, []):
            account = self.state["accounts"][key]
            groups[account["kind"]][account["name"]] = self.balance(key)
        totals = {kind: sum(accounts.values()) for kind, accounts in groups.items()}
        return {"assets": groups["asset"], "liabilities": groups["liability"],
                "equity": groups["equity"], "assets_cents": totals["asset"],
                "liabilities_cents": totals["liability"], "equity_cents": totals["equity"],
                "balanced": totals["asset"] == totals["liability"] + totals["equity"]}

    def audit(self):
        """Reconstruct balances from history, also checking each entity."""
        reconstructed = defaultdict(int)
        ids = set()
        for entry in self.state["journal"]:
            if entry["transaction_id"] in ids:
                raise LedgerError("Duplicate journal transaction")
            ids.add(entry["transaction_id"])
            owners = defaultdict(int)
            for line in entry["lines"]:
                key, amount = line["account_id"], line["signed_cents"]
                reconstructed[key] += amount
                owners[self.state["accounts"][key]["owner_id"]] += amount
            if any(owners.values()):
                raise LedgerError("Unbalanced journal history")
        for key, account in self.state["accounts"].items():
            if reconstructed[key] != account["balance"]:
                raise LedgerError("Journal and account balance disagree")
            if account["kind"] == "asset" and account["balance"] < 0:
                raise LedgerError("Negative asset")
            if account["kind"] == "liability" and account["balance"] > 0:
                raise LedgerError("Negative liability")
        return {"balanced": True, "journal_matches_balances": True,
                "transaction_count": len(ids), "account_count": len(reconstructed)}
