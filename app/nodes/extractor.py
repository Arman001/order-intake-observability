from app.state import State

# Phase 2 stub: fixed items, so the wiring and tracing can be proven before
# any extraction prompt exists. Replaced by the real v1 Extractor in phase 3.
STUB_ITEMS = [
    {"sku": "BOLT-M8", "qty": 100},
    {"sku": "BRACKET-L50", "qty": 50},
]


def extractor(state: State) -> dict:
    """Turn the email into order items."""
    if state["version"] == "v2":
        return {
            "items": [{**item, "qty_source": "explicit"} for item in STUB_ITEMS],
            "needs_clarification": False,
            "clarification_reason": None,
        }
    return {"items": [dict(item) for item in STUB_ITEMS]}
