"""Tests that call Mistral. Run with: uv run pytest -m live"""

import pytest

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
