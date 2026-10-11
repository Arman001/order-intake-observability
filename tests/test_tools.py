import json
from contextlib import closing

from app.db import connect
from app.tools import last_order, make_get_last_order


def test_last_order_for_client_co(db_path):
    assert last_order(db_path, "client-co") == {
        "order_id": "ORD-5EED01",
        "order_date": "2026-09-12",
        "items": [
            {"sku": "BOLT-M8", "qty": 200},
            {"sku": "NUT-M8", "qty": 200},
            {"sku": "WASHER-M8", "qty": 400},
        ],
    }


def test_no_order_for_a_customer_without_history(db_path):
    assert last_order(db_path, "northwind-build") is None


def test_no_order_for_an_unknown_customer(db_path):
    assert last_order(db_path, "nobody") is None


def test_returns_the_latest_of_several_orders(db_path):
    with closing(connect(db_path)) as conn:
        conn.execute("INSERT INTO orders VALUES ('ORD-00AAAA', 'client-co', '2026-06-01')")
        conn.execute("INSERT INTO order_lines VALUES ('ORD-00AAAA', 'ANCHOR-M10', 5)")
        conn.execute("INSERT INTO orders VALUES ('ORD-00BBBB', 'client-co', '2026-10-01')")
        conn.execute("INSERT INTO order_lines VALUES ('ORD-00BBBB', 'BRACKET-L50', 7)")
        conn.commit()

    order = last_order(db_path, "client-co")

    assert order["order_id"] == "ORD-00BBBB"
    assert order["items"] == [{"sku": "BRACKET-L50", "qty": 7}]


def test_the_tool_has_one_string_argument(db_path):
    tool = make_get_last_order(db_path)

    assert tool.name == "get_last_order"
    assert list(tool.args) == ["customer_id"]
    assert tool.args["customer_id"]["type"] == "string"


def test_the_tool_returns_the_order_as_json(db_path):
    tool = make_get_last_order(db_path)

    assert json.loads(tool.invoke({"customer_id": "client-co"})) == last_order(
        db_path, "client-co"
    )


def test_the_tool_says_so_when_there_is_no_history(db_path):
    tool = make_get_last_order(db_path)

    assert "no previous orders" in tool.invoke({"customer_id": "northwind-build"})
