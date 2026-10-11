from contextlib import closing
from pathlib import Path

from app.db import connect
from app.state import State


def validator(state: State, *, db_path: Path) -> dict:
    """Check the extracted items against the catalog."""
    items = state.get("items", [])

    # 1. v2 only: "I don't know" goes to a person. This runs first, because a
    #    missing qty or an empty list would otherwise be rejected below.
    if state["version"] == "v2":
        if state.get("needs_clarification"):
            reason = state.get("clarification_reason") or "request is unclear"
            return {"status": "needs_review", "reason": reason}
        unknown = [
            item["sku"]
            for item in items
            if item.get("qty") is None or item.get("qty_source") == "unknown"
        ]
        if unknown:
            return {
                "status": "needs_review",
                "reason": f"unknown qty for {', '.join(unknown)}",
            }

    # 2. There is something to order
    if not items:
        return {"status": "rejected", "reason": "no items"}

    with closing(connect(db_path)) as conn:
        max_qty = {
            row["sku"]: row["max_qty"]
            for row in conn.execute("SELECT sku, max_qty FROM catalog")
        }

    # 3. Every SKU exists
    for item in items:
        if item["sku"] not in max_qty:
            return {"status": "rejected", "reason": f"unknown SKU: {item['sku']}"}

    # 4. Every qty is positive and within the SKU's maximum
    for item in items:
        if not 1 <= item["qty"] <= max_qty[item["sku"]]:
            return {
                "status": "rejected",
                "reason": f"qty {item['qty']} for {item['sku']} is outside "
                          f"1 to {max_qty[item['sku']]}",
            }

    return {"status": "valid", "reason": f"{len(items)} items in catalog and in range"}
