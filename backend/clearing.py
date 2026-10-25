"""Conservative integer-cent interbank clearing with senior deposit claims.

Descending fixed-point iteration starts with full promised payments. Each
bank pays creditors pro rata from liquidatable assets plus incoming payments,
after protecting customer deposits. Fractional cents are retained, never minted.
This is a simplified Eisenberg–Noe-style model, not full bank resolution.
"""

from backend.ledger import LedgerError


def clear_payments(obligations, liquid_assets, protected_deposits, max_iterations=10_000):
    banks = sorted(liquid_assets)
    if any(type(value) is not int or value < 0
           for value in [*liquid_assets.values(), *protected_deposits.values()]):
        raise LedgerError("Clearing assets and deposits must be nonnegative integer cents")
    nominal = {}
    for (debtor, creditor), amount in obligations.items():
        if debtor not in banks or creditor not in banks or debtor == creditor:
            raise LedgerError("Invalid interbank counterparty")
        if type(amount) is not int or amount < 0:
            raise LedgerError("Interbank obligations must be nonnegative integer cents")
        nominal[debtor, creditor] = amount
    payments = nominal.copy()
    totals = {bank: sum(amount for (debtor, _), amount in nominal.items() if debtor == bank)
              for bank in banks}
    for iteration in range(1, max_iterations + 1):
        incoming = {bank: sum(amount for (_, creditor), amount in payments.items() if creditor == bank)
                    for bank in banks}
        budgets = {bank: min(totals[bank], max(0, liquid_assets[bank] + incoming[bank]
                                              - protected_deposits.get(bank, 0))) for bank in banks}
        updated = {(debtor, creditor): (amount * budgets[debtor] // totals[debtor]
                                         if totals[debtor] else 0)
                   for (debtor, creditor), amount in nominal.items()}
        if updated == payments:
            return {"payments": payments, "iterations": iteration}
        payments = updated
    raise LedgerError("Interbank clearing did not converge; no settlement was posted")
