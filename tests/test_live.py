"""Tests that call Mistral. Run with: uv run pytest -m live"""

import pytest

import run
from app.db import load_email
from app.nodes.classifier import classifier

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def llm():
    from app.llm import get_llm

    return get_llm()


@pytest.mark.parametrize(
    "email_id, is_order",
    [("01", True), ("02", False), ("03", True), ("04", True), ("05", True)],
)
def test_classifier(llm, email_id, is_order):
    result = classifier({"email": load_email(email_id)}, llm=llm)

    assert result["is_order"] is is_order
    assert result.get("status") == (None if is_order else "not_an_order")


@pytest.fixture
def paths(tmp_path):
    return {"db_path": tmp_path / "orders.db", "outbox_dir": tmp_path / "outbox"}


def items(state):
    return {item["sku"]: item["qty"] for item in state["items"]}


def test_v1_email_01_completes_with_the_stated_quantities(llm, paths):
    state = run.run_email("01", "v1", llm=llm, **paths)

    assert state["status"] == "completed"
    assert items(state) == {"BOLT-M8": 100, "BRACKET-L50": 50}


def test_v1_email_02_is_not_an_order(llm, paths):
    state = run.run_email("02", "v1", llm=llm, **paths)

    assert state["status"] == "not_an_order"
    assert "items" not in state


def test_v1_email_04_is_rejected_for_an_unknown_sku(llm, paths):
    state = run.run_email("04", "v1", llm=llm, **paths)

    assert state["status"] == "rejected"
    assert "unknown SKU" in state["reason"]


def test_v1_email_03_completes_with_a_wrong_order(llm, paths):
    # The failure the demo depends on. Correct is 400 bolts, 200 nuts, 400 washers.
    state = run.run_email("03", "v1", llm=llm, **paths)

    assert state["status"] == "completed"
    assert items(state) != {"BOLT-M8": 400, "NUT-M8": 200, "WASHER-M8": 400}
    assert items(state).get("BOLT-M8") != 400


# v2: every email against the expected-outcome table


def test_v2_email_03_uses_history_and_doubles_the_bolts(llm, paths):
    state = run.run_email("03", "v2", llm=llm, **paths)

    assert state["status"] == "completed"
    assert items(state) == {"BOLT-M8": 400, "NUT-M8": 200, "WASHER-M8": 400}
    assert {item["qty_source"] for item in state["items"]} == {"from_history"}


def test_v2_email_05_needs_review_instead_of_guessing(llm, paths):
    state = run.run_email("05", "v2", llm=llm, **paths)

    assert state["status"] == "needs_review"
    assert "order_id" not in state


def test_v2_email_01_completes_with_explicit_quantities(llm, paths):
    state = run.run_email("01", "v2", llm=llm, **paths)

    assert state["status"] == "completed"
    assert items(state) == {"BOLT-M8": 100, "BRACKET-L50": 50}
    assert {item["qty_source"] for item in state["items"]} == {"explicit"}


def test_v2_email_02_is_not_an_order(llm, paths):
    assert run.run_email("02", "v2", llm=llm, **paths)["status"] == "not_an_order"


def test_v2_email_04_is_rejected_for_an_unknown_sku(llm, paths):
    state = run.run_email("04", "v2", llm=llm, **paths)

    assert state["status"] == "rejected"
    assert "unknown SKU" in state["reason"]
