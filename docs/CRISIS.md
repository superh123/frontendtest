# Bank Crisis Model and Demo

Milestone 2 connects a bank asset loss to lending constraints, missed business obligations, job losses, and losses on interbank exposures. Outcomes come from ledger transactions and documented rules. The rules are stylized; the results are not predictions of a real economy.

## Run the demo

Start the backend using [the setup instructions](../README.md), then run in PowerShell:

```powershell
$world = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/worlds -ContentType application/json -Body '{"seed":42,"scenario":"credit_crunch"}'
$base = 'http://127.0.0.1:8000/api/worlds/' + $world.simulation_id
Invoke-RestMethod -Method Post -Uri "$base/shocks" -ContentType application/json -Body '{"transaction_id":"demo-shock-1","bank_id":"bank_1","loss_bps":4000}'
Invoke-RestMethod -Method Post -Uri "$base/step" -ContentType application/json -Body '{"ticks":12}'
Invoke-RestMethod -Uri "$base/network"
Invoke-RestMethod -Uri "$base/events?after=0&limit=1000"
Invoke-RestMethod -Uri "$base/audit"
```

Page through events using `next_after` while `has_more` is true. Create another world using the same seed/configuration and step 12 days without applying a shock to compare the healthy baseline. To test interventions from the same shocked state, use [the Fork Reality API](./FORK_REALITY.md).

Regenerate [the calculated example](./crisis_demo.json) with `python -m scripts.export_contract`. It includes baseline and shocked metrics, financial exposures, the shock receipt, default events, and an accounting audit.

## Initial conditions

Both starting scenarios form a directed ring of interbank loans when there are at least two banks. Each bank lends to the next bank. Every obligation has the same principal: half the smallest pre-portfolio bank reserve balance. Simultaneous origination transfers reserves and records matching loan assets and debt liabilities. These obligations mature at tick 5 and clear once; new interbank borrowing is not yet modeled.

Banks allocate reserve assets to a risky portfolio while keeping the greater of 20% of their pre-allocation reserves or 15% of customer deposits in reserves. This is an explicit opening portfolio allocation; purchases from outside the simulated economy are represented as an asset swap.

The `standard` scenario retains the original bank equity endowment of 10,000,000 cents. It deliberately has high loss-absorbing capital.

The `credit_crunch` scenario first issues each business a working-capital loan of two days’ payroll, with a minimum of 10,000 and maximum of 300,000 cents. Businesses pay initial setup-service expenses to households, retaining at least 10,000 cents or 1.5 days’ payroll. These transfers create financing dependence without deleting money. This is a synthetic starting allocation, not a model of real setup-service providers.

Each bank’s opening equity is then set to the maximum of 100,000 cents, one-sixth of customer deposits, or customer loan assets minus 80% of deposits plus 100,000 cents. An explicit genesis capital entry adjusts endowed reserves and equity. This liquidity floor keeps unusual population configurations financially feasible. No subsequent shock or intervention uses this initialization mechanism.

## Shocks and lending

A shock writes off `floor(remaining risky assets × loss_bps / 10000)`. Risky assets and bank equity fall by the same amount. Customer deposits and reserves do not change. A loss that rounds to zero is rejected.

A bank is insolvent when equity is zero or negative. It is stressed when capital/assets is below 8%, reserves/customer deposits is below 10%, or it has previously defaulted on an interbank obligation. Zero customer deposits gives a liquidity ratio of one. Otherwise it is active. These are engineering assumptions, not regulatory thresholds.

Only active banks lend. Customer debt is capped at 500,000 cents and bank customer-loan assets at five times equity. Insolvent banks freeze outgoing customer trading payments and loan repayments; incoming deposits are still possible. Stressed banks can settle customer payments when reserves permit, but cannot extend or refinance credit.

## Business obligations and default

New business debt matures after five ticks. On maturity, the business attempts repayment using cash above one payroll buffer. Remaining principal is extended five ticks only if current lending rules allow it. Extension changes the maturity and emits a trace; it creates no new deposits. Failed refinancing on two consecutive ticks closes the business. Fully repaid loans stop the overdue counter.

Before paying wages, active businesses request credit for a payroll cash shortfall. Unpaid wages on two consecutive ticks also close the business. Wage attempts are ordered by household ID insertion order; some employees may receive wages before cash runs out. A later salary shortfall is not rolled back as a full payroll batch.

Closure writes off remaining principal with zero modeled recovery. Bank loan assets and equity fall; business debt is extinguished with a matching equity gain. The business stops trading and its workers lose their employer links. Existing deposits remain recorded. There is no liquidation/recovery auction, deposit insurance, hiring, or business reopening yet.

## Interbank clearing

The implementation is inspired by the fixed-point payment framework in [Eisenberg and Noe’s Systemic Risk in Financial Systems](https://pubsonline.informs.org/doi/10.1287/mnsc.47.2.236.9835). The original framework computes payments jointly under limited liability and proportional repayment. Our implementation adds senior customer-deposit protection and integer-cent rounding, and should be described as a simplified variant.

At maturity, each bank’s interbank payment budget is the lesser of its due obligations and the nonnegative remainder of:

`reserves + risky assets at current book value + incoming clearing payments - customer deposits`

Customer loans are excluded from immediately liquidatable assets. Payments are split across interbank creditors in proportion to nominal obligations, rounding each payment down to integer cents. Remainder cents stay with the payer. Start from full nominal payments and iterate downward until unchanged, with a 10,000-iteration guard. Failure to converge rejects the operation; SQLite saves no partial tick.

The final payments settle simultaneously in one journal transaction. Risky assets are liquidated at current book value only when needed for net reserve outflows. This settlement introduces no customer deposits. Unpaid interbank balances are written off on both sides: creditors recognize losses and debtors recognize debt relief. The affected borrower is flagged as an interbank defaulter. Senior customer deposits are left outstanding; an insolvent bank can still have a deposit shortfall, and resolution is not modeled.

This treatment intentionally omits fire-sale discounts, interest, external creditor classes beyond customer deposits, and recovery costs. Cyclic obligations may settle through netting without gross reserve transfers. Conservative rounding can retain fewer than one cent per outgoing edge relative to exact proportional payments; no uniqueness claim is made for this variant.

## Tick order and inspection

1. Clear due interbank obligations, recalculate bank health, and attempt due supplier bills. Repeated unpaid supplier bills default the buyer and write off matching claims.
2. Consume raw materials at recorded carrying cost, process business loan maturities, and request payroll credit.
3. Attempt wages, track missed payroll, and close defaulting businesses.
4. Attempt household consumption. Unemployed households limit their budget to 10% of current deposits. Choices of closed businesses are skipped.
5. Recalculate bank status, record tick metrics, and audit the ledger.

The inspector exposes bank ratios, lending availability, business maturity/counters, and balance sheets. Network exposures give borrower/lender IDs and remaining principal. Events connect asset loss, rejected credit, loan writeoff, business closure, job loss, and interbank default. All histories and obligations survive a restart in the SQLite world checkpoint.

Older milestone-1 worlds continue to load and run their existing accounts. They do not receive hidden portfolio assets or interbank obligations during loading. Create a new world to use the new starting scenarios.
