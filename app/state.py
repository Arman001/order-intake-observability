from typing import TypedDict


class State(TypedDict, total=False):
    # Set by run.py before the graph starts
    email: dict
    customer_id: str
    version: str  # "v1" or "v2"

    # Classifier
    is_order: bool
    classifier_reason: str

    # Extractor
    items: list[dict]
    needs_clarification: bool
    clarification_reason: str | None

    # Validator and Executor
    status: str  # not_an_order, valid, rejected, needs_review, completed
    reason: str
    order_id: str
