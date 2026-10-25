"""Bounded function-tool conversations with public trace callbacks."""

import json

from pydantic import ValidationError

from backend.ledger import LedgerError
from backend.provider import ProviderError


def tool_session(model, tools, handler, trace_callback, instruction):
    messages = [{"role": "system", "content": instruction +
        " Use only the supplied function tools. Do not invent balances or settlement. "
        "Provide brief public rationales, not hidden reasoning."}]
    for _ in range(6):
        message = model.complete(messages, tools)
        calls = message.get("tool_calls") if isinstance(message, dict) else None
        if not isinstance(calls, list) or not 1 <= len(calls) <= 4:
            raise ProviderError("Supplier workflow returned an invalid tool-call batch")
        for call in calls:
            if (not isinstance(call, dict) or not isinstance(call.get("id"), str) or not call["id"]
                    or not isinstance(call.get("function"), dict)
                    or not isinstance(call["function"].get("name"), str)
                    or not isinstance(call["function"].get("arguments"), str)):
                raise ProviderError("Supplier workflow returned a malformed function call")
        messages.append(message)
        for call in calls:
            args, done = {}, False
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"])
                if not isinstance(args, dict):
                    raise ValueError("Arguments must be an object")
                result, done = handler(name, args)
                status = "accepted"
            except (LedgerError, ValidationError, ValueError, KeyError, TypeError) as error:
                status = "rejected"
                result = {"error": str(error) if isinstance(error, LedgerError) else "Tool arguments do not match the allowed schema"}
                if not isinstance(args, dict):
                    args = {}
            trace_callback(name, args, status, result)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
            if done:
                return
    raise ProviderError("Supplier workflow turn limit reached without a decision")
