import json
import re
from contextlib import closing

import pytest

import run
from app import console
from app.db import UnknownSenderError, connect
from app.schemas import ClassifierOutput, ExtractionV1, ItemV1
from tests.conftest import FakeLLM, order_llm

ANSI = re.compile(r"\033\[[0-9;]*m")
ALL_SKUS = ["BOLT-M8", "NUT-M8", "WASHER-M8", "ANCHOR-M10", "BRACKET-L50"]
LONG_REASON = "The email lists explicit quantities and a PO number. " * 10


def plain_lines(text):
    return ANSI.sub("", text).splitlines()


@pytest.fixture
def paths(tmp_path):
    return {"db_path": tmp_path / "orders.db", "outbox_dir": tmp_path / "outbox"}


def test_run_email_completes_and_prints_one_line_per_node(paths, capsys):
    state = run.run_email("01", "v1", llm=order_llm(), **paths)

    assert state["status"] == "completed"
    assert state["customer_id"] == "acme-fab"
    lines = plain_lines(capsys.readouterr().out)
    assert [line.split()[1] for line in lines[1:]] == [
        "classifier", "extractor", "validator", "executor",
    ]
    assert all(line.startswith("✓") for line in lines[1:])


def test_all_four_node_lines_are_green_on_a_completed_run(paths, capsys):
    run.run_email("01", "v1", llm=order_llm(), **paths)

    node_lines = capsys.readouterr().out.splitlines()[1:]
    assert len(node_lines) == 4
    assert all(line.startswith(console.GREEN) for line in node_lines)


def test_a_rejected_run_shows_a_red_validator_line(paths, capsys):
    llm = order_llm(ItemV1(sku="PTFE tape", qty=25))
    state = run.run_email("04", "v1", llm=llm, **paths)

    assert state["status"] == "rejected"
    last = capsys.readouterr().out.splitlines()[-1]
    assert last.startswith(console.RED)
    assert "unknown SKU: PTFE tape" in last


def test_no_line_is_over_80_characters(paths, capsys):
    llm = FakeLLM(
        ClassifierOutput(is_order=True, reason=LONG_REASON),
        ExtractionV1(items=[ItemV1(sku=sku, qty=100) for sku in ALL_SKUS]),
    )
    state = run.run_email("01", "v1", llm=llm, **paths)
    lines = run.order_lines(state["order_id"], paths["db_path"])
    print("\n".join(console.summary_lines(state, lines, "tr-" + "a" * 32)))

    for line in plain_lines(capsys.readouterr().out):
        assert len(line) < 80, line


def test_the_summary_shows_the_order_as_written_to_the_database(paths, capsys):
    state = run.run_email("01", "v1", llm=order_llm(), **paths)
    capsys.readouterr()
    lines = run.order_lines(state["order_id"], paths["db_path"])
    print("\n".join(console.summary_lines(state, lines, "tr-abc")))

    out = plain_lines(capsys.readouterr().out)
    assert "Status: completed" in out
    assert f"Order:  {state['order_id']}" in out
    assert "    100 x BOLT-M8" in out
    assert "     50 x BRACKET-L50" in out
    assert "Trace:  tr-abc" in out


def test_the_api_key_is_never_printed(paths, capsys, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test_secret_value")
    state = run.run_email("01", "v1", llm=order_llm(), **paths)
    print("\n".join(console.summary_lines(state, [], "tr-abc")))

    captured = capsys.readouterr()
    assert "test_secret_value" not in captured.out + captured.err


def test_every_run_starts_from_a_fresh_seed(paths):
    for _ in range(2):
        run.run_email("01", "v1", llm=order_llm(), **paths)

    with closing(connect(paths["db_path"])) as conn:
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert count == 3  # two seeded orders plus this run's, not the previous run's


def test_unknown_sender_stops_before_the_graph_starts(paths, tmp_path, monkeypatch):
    emails = tmp_path / "emails"
    emails.mkdir()
    (emails / "99.json").write_text(json.dumps({
        "id": "99", "from": "stranger@nowhere.example", "date": "2026-10-09",
        "subject": "Order", "body": "100 bolts please",
    }))

    def fail(*args, **kwargs):
        raise AssertionError("the graph must not be built")

    monkeypatch.setattr(run, "build_graph", fail)
    llm = FakeLLM()

    with pytest.raises(UnknownSenderError, match="stranger@nowhere.example"):
        run.run_email("99", "v1", llm=llm, emails_dir=emails, **paths)
    assert llm.prompts == []


def test_a_wrong_order_still_shows_four_green_lines(paths, capsys):
    # The "logs look fine" shot: 2 bolts instead of 400, and nothing is red.
    llm = order_llm(ItemV1(sku="BOLT-M8", qty=2))
    state = run.run_email("03", "v1", llm=llm, **paths)

    assert state["status"] == "completed"
    node_lines = capsys.readouterr().out.splitlines()[1:]
    assert len(node_lines) == 4
    assert all(line.startswith(console.GREEN) for line in node_lines)


def test_a_long_item_list_is_cut_on_a_whole_item(paths, capsys):
    llm = order_llm(*[ItemV1(sku=sku, qty=100) for sku in ALL_SKUS])
    run.run_email("01", "v1", llm=llm, **paths)

    extractor_line = plain_lines(capsys.readouterr().out)[2]
    assert extractor_line.endswith("more")
    assert "5 items: 100 BOLT-M8" in extractor_line
