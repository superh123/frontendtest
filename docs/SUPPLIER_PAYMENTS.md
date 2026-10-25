# Supplier Negotiation and Contract Payments

The buyer requests quotes from two real businesses in the simulated world. Supplier roles inspect their stock and policy, quote terms, and evaluate one buyer counteroffer. The buyer selects an eligible original or revised offer. Contract creation delivers material stock, settles the down payment, and records the future bill as a payable and matching receivable. Everything uses the internal simulation ledger; there is no external x402 or real-money settlement yet.

## Run the complete demo

Start the backend using [the README](../README.md), then run in a second PowerShell terminal:

```powershell
$world = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/worlds -ContentType application/json -Body '{}'
$base = 'http://127.0.0.1:8000/api/worlds/' + $world.simulation_id
$buyUrl = "$base/businesses/business_1/procurement-runs"
$run = Invoke-RestMethod -Method Post -Uri $buyUrl -ContentType application/json -Body '{"request_id":"inventory-1","mode":"demo","quantity":20,"max_total_cents":100000,"auto_settle":true}'
$run.offers
$run.negotiation
$run.selected_offer
$contract = $run.settlement.contract
$contract
$days = $contract.due_tick - $world.simulation_tick
$stepBody = @{ticks=$days} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/step" -ContentType application/json -Body $stepBody
Invoke-RestMethod -Uri ($base + '/contracts/' + $contract.contract_id)
Invoke-RestMethod -Uri "$base/audit"
```

The default example obtains two original quotes and one accepted revised quote. It buys 20 units for 10,160 cents, pays 2,032 cents upfront, and records 8,128 cents due at tick 5. Those values are calculated from the seeded world, not embedded in engine logic. [procurement_demo.json](./procurement_demo.json) contains the actual negotiation trace, creation receipt, final paid contract, and audit with stable illustrative IDs.

## Request and modes

`POST /api/worlds/{id}/businesses/{buyer_id}/procurement-runs` accepts:

```json
{"request_id":"inventory-1","mode":"demo","supplier_ids":["business_2","business_3"],"quantity":20,"max_total_cents":100000,"auto_settle":false}
```

Only `request_id` is required. Mode defaults to live. Quantity defaults to 20 and accepts integer values from 1–1,000. The full-invoice budget defaults to 100,000 cents and accepts up to 1,000,000,000 cents. If supplier IDs are omitted/null, choose the first two other active businesses by sorted ID. Explicit lists require two different supplier businesses, neither equal to the buyer. A world needs at least three active businesses for this workflow.

Live mode uses [the existing Nebius configuration](./CENTRAL_BANK_AGENT.md), with separate buyer and supplier conversations on the configured model. Provider access remains unverified without live credentials. Demo mode uses `deterministic_demo` / `demo-supply-v1`; it is not an AI inference transcript. No automatic fallback is performed.

## Negotiation and policy

Each supplier must inspect before quoting or declining. A quote specifies unit price, down-payment basis points, and days until the remaining balance is due. The backend computes quantity, total, and rounded-up initial payment; the model cannot supply inconsistent totals.

The supplier pricing floor is the greater of one cent, 80% of its reference price, or the ceiling of current per-unit inventory carrying cost. Reference price is half the business’s seeded retail price, floored at one cent. The supplier requires at least 20% upfront and allows at most 10 deferred ticks. The schema permits wider proposals, but policy rejects a quote or accepted counteroffer outside those limits. This is an explicit synthetic pricing model, not a real market calibration.

After inspecting actual offers and settlement eligibility, the buyer can select one, decline, or negotiate once with a supplier that already quoted. The targeted supplier reviews the exact proposed terms and accepts or declines. Acceptance creates a second offer from that supplier. Declining a counteroffer leaves its original quote available. The buyer then inspects the final offers and selects an existing eligible offer or declines. There is no second negotiation round.

Selection checks the full budget, stock, active counterparties, spendable buyer deposits, and bank settlement liquidity by previewing a complete contract in an isolated copy. A low down payment cannot hide a future invoice above the caller’s full budget. Insufficient cash, frozen buyer deposits, or missing stock makes an offer ineligible.

The demo requests a 10% quote discount, 20% upfront, and five ticks to pay, then prefers eligible offers with lower immediate cash use, lower full cost, and longer terms. Live models can choose differently within validated bounds. Each conversation is bounded to six model turns and four tool calls per turn. Unknown tools, invented offer IDs, uninspected decisions, and invalid terms generate rejected trace entries with feedback.

## Contract accounting and materials

New worlds explicitly give each business 1,000 units of generic raw material with zero opening book cost. Older saved worlds without stock fields retain zero supplier stock; create a fresh world for the demo. These are raw inputs, separate from the existing unlimited finished-goods consumption market.

