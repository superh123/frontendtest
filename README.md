# Economy God Mode Backend

Milestone 7 adds **Play/Pause, speed control, safe reset, and reconnectable live events** for the frontend demo. Automatic ticks use atomic SQLite scheduling, while Server-Sent Events replay committed financial activity. The backend also includes supplier negotiation and contract payments, business/bank credit agents, the central-bank workflow, Fork Reality, crisis propagation, and a balanced ledger. Live roles use configured Nemotron on Nebius; demo controllers are explicitly labeled. Live inference remains unverified, and external payment integrations remain unimplemented.

The product direction is saved in [UI_PLAN.md](./UI_PLAN.md). Frontend integration details are in [docs/API.md](./docs/API.md).

## Frontend demo

The React frontend lives in [`apps/web`](./apps/web/README.md). It includes the local Earth globe, a Canvas miniature of San Francisco, and the full healthy-world → crisis → intervention → comparison UI path. Its economics and mock agent responses currently come from committed fixtures; it does not call the Python API yet. The backend integration contract is documented in [docs/API.md](./docs/API.md).

From the repository root, use Node 22 or 24 and run:

```sh
npm install
npm run dev
npm test
npm run build
```

Open <http://127.0.0.1:5173/>. The frontend does not require the Python service for the offline demo. See the [frontend README](./apps/web/README.md) for the supported fixture scenario and controls.

## Run locally

Prerequisites: Git and Python 3.11 or newer with pip and venv. The backend was tested with Python 3.11 on Windows. SQLite is included with Python; no separate database server, Node.js, or Docker is needed. Simulation and explicit demo-agent mode need no cloud account or API keys. Live agent mode requires Nebius credentials and a tool-capable model. The fixture-driven frontend lives in `apps/web` and runs independently of the backend.

Clone the repository:

```sh
git clone https://github.com/shivanginarayan/CalHacks.git
cd CalHacks
```

On Windows, run these commands from the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

On macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Run commands from the repository root. Calling the virtual environment's Python directly avoids activation and PowerShell execution-policy requirements. The exact tested dependency versions are in [requirements.lock.txt](./requirements.lock.txt); [requirements.txt](./requirements.txt) records the supported direct dependency ranges. The same lock file is used on all platforms, but only Windows execution has been verified so far.

Open the interactive API at <http://127.0.0.1:8000/docs>. Health is available at <http://127.0.0.1:8000/health>.

Keep the server terminal open and use a second terminal for API requests. Stop the server with Ctrl+C. Simulation data survives restarts. No environment variables are required with the defaults.

## Environment configuration

The optional [environment template](./.env.example) documents the available settings. The application reads shell environment variables; copying the template to `.env` does **not** load it automatically.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ECONOMY_DB_PATH` | `data/economy.sqlite3` under the repository root | SQLite world storage. An override may be an absolute path, or a path relative to the working directory. Parent directories are created automatically. |
| `ECONOMY_CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173` | Comma-separated frontend origins, including scheme and port. |
| `NEBIUS_API_KEY` | Unset | Required for live central-bank, credit, and supplier agents. |
| `NEBIUS_MODEL` | Unset | Exact tool-capable Nemotron model ID available to your account. |
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1` | HTTPS chat-completions API base; use your account’s regional endpoint if required. |

Example overrides in PowerShell, before starting the server:

```powershell
$env:ECONOMY_DB_PATH = 'data/economy.sqlite3'
$env:ECONOMY_CORS_ORIGINS = 'http://localhost:5173,http://localhost:3000'
```

Or on macOS/Linux:

```sh
export ECONOMY_DB_PATH="data/economy.sqlite3"
export ECONOMY_CORS_ORIGINS="http://localhost:5173,http://localhost:3000"
```

The UI's API base URL should be `http://127.0.0.1:8000` on the same computer. If another service uses port 8000, start Uvicorn with `--port 8001` and update the frontend's API base URL. CORS settings identify the frontend's origin, not the backend URL. The local API has no authentication; keep this development setup on localhost.

The virtual environment, local database files, caches, and private environment files are excluded from Git. Keep the example template free of secrets. See [the central-bank agent guide](./docs/CENTRAL_BANK_AGENT.md) for credential setup, model selection, and live/demo requests.

## Try the API

Create and advance a world:

```powershell
$world = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/worlds -ContentType application/json -Body '{"seed":42,"households":40,"businesses":8,"banks":5}'
$simulationId = $world.simulation_id
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/worlds/$simulationId/step" -ContentType application/json -Body '{"ticks":1}'
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/worlds/$simulationId/audit"
```

