# Fork Reality Model and UI Integration

Fork Reality takes one committed economy snapshot and calculates three isolated futures: no intervention, emergency bank lending, and direct household support. The source world remains unchanged. Each branch has its own ledger, events, obligations, and simulation ID.

## Run a comparison

Start the backend using [the README](../README.md). In a second PowerShell terminal:

```powershell
$world = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/worlds -ContentType application/json -Body '{"seed":42,"scenario":"credit_crunch"}'
$base = 'http://127.0.0.1:8000/api/worlds/' + $world.simulation_id
Invoke-RestMethod -Method Post -Uri "$base/shocks" -ContentType application/json -Body '{"transaction_id":"shock-1","bank_id":"bank_1","loss_bps":4000}'
$comparison = Invoke-RestMethod -Method Post -Uri "$base/forks" -ContentType application/json -Body '{"request_id":"compare-1","bank_id":"bank_1","budget_cents":1000000,"ticks":12}'
$comparison.branches | Select-Object strategy, metrics
Invoke-RestMethod -Uri ('http://127.0.0.1:8000/api/forks/' + $comparison.fork_id)
```

Use the existing crisis API to apply a shock **before** forking. Forking neither applies nor repeats shocks. It also works at later ticks, but cannot undo defaults or settlements already in the source snapshot.

Each intervention branch receives the same additional total budget, expressed in integer cents. Default budget: 1,000,000 cents ($10,000). Default horizon: 12 days; allowed horizon: 1–100 days. The no-intervention branch receives zero additional support. Interventions settle immediately at the source tick, followed by the requested simulation days.

## Financial treatment

Emergency bank lending credits the target bank’s reserves and creates an equal central-bank debt liability. The central bank records a matching loan asset and issued-reserve liability. Bank equity does not change. Liquidity support cannot directly repair insolvency and may worsen capital/assets ratios by increasing assets without capital. The experiment allows lending to an insolvent bank so this limitation can be tested explicitly.

Household support is distributed equally across all households, with remainder cents assigned by sorted household ID. A household receives deposits and an equity gain; its bank receives matching reserves and a deposit liability. The government records the fiscal expense as an equity reduction and matching debt to the central bank. The central bank records a government loan asset and issued reserves. Incoming support does not restore an insolvent commercial bank’s equity, so deposits there may remain frozen under existing crisis rules.

These are explicit simplified public-sector financing operations. They are not transfers from an unexplained cash pool. Public loans have no interest, repayment, maturity, collateral, or loss provisioning in this milestone. Household fiscal transfers are not loans to households. There is no automatic recapitalization, deposit insurance, business reopening, or hiring.

## Costs and recommendation

Every branch reports:

- `public_support_disbursed_cents`: cumulative gross support disbursed. The compatibility field `public_intervention_cost_cents` has the same value.
- `fiscal_transfer_cost_cents`: cumulative household grants financed by government debt.
- `public_loan_outstanding_cents`: central-bank claims on banks plus government. This is an asset/debt stock, not an additional expense. Government grant financing overlaps with fiscal transfers, so do not add these fields together as total cost.

The report’s `recommended_strategy` is currently **rule-based**, using this priority: maximize final employed households, then minimize business defaults, insolvent banks, stressed banks, and gross support disbursed. `tied_strategies` lists exact ties; the displayed winner then follows branch order. No learned model or AI recommendation is claimed.

The recommendation only describes this snapshot, seed, horizon, and chosen objective. It is not an estimate of real-world policy effectiveness or net taxpayer loss. Change the budget, horizon, and seed to explore sensitivity. Tests verify repeatability across several seeds; they do not establish that one strategy always wins.

For the default seed-42 demo at 12 days, the calculated example currently shows:

| Strategy | Employed households | Business defaults | Gross additional support |
| --- | --- | --- | --- |
| No intervention | 15 | 5 | $0 |
| Bank lending | 15 | 5 | $10,000 |
| Household cash | 20 | 4 | $10,000 |

These values are calculated by [the example exporter](../scripts/export_contract.py), not embedded in simulation logic. Full timelines, audits, and deltas are in [fork_demo.json](./fork_demo.json).

## UI contract

`POST /api/worlds/{id}/forks` accepts `request_id`, `bank_id`, `budget_cents`, and `ticks`. Except for `request_id`, fields have defaults. Budgets must be positive integer cents up to 1,000,000,000,000. The bank must exist and be a commercial bank. The response contains:

- `fork_id`, source simulation/tick, end tick, seed, engine version, and source snapshot SHA-256.
- `source_event_sequence`, the last inherited event cursor.
- `initial_metrics`, identical pre-intervention source conditions for every branch.
- Three branch records with strategy, simulation ID, final metrics, audit, and deltas versus no intervention.
- A timeline per branch with `ticks + 1` points: immediate post-intervention metrics at the source tick, then each completed day. Use the same tick axis and chart scales.
- A transparent recommendation rule and cost definition.

Inspect a branch through the existing world, institution, event, network, transaction, and audit endpoints. To animate only new branch activity, fetch branch events after `source_event_sequence`. A branch’s inherited historical events retain sequence order but use the branch’s simulation ID. Branch worlds expose `lineage`; source worlds have null lineage unless they were themselves forked earlier.

`GET /api/worlds/{id}/forks` lists saved report summaries. `GET /api/forks/{fork_id}` retrieves the original immutable report. You may continue stepping a branch after comparison, but those later changes do not rewrite the saved report; label the report horizon separately from a branch’s latest live tick.

## Isolation, retries, and persistence

The backend copies one committed SQLite checkpoint, including financial accounts, obligations, seed, and event history. Every branch starts from a deep copy. Future consumption choices derive from the same seed and absolute tick; neither branch IDs nor strategy names enter the random seed. Actions can differ as balances and business statuses diverge.

Supplier contracts, raw-material stock/carrying values, and invoice due dates are also isolated in each branch. Supplier claims settle or default independently. Metrics and deltas include outstanding trade credit and supplier contract defaults.

Computation runs synchronously outside the SQLite write lock. The source can continue while the experiment runs; the report still refers to its captured snapshot. Keep a loading state and avoid a short browser timeout for larger worlds. Population and tick limits are input limits, not a latency guarantee.

All three branch worlds, the source snapshot, and the comparison report publish in one transaction. Failure creates no partial set. `request_id` is scoped to the source world: retry an uncertain request with identical contents to recover the original report, even after the source advances. Reuse with different parameters returns 409. Concurrent identical requests may compute twice, but publish and return only one set. New request IDs capture new experiments.

Original transaction IDs remain valid inside each isolated branch. IDs are scoped by simulation ID; use `(simulation_id, transaction_id)` and `(simulation_id, event sequence)` as UI keys. Do not manually use the reserved `genesis:`, `tick:`, or `fork:` transaction prefixes.

## Direct interventions

For a manual experiment, `POST /api/worlds/{id}/interventions` accepts either:

```json
{"transaction_id":"manual-bank-support","kind":"bank_lending","bank_id":"bank_1","amount_cents":1000000}
```

or:

```json
{"transaction_id":"manual-household-support","kind":"household_cash","amount_cents":1000000}
```

Bank lending requires `bank_id`; household cash forbids it. The endpoint returns the settled journal receipt and uses the same replay protection as other payments. Fetch current state/events afterward. Manual interventions mutate that world, whereas the fork API protects the source and intervenes only in its copies. Existing source interventions and their cumulative costs are inherited by every future.
