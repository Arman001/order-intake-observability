from contextlib import closing

import pytest

from app.db import connect
from app.schemas import ClassifierOutput, ExtractionV1, ItemV1
from data.seed import seed


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "orders.db"
    seed(path)
    return path


@pytest.fixture
def conn(db_path):
    with closing(connect(db_path)) as conn:
        yield conn


class FakeLLM:
    """Stands in for the chat model: returns a fixed structured answer."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []
        self.schemas = []
        self.tools = []

    def with_structured_output(self, schema, **kwargs):
        self.schemas.append(schema)
        return self

    def bind_tools(self, tools, **kwargs):
        self.tools.extend(tools)
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0)


def order_llm(*items):
    """A model that says "this is an order" and then extracts the given items."""
    items = items or (ItemV1(sku="BOLT-M8", qty=100), ItemV1(sku="BRACKET-L50", qty=50))
    return FakeLLM(
        ClassifierOutput(is_order=True, reason="Lists items"),
        ExtractionV1(items=list(items)),
    )


@pytest.fixture
def outbox(tmp_path):
    return tmp_path / "outbox"


@pytest.fixture
def email():
    return {
        "id": "01",
        "from": "purchasing@acme-fab.example",
        "date": "2026-10-05",
        "subject": "PO 4471",
        "body": "100 M8 hex bolts and 50 L brackets please.",
    }
