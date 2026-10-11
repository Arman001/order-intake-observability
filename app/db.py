import json
import secrets
import sqlite3
from pathlib import Path

from app.config import DB_PATH, EMAILS_DIR


class UnknownSenderError(LookupError):
    pass


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def load_email(email_id: str, emails_dir: Path = EMAILS_DIR) -> dict:
    path = emails_dir / f"{email_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No email with id {email_id!r} in {emails_dir}")
    return json.loads(path.read_text())


def resolve_customer(conn: sqlite3.Connection, sender: str) -> str:
    row = conn.execute(
        "SELECT customer_id FROM customers WHERE email = ?",
        (sender.strip().lower(),),
    ).fetchone()
    if row is None:
        raise UnknownSenderError(f"Unknown sender: {sender!r} is not a customer")
    return row["customer_id"]


def new_order_id(conn: sqlite3.Connection) -> str:
    # Not autoincrement: the database is re-seeded before every run, which
    # would hand the same ID to every run's first order.
    while True:
        order_id = f"ORD-{secrets.token_hex(3).upper()}"
        taken = conn.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        if not taken:
            return order_id
