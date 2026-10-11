import re

import pytest

from app.config import EMAILS_DIR
from app.db import UnknownSenderError, load_email, new_order_id, resolve_customer

EMAIL_IDS = ["01", "02", "03", "04", "05"]
EMAIL_CUSTOMERS = {
    "01": "acme-fab",
    "02": "acme-fab",
    "03": "client-co",
    "04": "acme-fab",
    "05": "northwind-build",
}


def test_there_are_exactly_five_emails():
    assert sorted(p.stem for p in EMAILS_DIR.glob("*.json")) == EMAIL_IDS


@pytest.mark.parametrize("email_id", EMAIL_IDS)
def test_email_has_the_five_fields(email_id):
    email = load_email(email_id)
    assert set(email) == {"id", "from", "date", "subject", "body"}
    assert email["id"] == email_id
    assert all(isinstance(v, str) and v for v in email.values())


@pytest.mark.parametrize("email_id", EMAIL_IDS)
def test_email_sender_maps_to_the_expected_customer(conn, email_id):
    email = load_email(email_id)
    assert resolve_customer(conn, email["from"]) == EMAIL_CUSTOMERS[email_id]


def test_email_03_is_the_double_the_bolts_email():
    assert "same as last month, but double the bolts" in load_email("03")["body"].lower()


def test_loading_a_missing_email_fails_clearly():
    with pytest.raises(FileNotFoundError, match="99"):
        load_email("99")


@pytest.mark.parametrize(
    "sender, customer_id",
    [
        ("orders@client-co.example", "client-co"),
        ("purchasing@acme-fab.example", "acme-fab"),
        ("site@northwind-build.example", "northwind-build"),
        ("  Orders@Client-Co.example ", "client-co"),
    ],
)
def test_resolve_customer(conn, sender, customer_id):
    assert resolve_customer(conn, sender) == customer_id


def test_unknown_sender_raises_a_clear_error(conn):
    with pytest.raises(UnknownSenderError, match="stranger@nowhere.example"):
        resolve_customer(conn, "stranger@nowhere.example")


def test_order_id_format(conn):
    assert re.fullmatch(r"ORD-[0-9A-F]{6}", new_order_id(conn))


def test_seeded_order_ids_use_the_same_format(conn):
    for row in conn.execute("SELECT order_id FROM orders"):
        assert re.fullmatch(r"ORD-[0-9A-F]{6}", row["order_id"])


def test_order_ids_never_repeat_or_reuse_a_seeded_id(conn):
    seeded = {r["order_id"] for r in conn.execute("SELECT order_id FROM orders")}
    generated = set()
    for _ in range(1000):
        order_id = new_order_id(conn)
        conn.execute(
            "INSERT INTO orders VALUES (?, 'client-co', '2026-10-08')", (order_id,)
        )
        generated.add(order_id)
    assert len(generated) == 1000
    assert not generated & seeded


def test_order_id_skips_one_that_is_taken(conn, monkeypatch):
    tokens = iter(["5eed01", "5eed02", "abc123"])
    monkeypatch.setattr("app.db.secrets.token_hex", lambda n: next(tokens))
    assert new_order_id(conn) == "ORD-ABC123"
