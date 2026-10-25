# Business and Bank Credit Workflow

This workflow connects a business payroll decision to a bank underwriting decision, borrower acceptance, and a real simulated loan. Each role observes a captured financial state and can only call its own tools. The backend controls amounts, eligibility, maturity, and settlement.

Live mode uses the existing Nebius adapter and configured Nemotron model. Explicit demo mode uses deterministic controllers and requires no credentials. These are separate model conversations with role-specific tools; they do not run thousands of model calls automatically in the simulation loop. Live model access remains unverified until account credentials are configured.

## Run a successful demo

Start the server using [the README](../README.md). In another PowerShell terminal:

```powershell
$world = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/worlds -ContentType application/json -Body '{}'
$base = 'http://127.0.0.1:8000/api/worlds/' + $world.simulation_id
$business = Invoke-RestMethod -Uri "$base/entities/business_1"
$expense = @{ transaction_id='initial-expense'; payer_id='business_1'; receiver_id='business_2'; amount_cents=$business.balance_sheet.assets.deposit } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/payments" -ContentType application/json -Body $expense
$creditUrl = "$base/businesses/business_1/credit-runs"
$run = Invoke-RestMethod -Method Post -Uri $creditUrl -ContentType application/json -Body '{"request_id":"payroll-review-1","mode":"demo","max_amount_cents":500000,"auto_settle":true}'
$run.status
$run.trace | Select-Object sequence, role, actor_id, tool, status
$run.settlement
Invoke-RestMethod -Uri "$base/audit"
```

The initial expense transfers existing deposits to another business, creating a real payroll shortfall rather than deleting funds. The workflow inspects that gap, requests credit, assesses the bank, accepts a qualifying offer, and issues the loan. Advance one tick to see the existing wage engine use the funded deposits. The workflow itself does not run payroll or advance time.

For a decline scenario, create `{"scenario":"credit_crunch"}`, apply a 40% risky-asset shock to `bank_1`, then run the same business’s credit review. Frozen deposits count as unavailable cash. The insolvent bank fails underwriting and does not lend. [credit_demo.json](./credit_demo.json) contains calculated settled and declined traces, clearly marked as demo mode.

## Request and response

`POST /api/worlds/{id}/businesses/{business_id}/credit-runs` accepts:

```json
{"request_id":"payroll-review-1","mode":"live","max_amount_cents":500000,"auto_settle":false}
```

Only `request_id` is required. Mode defaults to live; the maximum authorized amount defaults to 500,000 cents and must be a positive integer no greater than that value. `auto_settle` defaults to false. Live mode uses [the existing credential setup](./CENTRAL_BANK_AGENT.md); missing credentials return 503 without a demo fallback.

Reports contain source simulation/business/bank IDs, source tick/hash, engine version, request, provider/model for each role, captured facts, the business proposal, bank decision/assessment, borrower acceptance, role traces, settlement receipt, and any error.

Statuses:

| Status | Meaning |
| --- | --- |
| `running` | A role is still evaluating the captured snapshot. |
| `not_requested` | The business chose not to request credit. |
| `declined` | The bank declined, or the business rejected the bank’s offer. Inspect the decision and acceptance flag. |
| `approved` | The bank approved and the business accepted; funds have not settled. |
| `settled` | The matching loan, deposits, and debt were committed and audited. |
| `failed` | Provider/protocol failure or the bounded role loop ended without a valid decision. |

If authorized automatic settlement is blocked by a stale snapshot, the report stays `approved`, has no settlement, and records an error. Do not display it as funded. A manual settlement committed concurrently remains settled and cannot be overwritten by a late automatic error.

`GET /api/worlds/{id}/businesses/{business_id}/credit-runs` lists reports. `GET /api/credit-runs/{run_id}` retrieves one report, including progress saved after every tool call. Requests run synchronously; allow enough time for live inference. There is no cancellation queue or crash lease recovery yet.

## Decisions and deterministic policy

