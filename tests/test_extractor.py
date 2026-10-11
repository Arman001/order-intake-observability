import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.nodes.extractor import PROMPT_V1, extractor
from app.nodes.validator import validator
from app.schemas import ExtractionV1, ExtractionV2, ItemV1, ItemV2
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


# v2: one lookup, then an answer that may say "unknown"


def lookup(customer_id="client-co", call_id="call_1"):
    return AIMessage(
        content="",
        tool_calls=[
            {"name": "get_last_order", "args": {"customer_id": customer_id}, "id": call_id}
        ],
    )


def malformed():
    return AIMessage(
        content="",
        invalid_tool_calls=[
            {"name": "get_last_order", "args": "{customer_id:", "id": "bad", "error": "bad JSON"}
        ],
    )


HISTORY_ANSWER = ExtractionV2(
    needs_clarification=False,
    items=[
        ItemV2(sku="BOLT-M8", qty=400, qty_source="from_history"),
        ItemV2(sku="NUT-M8", qty=200, qty_source="from_history"),
        ItemV2(sku="WASHER-M8", qty=400, qty_source="from_history"),
    ],
)


def v2_state(email, customer_id="client-co"):
    return {"email": email, "customer_id": customer_id, "version": "v2"}


def test_v2_looks_up_the_last_order_once_and_returns_the_final_items(db_path, email):
    llm = FakeLLM(lookup(), HISTORY_ANSWER)

    result = extractor(v2_state(email), llm=llm, db_path=db_path)

    assert [tool.name for tool in llm.tools] == ["get_last_order"]
    assert llm.schemas == [ExtractionV2]
    assert result["needs_clarification"] is False
    assert result["items"] == [
        {"sku": "BOLT-M8", "qty": 400, "qty_source": "from_history"},
        {"sku": "NUT-M8", "qty": 200, "qty_source": "from_history"},
        {"sku": "WASHER-M8", "qty": 400, "qty_source": "from_history"},
    ]


def test_v2_gives_the_model_the_real_order_history(db_path, email):
    llm = FakeLLM(lookup(), HISTORY_ANSWER)

    extractor(v2_state(email), llm=llm, db_path=db_path)

    tool_results = [m for m in llm.prompts[-1] if isinstance(m, ToolMessage)]
    assert len(tool_results) == 1
    assert json.loads(tool_results[0].content)["items"][0] == {"sku": "BOLT-M8", "qty": 200}


def test_v2_looks_up_the_customer_from_the_state_not_from_the_model(db_path, email):
    # The model asks for acme-fab's history; it gets client-co's, the sender's.
    llm = FakeLLM(lookup(customer_id="acme-fab"), HISTORY_ANSWER)

    extractor(v2_state(email, "client-co"), llm=llm, db_path=db_path)

    tool_result = [m for m in llm.prompts[-1] if isinstance(m, ToolMessage)][0]
    assert json.loads(tool_result.content)["order_id"] == "ORD-5EED01"


def test_v2_without_a_tool_call_goes_straight_to_the_answer(db_path, email):
    answer = ExtractionV2(
        needs_clarification=False,
        items=[ItemV2(sku="BOLT-M8", qty=100, qty_source="explicit")],
    )
    llm = FakeLLM(AIMessage(content="The email lists its items."), answer)

    result = extractor(v2_state(email), llm=llm, db_path=db_path)

    assert not any(isinstance(m, ToolMessage) for m in llm.prompts[-1])
    assert result["items"] == [{"sku": "BOLT-M8", "qty": 100, "qty_source": "explicit"}]


def test_v2_passes_unknown_and_clarification_through(db_path, email):
    answer = ExtractionV2(
        needs_clarification=True, clarification_reason="no order history", items=[]
    )
    llm = FakeLLM(lookup(customer_id="northwind-build"), answer)

    result = extractor(v2_state(email, "northwind-build"), llm=llm, db_path=db_path)

    assert result == {
        "items": [],
        "needs_clarification": True,
        "clarification_reason": "no order history",
    }
    assert "no previous orders" in llm.prompts[-1][2].content


def test_v2_retries_once_on_a_malformed_tool_call(db_path, email):
    llm = FakeLLM(malformed(), lookup(), HISTORY_ANSWER)

    result = extractor(v2_state(email), llm=llm, db_path=db_path)

    assert len(result["items"]) == 3
    assert llm.answers == []


def test_v2_fails_clearly_on_a_second_malformed_tool_call(db_path, email):
    llm = FakeLLM(malformed(), malformed())

    with pytest.raises(ValueError, match="malformed"):
        extractor(v2_state(email), llm=llm, db_path=db_path)


def test_v2_answers_a_duplicate_tool_call_without_a_second_lookup(db_path, email):
    twice = lookup()
    twice.tool_calls.append(
        {"name": "get_last_order", "args": {"customer_id": "client-co"}, "id": "call_2"}
    )
    llm = FakeLLM(twice, HISTORY_ANSWER)

    extractor(v2_state(email), llm=llm, db_path=db_path)

    tool_results = [m for m in llm.prompts[-1] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in tool_results] == ["call_1", "call_2"]
    assert tool_results[0].content == tool_results[1].content


def test_v2_prompt_tells_the_model_not_to_guess(db_path, email):
    llm = FakeLLM(lookup(), HISTORY_ANSWER)

    extractor(v2_state(email), llm=llm, db_path=db_path)

    prompt = llm.prompts[0][0].content
    assert "Never guess a quantity" in prompt
    assert "get_last_order" in prompt


def test_v1_is_unchanged_by_v2(db_path, email):
    assert "get_last_order" not in PROMPT_V1
    assert "unknown" not in PROMPT_V1