On delivery, the buyer records the entire invoice as a material asset, reduces deposits by the initial payment, and records the remainder as a liability. The supplier receives the deposit payment, records the matching receivable, recognizes sales, and removes the proportional book cost of shipped materials. Bank deposit liabilities and cross-bank reserves move by the paid amount. Physical units move from supplier to buyer exactly once.

The supplier’s shipped cost is `floor(material carrying value × shipped units / stock before delivery)`. This pooled average-cost rule retains rounding cents in remaining stock and releases the entire cost when all units leave. Each active business consumes up to one material unit per employee at the start of its payroll preparation. Positive consumption cost reduces material assets and equity; zero-cost consumption only reduces physical stock. Finished-goods production is not yet gated by material availability, so raw-input inventory is finite while household goods supply retains its earlier simplified rule.

Paying the deferred balance reduces buyer deposits/payables and supplier receivables while increasing supplier deposits. It does not repeat delivery or recognize sales twice. Supplier payables match receivables in the audit, and outstanding amounts appear as `trade_credit` network exposures. Metrics show `trade_credit_outstanding_cents` and `supplier_contract_defaults`.

## Creation, authorization, and future collection

With `auto_settle: false`, negotiation returns `ready` without changing the source economy. To create the selected contract:

```powershell
$settleUrl = 'http://127.0.0.1:8000/api/procurement-runs/' + $run.run_id + '/settle'
Invoke-RestMethod -Method Post -Uri $settleUrl -ContentType application/json -Body '{"transaction_id":"inventory-down-payment-1"}'
```

With `auto_settle: true`, the caller authorizes creation of the selected contract within the full invoice budget. The engine uses `procurement:<run_id>`. Creating the contract authorizes both the down payment and automatic collection of its recorded balance at maturity. Models cannot enable this flag themselves. Delivery, payment, financial claims, world events, report, and receipt commit in one transaction.

Contract creation requires the exact reviewed source snapshot. Any intervening world mutation returns 409 and requires a new procurement run. Identical run retries return the stored result; changed parameters or duplicate running requests return 409. Contract creation settles once even under concurrent retries. Manual settlement retries must use the original transaction ID. Private backend prefixes `genesis:`, `tick:`, `fork:`, `credit:`, and `procurement:` are reserved.

On each tick, due supplier bills are attempted after interbank clearing and before business payroll financing. Payments are all-or-nothing; no automatic invoice refinancing is added. One failure marks the bill overdue. Failure on the next tick defaults the buyer through the existing business-default path, writes off its bank debt and all remaining supplier liabilities, closes it, and releases its employees. Each supplier recognizes its corresponding receivable loss; the buyer records debt relief. No recovery auction is modeled. A supplier that closes can still collect an existing receivable during wind-down.

## Inspector, statuses, and current state

Procurement statuses are `running`, `ready`, `declined`, `contracted`, and `failed`. `contracted` means delivery/down payment succeeded, not that the invoice is fully paid. The run’s creation receipt is historical. Read `GET /api/worlds/{id}/contracts/{contract_id}` for current status: `open`, `overdue`, `paid`, or `defaulted`, with total, paid, outstanding, written-off amounts, and due tick.

Other endpoints:

- `GET /api/worlds/{id}/businesses/{buyer_id}/procurement-runs`: saved reports for a buyer.
- `GET /api/procurement-runs/{run_id}`: role traces, offers, counteroffer, selection, and historical creation receipt.
- `GET /api/worlds/{id}/contracts`: all current contracts.
- `POST /api/worlds/{id}/contracts/{contract_id}/pay`: pay the entire remaining balance early or while overdue, using `{"transaction_id":"balance-payment-1"}`. Duplicate IDs return the original receipt; another payment after full settlement is rejected.

Show original/revised offers separately, total versus upfront cost, remaining liability, material units, and the negotiation rationale. Events connect `supplier_contract_created`, `supplier_down_payment`, `supplier_balance_paid`, `supplier_payment_rejected`, `supplier_contract_default`, and positive-cost `materials_consumed` to finances. All role traces and snapshots persist in SQLite. Counterparty defaults and due payments remain isolated when Fork Reality copies a world.

Provider failures save failed reports, and workflow status must be checked even when HTTP returns 200. Successfully collected quotes remain inspectable. An automatic creation blocked by a stale snapshot remains `ready` with an error and no contract; concurrent completed settlement cannot be overwritten by that error. The service is synchronous, has no cancellation/lease recovery, and is a local unauthenticated development API.

External x402 payments, external banking adapters, live inference verification, shipping delays, invoice cancellation, partial balance payments, and richer production constraints are subsequent work.
