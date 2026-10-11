"""Creates the SQLite database from scratch: uv run python -m data.seed"""

from contextlib import closing
from pathlib import Path

from app.config import DB_PATH
from app.db import connect

SCHEMA = """
DROP TABLE IF EXISTS order_lines;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS catalog;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE
);

CREATE TABLE catalog (
    sku     TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    max_qty INTEGER NOT NULL
);

CREATE TABLE orders (
    order_id    TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    order_date  TEXT NOT NULL
);

CREATE TABLE order_lines (
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    sku      TEXT NOT NULL,
    qty      INTEGER NOT NULL,
    PRIMARY KEY (order_id, sku)
);
"""

CUSTOMERS = [
    ("client-co", "Client Co", "orders@client-co.example"),
    ("acme-fab", "Acme Fabrication", "purchasing@acme-fab.example"),
    ("northwind-build", "Northwind Build", "site@northwind-build.example"),
]

CATALOG = [
    ("BOLT-M8", "M8 hex bolt", 1000),
    ("NUT-M8", "M8 hex nut", 1000),
    ("WASHER-M8", "M8 flat washer", 2000),
    ("ANCHOR-M10", "M10 wedge anchor", 500),
    ("BRACKET-L50", "50 mm L bracket", 200),
]

# Fixed IDs, in the same ORD-<6 hex> format the Executor generates.
ORDERS = [
    ("ORD-5EED01", "client-co", "2026-09-12"),
    ("ORD-5EED02", "acme-fab", "2026-08-28"),
]

ORDER_LINES = [
    ("ORD-5EED01", "BOLT-M8", 200),
    ("ORD-5EED01", "NUT-M8", 200),
    ("ORD-5EED01", "WASHER-M8", 400),
    ("ORD-5EED02", "ANCHOR-M10", 150),
    ("ORD-5EED02", "BRACKET-L50", 40),
]


def seed(db_path: Path = DB_PATH) -> None:
    with closing(connect(db_path)) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO customers VALUES (?, ?, ?)", CUSTOMERS)
        conn.executemany("INSERT INTO catalog VALUES (?, ?, ?)", CATALOG)
        conn.executemany("INSERT INTO orders VALUES (?, ?, ?)", ORDERS)
        conn.executemany("INSERT INTO order_lines VALUES (?, ?, ?)", ORDER_LINES)
        conn.commit()


if __name__ == "__main__":
    seed()
    print(f"Seeded {DB_PATH.name}: {len(CUSTOMERS)} customers, "
          f"{len(CATALOG)} SKUs, {len(ORDERS)} past orders")
