import pytest

from app.nodes.validator import validator


def check(db_path, version, items, **extra):
    state = {"version": version, "items": items, **extra}
    return validator(state, db_path=db_path)["status"]


def item(sku="BOLT-M8", qty=100, **extra):
    return {"sku": sku, "qty": qty, **extra}


# v1: rules 2 to 4 only


def test_v1_valid_items_pass(db_path):
    items = [item("BOLT-M8", 100), item("BRACKET-L50", 50)]
    assert check(db_path, "v1", items) == "valid"


def test_v1_empty_list_is_rejected(db_path):
    assert check(db_path, "v1", []) == "rejected"


def test_v1_unknown_sku_is_rejected(db_path):
    result = validator(
        {"version": "v1", "items": [item("PTFE tape", 25)]}, db_path=db_path
    )
    assert result["status"] == "rejected"
    assert "PTFE tape" in result["reason"]


@pytest.mark.parametrize("qty", [0, -5, 1001])
def test_v1_qty_out_of_range_is_rejected(db_path, qty):
    assert check(db_path, "v1", [item("BOLT-M8", qty)]) == "rejected"


@pytest.mark.parametrize("qty", [1, 1000])
def test_v1_qty_at_the_limits_passes(db_path, qty):
    assert check(db_path, "v1", [item("BOLT-M8", qty)]) == "valid"


def test_max_qty_is_per_sku(db_path):
    assert check(db_path, "v1", [item("WASHER-M8", 2000)]) == "valid"
    assert check(db_path, "v1", [item("BRACKET-L50", 201)]) == "rejected"


def test_a_wrong_but_plausible_qty_passes(db_path):
    # The whole problem: a guessed 50 is as valid as the correct 400.
    assert check(db_path, "v1", [item("BOLT-M8", 50)]) == "valid"
    assert check(db_path, "v1", [item("BOLT-M8", 400)]) == "valid"


# v2: rule 1 runs first


def test_v2_needs_clarification_with_no_items_is_needs_review(db_path):
    result = validator(
        {
            "version": "v2",
            "items": [],
            "needs_clarification": True,
            "clarification_reason": "no order history",
        },
        db_path=db_path,
    )
    assert result == {"status": "needs_review", "reason": "no order history"}


def test_v2_null_qty_is_needs_review_not_rejected(db_path):
    items = [item("BOLT-M8", None, qty_source="unknown")]
    assert check(db_path, "v2", items) == "needs_review"


def test_v2_unknown_source_is_needs_review(db_path):
    items = [item("BOLT-M8", 50, qty_source="unknown")]
    assert check(db_path, "v2", items) == "needs_review"


def test_v2_unknown_qty_and_unknown_sku_is_needs_review(db_path):
    items = [item("PTFE tape", None, qty_source="unknown")]
    assert check(db_path, "v2", items) == "needs_review"


def test_v2_one_unknown_among_known_items_is_needs_review(db_path):
    items = [
        item("BOLT-M8", 400, qty_source="from_history"),
        item("NUT-M8", None, qty_source="unknown"),
    ]
    assert check(db_path, "v2", items) == "needs_review"


def test_v2_explicit_items_with_unknown_sku_are_still_rejected(db_path):
    items = [item("PTFE tape", 25, qty_source="explicit")]
    assert check(db_path, "v2", items) == "rejected"


def test_v2_empty_list_without_clarification_is_rejected(db_path):
    assert check(db_path, "v2", [], needs_clarification=False) == "rejected"


def test_v2_known_items_pass(db_path):
    items = [
        item("BOLT-M8", 400, qty_source="from_history"),
        item("NUT-M8", 200, qty_source="from_history"),
    ]
    assert check(db_path, "v2", items, needs_clarification=False) == "valid"


def test_v1_ignores_the_v2_fields(db_path):
    # Rule 1 is off in v1, so the empty list falls through to rule 2.
    assert check(db_path, "v1", [], needs_clarification=True) == "rejected"
