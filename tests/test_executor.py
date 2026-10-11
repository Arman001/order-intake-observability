import re
from contextlib import closing

from app.db import connect
from app.nodes.executor import executor

ITEMS = [{"sku": "BOLT-M8", "qty": 100}, {"sku": "BRACKET-L50", "qty": 50}]


def run(db_path, outbox, email, items=ITEMS):
    state = {"email": email, "customer_id": "acme-fab", "version": "v1", "items": items}
    return executor(state, db_path=db_path, outbox_dir=outbox)


def test_writes_one_order_with_the_right_lines(db_path, outbox, email):
    result = run(db_path, outbox, email)

    assert result["status"] == "completed"
    assert re.fullmatch(r"ORD-[0-9A-F]{6}", result["order_id"])
    with closing(connect(db_path)) as conn:
        order = conn.execute(
            "SELECT customer_id, order_date FROM orders WHERE order_id = ?",
            (result["order_id"],),
        ).fetchone()
        lines = conn.execute(
            "SELECT sku, qty FROM order_lines WHERE order_id = ?",
            (result["order_id"],),
        ).fetchall()
    assert tuple(order) == ("acme-fab", "2026-10-05")
    assert {r["sku"]: r["qty"] for r in lines} == {"BOLT-M8": 100, "BRACKET-L50": 50}


def test_writes_the_confirmation_to_the_outbox(db_path, outbox, email):
    order_id = run(db_path, outbox, email)["order_id"]

    files = list(outbox.iterdir())
    assert [f.name for f in files] == [f"{order_id}.txt"]
    text = files[0].read_text()
    assert "To: purchasing@acme-fab.example" in text
    assert order_id in text
    assert re.search(r"100 x BOLT-M8\s+M8 hex bolt", text)
    assert re.search(r"50 x BRACKET-L50\s+50 mm L bracket", text)


def test_two_orders_get_different_ids(db_path, outbox, email):
    first = run(db_path, outbox, email)["order_id"]
    second = run(db_path, outbox, email)["order_id"]

    assert first != second
    assert len(list(outbox.iterdir())) == 2


def test_writes_whatever_it_is_given(db_path, outbox, email):
    # The Executor does not judge: a wrong qty is saved as faithfully as a right one.
    order_id = run(db_path, outbox, email, [{"sku": "BOLT-M8", "qty": 50}])["order_id"]

    assert "50 x BOLT-M8" in (outbox / f"{order_id}.txt").read_text()