The business inspects actual deposits, available deposits, debt/headroom, payroll, loan maturity, recorded sales/wages over the last five ticks, and supplier payables/receivables with the next bill due. The gap is payroll minus available deposits, floored at zero. An insolvent home bank makes those deposits unavailable under the existing freeze rule. This is observed history, not a cash-flow forecast or verified real-world credit score.

The business can request principal no greater than the gap and caller-authorized cap, or continue without credit. Requests are bound to the business in the URL and its existing home bank; the model cannot change borrower or lender identities.

The bank must inspect and assess before deciding. It may offer lower principal, but cannot exceed the business proposal. Approval requires the exact offered amount to have passed deterministic assessment in this run. The policy checks:

- Active borrower and bank; existing bank lending constraints.
- Customer debt of at most 500,000 cents and bank customer loans no greater than five times equity.
- No already-due outstanding business loan requiring refinancing first.
- After the proposed issuance, at least 8% bank capital/assets and 10% reserves/customer deposits, plus the existing interbank-default restrictions.

The bank may decline even an eligible request. The business then separately reviews an approved offer and accepts or rejects it. The demo bank caps offers at remaining credit headroom; the demo business rejects partial offers that do not fully cover the observed payroll gap. A live business may accept a useful partial offer, but it must call the acceptance tool explicitly.

Terms remain principal-only. New business debt matures after five ticks; additional borrowing preserves an existing loan’s maturity. Legacy loans may have no recorded maturity. No interest, collateral pledges, or competing-bank shopping is invented. These workflow risk checks are stricter than the earlier low-level loan endpoint because they also check projected bank ratios.

## Role tools and safeguards

Business proposal tools: `inspect_business`, `request_credit`, `continue_without_credit`.

Bank tools: `inspect_credit`, `assess_credit`, `decide_credit`.

Business acceptance tools: `review_offer`, `accept_offer`, `decline_offer`.

Each phase requires inspection before a decision. Unknown tools, cross-role commands, malformed arguments, over-cap requests, and unassessed approvals are rejected with feedback. Each phase allows at most eight model turns and four calls per turn. Public rationales are saved; hidden reasoning is not exposed. Traces identify each actor, role, tool, arguments, result, and acceptance/rejection status.

## Settlement, authorization, and retries

With `auto_settle: false`, an approved run only proposes a loan. To settle it:

```powershell
$settleUrl = 'http://127.0.0.1:8000/api/credit-runs/' + $run.run_id + '/settle'
Invoke-RestMethod -Method Post -Uri $settleUrl -ContentType application/json -Body '{"transaction_id":"settle-payroll-review-1"}'
```

With `auto_settle: true`, the caller authorizes the engine to settle a bank-approved, borrower-accepted loan within the request’s cap. Models cannot enable this flag. The engine uses a reserved transaction ID, `credit:<run_id>`.

Settlement verifies the source snapshot has not changed, rechecks underwriting and principal bounds, issues the loan through the balanced ledger, and commits the loan, source events, report, and receipt in one transaction. Issuance increases business deposits and debt, bank loan assets and deposit liabilities. It does not create new bank reserves. Failure leaves no partial loan or settlement record.

`request_id` is scoped by world and business. Identical retries return the stored report; conflicting parameters or duplicate running requests return 409. A settled run cannot lend again. Retry an uncertain manual settlement with the original transaction ID; another ID for an already-settled run returns 409. Any source mutation before funding requires a new review. Approved automatic runs interrupted before funding can retry settlement without rerunning the models.

Do not manually use reserved transaction prefixes `genesis:`, `tick:`, `fork:`, or `credit:`. Settlement emits `loan_issued` and `agent_credit_settled`; reviews and declined offers leave financial state unchanged. Financial validation is not user authentication: this remains a local development API.

## What comes next

Supplier offers, negotiated contracts, down payments, and future supplier obligations are now available through [the supplier payment workflow](./SUPPLIER_PAYMENTS.md). External payment and banking integrations, live-provider verification, and automatic per-tick LLM scheduling remain separate work.
