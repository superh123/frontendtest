# Central Bank Agent Workflow

The central-bank workflow observes one financial snapshot, tests alternatives through Fork Reality, optionally revises the budget/target, and recommends a strategy it actually tested. It saves a public rationale, verified outcome metrics, and an ordered tool trace. It cannot directly modify balances. Applying the recommendation is a separate validated operation.

## Live and demo modes

`mode: "live"` is the default. It requires `NEBIUS_API_KEY` and `NEBIUS_MODEL`. The adapter uses Nebius’s chat-completions API with function tools. Select an exact Nemotron model ID that your account supports; no model name is guessed or silently substituted. Provider/model access has not been verified with live credentials in this workspace.

`mode: "demo"` is explicit, deterministic, and credential-free. Its provider is `deterministic_demo`, its model is `demo-policy-v1`, and its rationale says it is not AI-generated. It calls the same validated tools and simulation engine, testing the full cap and then smaller budgets within the requested experiment count. It is useful for UI integration and workflow testing, not evidence of live Nemotron inference.

The provider configuration follows [Nebius’s official API example](https://dev.nebius.com/cookbook/claude-code-token-factory-relay). Nemotron options can be found through [Nebius’s model catalog](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference). Use your account’s available model ID and regional endpoint where applicable.

## Run the workflow without credentials

Start the backend following [the README](../README.md). In a second PowerShell terminal:

```powershell
$world = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/worlds -ContentType application/json -Body '{"scenario":"credit_crunch","seed":42}'
$base = 'http://127.0.0.1:8000/api/worlds/' + $world.simulation_id
Invoke-RestMethod -Method Post -Uri "$base/shocks" -ContentType application/json -Body '{"transaction_id":"shock","bank_id":"bank_1","loss_bps":4000}'
$run = Invoke-RestMethod -Method Post -Uri "$base/agent-runs" -ContentType application/json -Body '{"request_id":"central-bank-1","mode":"demo","budget_cap_cents":1000000,"ticks":12,"max_experiments":2}'
$run.recommendation
$run.trace | Select-Object sequence, tool, status
Invoke-RestMethod -Uri ('http://127.0.0.1:8000/api/agent-runs/' + $run.run_id)
```

The source is unchanged by analysis. The run publishes three isolated worlds per successful experiment. Its comparison IDs can be opened with `/api/forks/{fork_id}` for complete timelines and audits. [agent_demo.json](./agent_demo.json) contains a calculated demo trace with stable illustrative IDs; it is not a live inference transcript.

## Configure live Nemotron access

Set environment variables in the server’s terminal before starting/restarting Uvicorn. The application reads shell variables; an `.env` file is not automatically loaded.

PowerShell can read the key without recording its value in command history:

```powershell
$agentKey = Read-Host 'Nebius API key' -AsSecureString
$env:NEBIUS_API_KEY = [System.Net.NetworkCredential]::new('', $agentKey).Password
$env:NEBIUS_MODEL = '<exact tool-capable Nemotron model ID from your account>'
$env:NEBIUS_BASE_URL = 'https://api.tokenfactory.nebius.com/v1'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In Bash:

```bash
read -s -p 'Nebius API key: ' NEBIUS_API_KEY
export NEBIUS_API_KEY
export NEBIUS_MODEL='<exact tool-capable Nemotron model ID from your account>'
export NEBIUS_BASE_URL='https://api.tokenfactory.nebius.com/v1'
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

`GET /api/agents/status` shows missing variable names and the configured model, never the key. `live_configured` checks configuration presence, not model availability or account balance. Use a new run request with `mode: "live"` to verify actual provider access. Missing or invalid base configuration returns 503; the service never substitutes demo mode.

The adapter uses HTTPS, does not follow redirects, does not inherit HTTP proxies, uses a 60-second timeout per model request, and returns sanitized provider errors without upstream response bodies. It does not automatically retry external inference calls. Backend requests contain simulated economy observations, not API credentials. Existing HTTPX dependencies are sufficient; no new SDK is required.

## Agent tools and limits

The model has three tools:

1. `inspect_economy({})`: current captured metrics, bank equity/assets/reserves, capital/liquidity ratios, and lending status.
2. `compare_interventions({bank_id, budget_cents})`: calculate all three strategies using the run’s captured snapshot and fixed horizon. The bank must exist, the budget must not exceed the caller’s cap, and the experiment count must remain within its limit.
3. `recommend_intervention({fork_id, strategy, rationale})`: finish using a comparison produced in this run. The backend copies the selected strategy’s actual metrics/deltas into the recommendation; the model does not supply balances or outcome numbers.

The model must inspect before comparing, and compare before recommending. Invalid JSON, unknown tools, wrong argument types, over-budget proposals, excessive experiments, and invented comparison IDs are rejected and returned as feedback so the model can recover. Maximum: 10 model turns, 4 tool calls per turn, and 1–3 successful experiments per run. `max_experiments` defaults to 2. The horizon is 1–100 ticks, default 12. Simulated budget caps are positive integer cents up to 1,000,000,000,000; they do not measure external inference charges.

The live model can choose a strategy different from Fork Reality’s rule-based ranking. Preserve both in the UI. Model rationale is qualitative generated text; canonical metrics and deltas come from the simulation. No hidden model reasoning is saved or exposed. No recommendation is a claim about real-world policy effectiveness.

## Applying the recommendation

If the run is completed and the source world has not changed since its snapshot:

```powershell
$applyUrl = 'http://127.0.0.1:8000/api/agent-runs/' + $run.run_id + '/apply'
Invoke-RestMethod -Method Post -Uri $applyUrl -ContentType application/json -Body '{"transaction_id":"apply-central-bank-1"}'
Invoke-RestMethod -Uri "$base/audit"
```

The backend validates the stored recommendation, rechecks the source hash under a SQLite write lock, and settles through the existing intervention ledger. A no-intervention choice records an audited zero-amount decision and application event. Each run can be applied once. Retry an uncertain application with its original transaction ID to recover the original receipt. A different ID after application, an already-used financial transaction ID, or any source change before application returns 409. Failed/running analyses cannot be applied.

Stepping the source, making payments, applying shocks, or other mutations invalidate an unapplied recommendation. Run a new analysis using a new `request_id`; analysis trials do not invalidate their source because they run in isolated branches. The separate apply endpoint is also the handoff point for future explicitly authorized automatic execution.

## UI, persistence, and failures

Use `POST /api/worlds/{id}/agent-runs` to start synchronous analysis. Default mode is live, so UI demos must explicitly send `mode: "demo"`. Show a loading state and allow enough time for model inference and simulations. `GET /api/worlds/{id}/agent-runs` lists reports, and `GET /api/agent-runs/{run_id}` retrieves progress and results. Traces save after each tool call, so another request can inspect progress. There is no background job queue or cancellation API yet.

Display `status`, provider/model, source tick/hash, each accepted/rejected tool call, links to comparison reports, the final rationale, and canonical outcome metrics. Application emits `agent_recommendation_applied` in the source’s event stream. Analysis traces are separate from financial events.

`request_id` is scoped to the world. Identical retries of completed or failed runs return the stored report without more inference or simulation. Conflicting parameters or a duplicate still-running request return 409. Live model errors, malformed responses, or an exhausted turn limit save a failed report; HTTP 200 means a report was returned, not necessarily that the workflow succeeded. Check `status` and `error`.

If analysis fails after successful trials, those isolated comparisons remain saved and inspectable. A process crash may leave a run marked running; there is no automatic lease recovery. Retrieve its trace, then use a new request ID for a fresh attempt. Public source balances stay unchanged unless application commits successfully.

The local API still has no authentication; the financial validation layer is not an identity system. Business/bank credit roles are available through [the credit workflow](./BUSINESS_BANK_AGENTS.md), and supplier negotiation through [the procurement workflow](./SUPPLIER_PAYMENTS.md). External settlement and automatic central-bank intervention execution remain subsequent work.
