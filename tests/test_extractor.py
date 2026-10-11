import pytest

from app.nodes.extractor import extractor
from app.nodes.validator import validator
from app.schemas import ExtractionV1, ItemV1
from tests.conftest import FakeLLM


def state(email, **extra):
    return {"email": email, "customer_id": "acme-fab", "version": "v1", **extra}


def test_v1_puts_the_model_items_in_the_state_unchanged(db_path, email):
    llm = FakeLLM(ExtractionV1(items=[ItemV1(sku="BOLT-M8", qty=2)]))

    result = extractor(state(email), llm=llm, db_path=db_path)

    assert result == {"items": [{"sku": "BOLT-M8", "qty": 2}]}


def test_v1_binds_no_tools_and_uses_the_strict_schema(db_path, email):
    llm = FakeLLM(ExtractionV1(items=[]))

    extractor(state(email), llm=llm, db_path=db_path)

    assert llm.tools == []
    assert llm.schemas == [ExtractionV1]
    assert len(llm.prompts) == 1


def test_v1_prompt_has_the_email_the_customer_and_the_catalog(db_path, email):
    llm = FakeLLM(ExtractionV1(items=[]))

    extractor(state(email), llm=llm, db_path=db_path)

    prompt = llm.prompts[0]
    assert email["body"] in prompt
    assert "Customer: acme-fab" in prompt
    for line in [
        "- BOLT-M8: M8 hex bolt",
        "- NUT-M8: M8 hex nut",
        "- WASHER-M8: M8 flat washer",
        "- ANCHOR-M10: M10 wedge anchor",
        "- BRACKET-L50: 50 mm L bracket",
    ]:
        assert line in prompt


def test_v1_prompt_gives_no_order_history_and_no_maximums(db_path, email):
    # v1 has nothing to look "last month" up in. That is the point.
    llm = FakeLLM(ExtractionV1(items=[]))

    extractor(state(email), llm=llm, db_path=db_path)

    assert "200" not in llm.prompts[0]
    assert "1000" not in llm.prompts[0]


def test_v1_does_not_return_a_customer_id(db_path, email):
    llm = FakeLLM(ExtractionV1(items=[ItemV1(sku="BOLT-M8", qty=2)]))

    result = extractor(state(email), llm=llm, db_path=db_path)

    assert "customer_id" not in result


def test_an_unknown_product_passes_through_and_the_validator_rejects_it(db_path, email):
    llm = FakeLLM(ExtractionV1(items=[ItemV1(sku="PTFE thread seal tape", qty=25)]))

    result = extractor(state(email), llm=llm, db_path=db_path)
    assert result["items"] == [{"sku": "PTFE thread seal tape", "qty": 25}]

    verdict = validator(state(email, **result), db_path=db_path)
    assert verdict["status"] == "rejected"


def test_v2_is_not_built_yet(db_path, email):
    with pytest.raises(NotImplementedError):
        extractor({**state(email), "version": "v2"}, llm=FakeLLM(), db_path=db_path)
