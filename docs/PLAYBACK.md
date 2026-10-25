# Playback and live events

Milestone 7 connects the top-bar controls and live city activity in [the UI plan](../UI_PLAN.md). All controls apply to one simulation ID. Money remains integer USD cents; one tick represents one simulated day.

## Controls

| Method | Path | Body / result |
| --- | --- | --- |
| GET | `/api/worlds/{id}/playback` | `{simulation_id, status, interval_ms, error}` |
| POST | `/api/worlds/{id}/play` | `{"interval_ms":1000}`; returns playback status. |
| POST | `/api/worlds/{id}/pause` | No body; returns playback status. |
| POST | `/api/worlds/{id}/reset` | `{"request_id":"reset-click-1"}`; returns `{source_simulation_id, simulation_id}`. |
| GET | `/api/worlds/{id}/events/stream?after=0` | Server-Sent Events with replay after the exclusive sequence cursor. |

`interval_ms` is a strict integer from 250 to 10,000, default 1,000. Suggested UI speeds: 0.5x = 2,000; 1x = 1,000; 2x = 500; 4x = 250. Change speed by calling Play with the new interval. Identical repeated Play requests preserve the next scheduled tick. Pause is safe to repeat. Manual `/step` returns 409 while running; pause first.

`GET /api/worlds/{id}` now reports `status: "running"` or `"paused"`. Poll `/playback` for scheduling errors and the current interval. Playback state is separate from the economic snapshot, so toggling Play/Pause does not invalidate agent observations. Advancing a tick does invalidate them. Pause before starting a recommendation or negotiation that you intend to apply to that exact snapshot.

## Reset behavior

Reset atomically pauses the source and creates a **new paused world** using its original seed, population, and scenario. It starts at tick zero with the same opening endowments. Shocks, contracts, interventions, and fork lineage are absent in the new world. Existing source history, branches, agent reports, and receipts remain accessible under their original IDs.

Generate one request ID per Reset click and reuse it when retrying that request. Retrying returns the same target simulation ID, even if the target has since advanced. A different request ID creates another world. After success, close the old event stream, switch the selected world ID, clear the chart and event cursor, and fetch the new state. The response contains IDs rather than an immutable initial-state receipt; GET the returned world for its current state.

## Connect the event feed

Fetch the world first, render it, and use its `latest_event_sequence` as the starting cursor when you only want new activity. Use `after=0` to replay all events. Persisted event sequences are per world and start at one.

```js
const base = 'http://127.0.0.1:8000';
const world = await fetch(`${base}/api/worlds/${id}`).then(r => r.json());
let lastSeen = world.latest_event_sequence;
const stream = new EventSource(
  `${base}/api/worlds/${id}/events/stream?after=${lastSeen}`
);
stream.addEventListener('economy_event', ({ data }) => {
  const event = JSON.parse(data);
  if (event.sequence <= lastSeen) return; // Ignore replayed events.
  lastSeen = event.sequence;
  renderActivity(event); // Your city animation / inspector feed.
});
stream.onerror = () => showConnectionStatus('reconnecting');
stream.onopen = () => showConnectionStatus('connected');
// Close on world switch or component unmount:
// stream.close();
```

Each event uses this framing:

```text
id: 17
event: economy_event
data: {"sequence":17,"simulation_id":"world_...", ...}

```

The payload has the existing [Event schema](./openapi.json): tick, ordering, institution IDs, optional amount, transaction ID, and details. These are committed financial events. Agent tool traces remain available through agent-report polling. Stream messages do not contain complete world snapshots; refresh current world/metrics after activity, batching refreshes as appropriate for the UI.

Browser EventSource automatically reconnects with `Last-Event-ID`; the server gives that header precedence over `after`. A newly constructed connection must explicitly pass its own stored cursor. Delivery supports replay, so consumers should deduplicate by `(simulation_id, sequence)`. Invalid header cursors return 422, unknown worlds 404, and a cursor beyond the latest event 409. On an invalid cursor, close the connection, refresh authoritative state, and reconnect using that world's cursor.

Streams drain stored events in batches of 200, then send a heartbeat comment and wait one second when idle. Heartbeats are not economic events. Streaming works while paused as well. A reconnect can replay financial activity committed while the browser was disconnected.

## Runtime and persistence

Start the backend using [the normal run instructions](../README.md). FastAPI lifespan starts a scheduler; no additional service or environment variables are needed. Playback status, speed, and next due time live in SQLite. Each scheduled tick rechecks its due time under the same write lock as ledger settlement. Concurrent workers cannot execute the same due tick twice. Pause waits behind an in-flight tick, then prevents further automatic ticks after its response.

Running worlds resume when the server restarts. Server downtime does not simulate elapsed days: an overdue world advances once, then schedules the next tick from the current time. Slow simulations similarly run below the requested speed instead of accumulating catch-up work. Each scheduler pass considers up to ten due worlds, ordered by next due time. On shutdown, the scheduler finishes any in-flight pass before stopping.

A failed tick rolls back the entire economic update and pauses that world with a generic `/playback.error`. Server logs retain the diagnostic. Other worlds can continue. Inspect the state/audit before explicitly pressing Play to clear the error and retry.

The service still stores and reloads full histories. Playback and SSE are intended for the local hackathon demo; large populations, long sessions, and many simultaneous subscribers need performance measurement and incremental persistence. External payments and continuous autonomous agent scheduling remain future work.
