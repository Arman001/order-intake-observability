import pytest
from pydantic import ValidationError

from app.schemas import ClassifierOutput, ExtractionV1, ExtractionV2


def test_classifier_output():
    out = ClassifierOutput.model_validate({"is_order": False, "reason": "A question"})
    assert out.is_order is False


def test_v1_accepts_items_with_sku_and_qty():
    out = ExtractionV1.model_validate({"items": [{"sku": "BOLT-M8", "qty": 100}]})
    assert out.items[0].qty == 100


def test_v1_rejects_an_item_with_no_qty():
    with pytest.raises(ValidationError):
        ExtractionV1.model_validate({"items": [{"sku": "BOLT-M8"}]})


def test_v1_rejects_a_null_qty():
    with pytest.raises(ValidationError):
        ExtractionV1.model_validate({"items": [{"sku": "BOLT-M8", "qty": None}]})


def test_v1_sku_is_free_text():
    out = ExtractionV1.model_validate({"items": [{"sku": "PTFE tape", "qty": 25}]})
    assert out.items[0].sku == "PTFE tape"


def test_v2_accepts_a_null_qty_marked_unknown():
    out = ExtractionV2.model_validate(
        {
            "needs_clarification": False,
            "items": [{"sku": "BOLT-M8", "qty": None, "qty_source": "unknown"}],
        }
    )
    assert out.items[0].qty is None
    assert out.clarification_reason is None


def test_v2_accepts_needs_clarification_with_no_items():
    out = ExtractionV2.model_validate(
        {
            "needs_clarification": True,
            "clarification_reason": "No order history for 'the usual'",
            "items": [],
        }
    )
    assert out.needs_clarification is True
    assert out.items == []


def test_v2_rejects_an_unknown_qty_source():
    with pytest.raises(ValidationError):
        ExtractionV2.model_validate(
            {
                "needs_clarification": False,
                "items": [{"sku": "BOLT-M8", "qty": 50, "qty_source": "guessed"}],
            }
        )


def test_v2_requires_qty_source():
    with pytest.raises(ValidationError):
        ExtractionV2.model_validate(
            {"needs_clarification": False, "items": [{"sku": "BOLT-M8", "qty": 50}]}
        )