## What works

- Seeded world creation with employment and banking relationships.
- Balance sheets and balanced journal entries for every entity.
- Same-bank and cross-bank payments, including reserve settlement.
- Explicit bank credit creation and principal repayment.
- Wages, rule-based household consumption, and rejected-payment events.
- Idempotent transaction IDs: exact retries settle once; conflicting reuse fails.
- Atomic SQLite checkpoints: balances, tick, journal, and events commit together.
- Institution inspection, historical tick metrics, paginated transactions and events.
- Typed OpenAPI contract and generated example responses for the UI.
- Idempotent bank asset shocks and live capital/liquidity indicators.
- Automatic payroll credit, business debt maturities, and refinancing decisions.
- Business closures, matching loan writeoffs, and job losses after missed obligations.
- Interbank exposures and simultaneous clearing with protected deposit claims.
- A reproducible `credit_crunch` starting scenario for the crisis demo.
- Three-way Fork Reality comparisons with isolated branch worlds and aligned timelines.
- Explicit central-bank loans and public-debt-financed household transfers.
- Separate reporting of gross support, fiscal transfers, and outstanding public loans.
- Immutable comparison reports, source snapshot hashes, and retry-safe atomic publication.
- Bounded central-bank observe/test/revise/recommend tool loop with persisted traces.
- Nebius model adapter, strict budget/argument validation, and explicit offline demo mode.
- Separate recommendation application with snapshot checks and exactly-once settlement.
- Business-to-bank payroll credit reviews with separate role tools and decision traces.
- Deterministic underwriting, counteroffers, borrower acceptance, and post-loan risk checks.
- Optional authorized automatic credit settlement, with stale-state checks and safe retries.
- Two supplier quotes, one counteroffer round, and buyer acceptance of real terms.
- Atomic delivery, down payment, matching payables/receivables, and future invoice settlement.
- Finite raw-material units, inventory carrying values, consumption costs, and supplier default losses.
- Persistent Play/Pause and speed control with atomic automatic ticks across workers.
- Retry-safe reset into a new seeded world while preserving the source history.
- Server-Sent Events with ordered replay, reconnect cursors, and idle heartbeats.

## Financial rules and assumptions

All amounts are integer USD cents. Account balances are derived from signed debit/credit entries. Each transaction balances separately for every affected institution. An audit reconstructs all balances from the journal and checks customer deposits and debts against the banks’ corresponding liabilities and assets.

Opening bank capital and customer deposits are explicit genesis endowments. Initial deposits are backed by endowed bank reserves; these operations run only at world creation. This starting allocation is an assumption of the experiment.

Wages and purchases move existing deposits and recognize changes in each customer’s equity immediately. Transfers between banks move reserves. Credit issuance creates a bank loan asset, deposit liability, borrower deposit, and borrower debt. Repayment reverses those entries and destroys the repaid deposit money.

One tick represents one day. Due interbank obligations clear first. Active businesses then attempt principal repayments/refinancing and request payroll credit when needed. Businesses attempt wages before households buy goods. A household selects a business using a seeded per-tick random stream and spends up to its fixed budget and available deposit, rounded down to whole units of the seller’s price. Unemployed households cap spending at 10% of available deposits. Purchases targeting closed businesses are skipped. Goods supply is currently unlimited.

Loans are principal-only and may be manually requested or rule-based payroll credit. Business loans mature after five ticks and may be extended under the bank’s current lending rules. Borrower debt is capped at 500,000 cents; bank lending requires at least 8% capital/assets, at least 10% reserves/customer deposits, positive equity, no prior interbank payment default, and total customer loans no greater than five times equity. These are initial simulation rules, not calibrated economics or regulatory thresholds. See [the crisis model](./docs/CRISIS.md) for the exact default and clearing assumptions.

Government and central-bank entities record public lending, reserve issuance, and debt-financed household support when requested. Bank lending adds matching reserves and debt without restoring bank equity. Household support adds deposits, reserves, and government debt. See [the Fork Reality model and walkthrough](./docs/FORK_REALITY.md) for funding and comparison rules. Taxes, rent, constrained finished-goods production, continuous autonomous agent scheduling, and external payment/banking integrations are subsequent milestones.

## Frontend connection

