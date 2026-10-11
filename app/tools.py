import json
from contextlib import closing
from pathlib import Path

from langchain_core.tools import tool

from app.db import connect


def last_order(db_path: Path, customer_id: str) -> dict | None:
    """The customer's most recent order, or None if they have never ordered."""
    with closing(connect(db_path)) as conn:
        order = conn.execute(
            "SELECT order_id, order_date FROM orders WHERE customer_id = ? "
            "ORDER BY order_date DESC, rowid DESC LIMIT 1",
            (customer_id,),
        ).fetchone()
        if order is None:
            return None
        lines = conn.execute(
            "SELECT sku, qty FROM order_lines WHERE order_id = ? ORDER BY rowid",
            (order["order_id"],),
        ).fetchall()
    return {
        "order_id": order["order_id"],
        "order_date": order["order_date"],
        "items": [{"sku": line["sku"], "qty": line["qty"]} for line in lines],
    }


def make_get_last_order(db_path: Path):
    @tool
    def get_last_order(customer_id: str) -> str:
        """Look up the customer's most recent order: its date, items and quantities."""
        order = last_order(db_path, customer_id)
        return json.dumps(order) if order else "This customer has no previous orders."

    return get_last_order
