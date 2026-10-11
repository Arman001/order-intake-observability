from contextlib import closing
from pathlib import Path

from app.db import connect, new_order_id
from app.state import State

CONFIRMATION = """To: {to}
Subject: Order confirmation {order_id}

Thank you for your order. We have booked the following:

{lines}

Order reference: {order_id}
"""


def executor(state: State, *, db_path: Path, outbox_dir: Path) -> dict:
    """Write the order to the database and the confirmation to outbox/."""
    email = state["email"]
    items = state["items"]

    with closing(connect(db_path)) as conn:
        order_id = new_order_id(conn)
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?)",
            (order_id, state["customer_id"], email["date"]),
        )
        conn.executemany(
            "INSERT INTO order_lines VALUES (?, ?, ?)",
            [(order_id, item["sku"], item["qty"]) for item in items],
        )
        names = dict(conn.execute("SELECT sku, name FROM catalog").fetchall())
        conn.commit()

    # Written to a file, not sent.
    lines = "\n".join(
        f"  {item['qty']:>5} x {item['sku']}  {names[item['sku']]}" for item in items
    )
    outbox_dir.mkdir(exist_ok=True)
    (outbox_dir / f"{order_id}.txt").write_text(
        CONFIRMATION.format(to=email["from"], order_id=order_id, lines=lines)
    )

    return {"status": "completed", "order_id": order_id}
