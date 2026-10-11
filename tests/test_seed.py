from contextlib import closing

from app.db import connect
from data.seed import seed

TABLES = ("customers", "catalog", "orders", "order_lines")


def dump(db_path):
    with closing(connect(db_path)) as conn:
        return {
            table: [tuple(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY 1, 2")]
            for table in TABLES
        }


def test_customers(conn):
    rows = conn.execute("SELECT customer_id, email FROM customers").fetchall()
    assert {r["customer_id"]: r["email"] for r in rows} == {
        "client-co": "orders@client-co.example",
        "acme-fab": "purchasing@acme-fab.example",
        "northwind-build": "site@northwind-build.example",
    }


def test_catalog(conn):
    rows = conn.execute("SELECT sku, max_qty FROM catalog").fetchall()
    assert {r["sku"]: r["max_qty"] for r in rows} == {
        "BOLT-M8": 1000,
        "NUT-M8": 1000,
        "WASHER-M8": 2000,
        "ANCHOR-M10": 500,
        "BRACKET-L50": 200,
    }


def test_client_co_last_order(conn):
    orders = conn.execute(
        "SELECT order_id, order_date FROM orders WHERE customer_id = 'client-co'"
    ).fetchall()
    assert len(orders) == 1
    assert orders[0]["order_date"] == "2026-09-12"

    lines = conn.execute(
        "SELECT sku, qty FROM order_lines WHERE order_id = ?", (orders[0]["order_id"],)
    ).fetchall()
    assert {r["sku"]: r["qty"] for r in lines} == {
        "BOLT-M8": 200,
        "NUT-M8": 200,
        "WASHER-M8": 400,
    }


def test_acme_has_one_unrelated_order(conn):
    lines = conn.execute(
        "SELECT sku FROM order_lines JOIN orders USING (order_id) "
        "WHERE customer_id = 'acme-fab'"
    ).fetchall()
    assert lines
    assert not {r["sku"] for r in lines} & {"BOLT-M8", "NUT-M8", "WASHER-M8"}


def test_northwind_has_no_orders(conn):
    count = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE customer_id = 'northwind-build'"
    ).fetchone()[0]
    assert count == 0


def test_order_lines_only_use_catalog_skus(conn):
    unknown = conn.execute(
        "SELECT sku FROM order_lines WHERE sku NOT IN (SELECT sku FROM catalog)"
    ).fetchall()
    assert unknown == []


def test_seeding_twice_gives_the_same_database(db_path):
    first = dump(db_path)
    seed(db_path)
    assert dump(db_path) == first


def test_seeding_removes_orders_created_by_runs(db_path):
    first = dump(db_path)
    with closing(connect(db_path)) as conn:
        conn.execute("INSERT INTO orders VALUES ('ORD-ABC123', 'client-co', '2026-10-08')")
        conn.execute("INSERT INTO order_lines VALUES ('ORD-ABC123', 'BOLT-M8', 50)")
        conn.commit()
    seed(db_path)
    assert dump(db_path) == first
