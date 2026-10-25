"""Replay committed financial events using standard Server-Sent Events framing."""

import asyncio
import json


def event_batch(store, simulation_id, after, limit=200):
    events = store.get(simulation_id).state["events"]
    return events[after:after + limit]


async def stream_events(request, store, simulation_id, after):
    while not await request.is_disconnected():
        events = await asyncio.to_thread(event_batch, store, simulation_id, after)
        if events:
            for event in events:
                after = event["sequence"]
                yield f"id: {after}\nevent: economy_event\ndata: {json.dumps(event)}\n\n"
        else:
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)
