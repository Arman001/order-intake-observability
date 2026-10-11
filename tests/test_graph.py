from contextlib import closing

import pytest

import app.graph
from app.db import connect
from app.graph import build_graph
from app.schemas import ClassifierOutput
from tests.conftest import FakeLLM


def order_count(db_path):
    with closing(connect(db_path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]


def run(llm, db_path, outbox, email, version="v1"):
    graph = build_graph(llm, db_path, outbox)
    state = {"email": email, "customer_id": "acme-fab", "version": version}
    visited = []
    for step in graph.stream(state, stream_mode="updates"):
        for name, update in step.items():
            visited.append(name)
            state.update(update)
    return state, visited


@pytest.fixture
def order_llm():
    return FakeLLM(ClassifierOutput(is_order=True, reason="Lists items"))


def test_a_valid_order_runs_all_four_nodes(order_llm, db_path, outbox, email):
    before = order_count(db_path)
    state, visited = run(order_llm, db_path, outbox, email)

    assert visited == ["classifier", "extractor", "validator", "executor"]
    assert state["status"] == "completed"
    assert order_count(db_path) == before + 1
    assert (outbox / f"{state['order_id']}.txt").exists()


def test_not_an_order_stops_after_the_classifier(db_path, outbox, email):
    llm = FakeLLM(ClassifierOutput(is_order=False, reason="A question"))
    before = order_count(db_path)
    state, visited = run(llm, db_path, outbox, email)

    assert visited == ["classifier"]
    assert state["status"] == "not_an_order"
    assert "order_id" not in state
    assert order_count(db_path) == before
    assert not outbox.exists()


@pytest.mark.parametrize(
    "extracted, status",
    [
        ({"items": [{"sku": "PTFE tape", "qty": 25}]}, "rejected"),
        ({"items": []}, "rejected"),
    ],
)
def test_rejected_stops_after_the_validator(
    order_llm, db_path, outbox, email, monkeypatch, extracted, status
):
    monkeypatch.setattr(app.graph, "extractor", lambda state: extracted)
    before = order_count(db_path)
    state, visited = run(order_llm, db_path, outbox, email)

    assert visited == ["classifier", "extractor", "validator"]
    assert state["status"] == status
    assert order_count(db_path) == before
    assert not outbox.exists()


def test_needs_review_stops_after_the_validator(
    order_llm, db_path, outbox, email, monkeypatch
):
    extracted = {
        "items": [],
        "needs_clarification": True,
        "clarification_reason": "no order history",
    }
    monkeypatch.setattr(app.graph, "extractor", lambda state: extracted)
    before = order_count(db_path)
    state, visited = run(order_llm, db_path, outbox, email, version="v2")

    assert visited == ["classifier", "extractor", "validator"]
    assert state["status"] == "needs_review"
    assert order_count(db_path) == before
    assert not outbox.exists()


def test_the_classifier_prompt_contains_the_email(order_llm, db_path, outbox, email):
    run(order_llm, db_path, outbox, email)

    assert email["body"] in order_llm.prompts[0]
    assert email["subject"] in order_llm.prompts[0]


def test_customer_id_comes_from_the_state_not_the_model(
    order_llm, db_path, outbox, email
):
    state, _ = run(order_llm, db_path, outbox, email)

    with closing(connect(db_path)) as conn:
        customer = conn.execute(
            "SELECT customer_id FROM orders WHERE order_id = ?", (state["order_id"],)
        ).fetchone()[0]
    assert customer == "acme-fab"
