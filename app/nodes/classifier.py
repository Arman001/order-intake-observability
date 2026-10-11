from app.schemas import ClassifierOutput
from app.state import State

PROMPT = """You triage the inbox of an industrial fasteners supplier.

Decide whether this email is a purchase order: the sender wants goods supplied
now. Questions, quote requests and anything that is not yet an order are not
orders. An order can refer to earlier orders instead of listing items.

From: {sender}
Subject: {subject}

{body}"""


def classifier(state: State, *, llm) -> dict:
    """Decide whether the email is an order."""
    email = state["email"]
    prompt = PROMPT.format(
        sender=email["from"], subject=email["subject"], body=email["body"]
    )
    out = llm.with_structured_output(ClassifierOutput).invoke(prompt)

    update = {"is_order": out.is_order, "classifier_reason": out.reason}
    if not out.is_order:
        update["status"] = "not_an_order"
    return update