The UI can create a world, render relationships, inspect balance sheets, advance time, trigger a bank shock, compare three futures, run the central-bank workflow, poll traces/events, and apply a completed recommendation. New worlds start paused; use Play/Pause and speed controls to advance automatically, or step manually while paused. Reset creates a fresh world and preserves the source. See [the playback and SSE integration guide](./docs/PLAYBACK.md) for control requests, reconnect handling, and JavaScript examples. Fork Reality’s own ranking remains rule-based. Agent reports separately identify live provider/model or deterministic demo mode; preserve that distinction in the inspector. The network endpoint exposes real borrower/lender relationships and amounts.

Business inspectors can also start a credit review, show separate business/bank tool traces and an approved/declined offer, and settle accepted credit. See [the credit workflow guide](./docs/BUSINESS_BANK_AGENTS.md) and [calculated success/decline examples](./docs/credit_demo.json). Credit workflows do not run automatically for every business on each tick; the existing rule-based simulation continues between explicit agent requests.

Supplier workflows are also ready for integration. Show the two original quotes, requested counteroffer, supplier response, selected full price/down payment/due tick, and separate procurement/contract statuses. See [the supplier guide](./docs/SUPPLIER_PAYMENTS.md) and [the calculated negotiation and payment example](./docs/procurement_demo.json). A contract commits future automatic balance collection; the maximum budget covers its entire invoice, not only the initial payment.

For the demo, create a world with `{"seed":42,"scenario":"credit_crunch"}`, post a 4,000-basis-point shock to `bank_1`, then step 12 days. Follow the runnable requests in [docs/CRISIS.md](./docs/CRISIS.md). The `standard` scenario retains high starting bank capital and can absorb the same shock; scenarios are intentionally different initial conditions.

To compare rescue strategies, create and shock the world, then call `/api/worlds/{id}/forks` **before advancing time** with `{"request_id":"demo-1","bank_id":"bank_1","budget_cents":1000000,"ticks":12}`. Each intervention branch receives the same additional budget. The source stays unchanged. Follow [the complete Fork Reality walkthrough](./docs/FORK_REALITY.md) for sample results and UI integration.

The local browser origins `localhost:3000`, `localhost:5173`, `127.0.0.1:3000`, and `127.0.0.1:5173` are enabled. Configure a comma-separated `ECONOMY_CORS_ORIGINS` environment variable for another frontend origin. Configuration follows [FastAPI’s CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/).

The default database is [data/economy.sqlite3](./data/economy.sqlite3), created on first import/start. Set `ECONOMY_DB_PATH` to override it. The API is a local development service with no authentication; transaction IDs provide retry protection, not authorization.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.export_contract
```

On macOS/Linux, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`. The current suite contains 100 tests. Contract export regenerates the schema and calculated examples in [docs/](./docs/), including [the crisis demo](./docs/crisis_demo.json), [the fork comparison](./docs/fork_demo.json), [the central-bank demo trace](./docs/agent_demo.json), [the credit demo traces](./docs/credit_demo.json), and [the supplier payment demo](./docs/procurement_demo.json).

Tests cover ledger invariants, reproducibility, reserve/deposit conservation, loan creation and repayment, rejected transactions, request validation, persistence, event pagination, CORS, concurrent requests, shock replay, clearing calculations, crisis propagation, defaults, and legacy checkpoints.

Fork tests additionally verify matched trajectories across seeds, source/sibling isolation, public lending/grant accounting, every-cent distribution, report persistence, concurrent retries, and rollback of partially published branch sets.

Agent tests use offline scripted responses and mocked HTTP transport. They verify proposal rejection/recovery, turn limits, frozen snapshots, trace persistence, credential handling, and safe recommendation application. They do not prove live Nemotron availability or sponsor integration eligibility.

Credit tests additionally verify role permissions, borrower acceptance, counteroffers, frozen deposits, post-issuance risk constraints, maturity preservation, concurrent settlement, complete rollback, and automatic settlement recovery.

Supplier tests verify invoice accounting, stock and cost-basis transfers, due payments/defaults, contract branch isolation, negotiation policy, source snapshots, duplicate settlement, and full publication rollback.

Playback tests verify concurrent schedulers, deterministic ticks, pause/manual-step exclusion, restart behavior, speed changes, failed-tick rollback, retry-safe reset, SSE replay and reconnect headers, plus the real API background loop.

The persistence approach stores complete world checkpoints, including history. It favors correctness and easy snapshots for the first milestone. Long runs and high-volume event retrieval will need normalized storage or incremental journal writes; the maximum input population is not a throughput guarantee.
