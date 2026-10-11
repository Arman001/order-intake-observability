from contextlib import closing
from pathlib import Path

from langchain_core.messages import HumanMessage, ToolMessage

from app.db import connect
from app.llm import structured
from app.schemas import ExtractionV1, ExtractionV2
from app.state import State
from app.tools import make_get_last_order

PROMPT_V1 = """You extract order lines from customer emails for an industrial \
fasteners supplier.

Customer: {customer_id}

Catalog:
{catalog}

Return every item the customer is ordering, with its catalog SKU and quantity.
If a product is not in the catalog, pass its name through as written.

From: {sender}
Subject: {subject}

{body}"""

PROMPT_V2 = """You extract order lines from customer emails for an industrial \
fasteners supplier.

Customer: {customer_id}

Catalog:
{catalog}

Return every item the customer is ordering, with its catalog SKU and quantity.
If a product is not in the catalog, pass its name through as written, with the
quantity the email gives.

If the email refers to a previous order instead of listing its items (for
example "same as last month" or "the usual"), call get_last_order to look it
up. Do not call it when the email lists its own items and quantities.

For every item, say where the quantity came from:
- explicit: the email states it
- from_history: worked out from the order that get_last_order returned
- unknown: you cannot tell. Leave qty empty. Never guess a quantity.

Set needs_clarification only when you cannot tell which products are being
ordered at all. In that case return no items. A product that is named but is
not in the catalog is not a reason to ask: pass it through as an item.

From: {sender}
Subject: {subject}

{body}"""

FINAL_V2 = "Now return the order."


def catalog_text(db_path: Path) -> str:
    with closing(connect(db_path)) as conn:
        rows = conn.execute("SELECT sku, name FROM catalog ORDER BY rowid").fetchall()
    return "\n".join(f"- {row['sku']}: {row['name']}" for row in rows)


def build_prompt(template: str, state: State, db_path: Path) -> str:
    email = state["email"]
    return template.format(
        customer_id=state["customer_id"],
        catalog=catalog_text(db_path),
        sender=email["from"],
        subject=email["subject"],
        body=email["body"],
    )


def extract_v1(state: State, llm, db_path: Path) -> dict:
    # No tools, and a schema where every item must have a qty.
    prompt = build_prompt(PROMPT_V1, state, db_path)
    out = structured(llm, ExtractionV1).invoke(prompt)
    return {"items": [item.model_dump() for item in out.items]}


def extract_v2(state: State, llm, db_path: Path) -> dict:
    get_last_order = make_get_last_order(db_path)
    with_tool = llm.bind_tools([get_last_order])
    messages = [HumanMessage(build_prompt(PROMPT_V2, state, db_path))]

    # Step 1: the model may ask for the customer's last order.
    reply = with_tool.invoke(messages)
    if reply.invalid_tool_calls and not reply.tool_calls:
        reply = with_tool.invoke(messages)  # retry once on a malformed tool call
        if reply.invalid_tool_calls and not reply.tool_calls:
            raise ValueError("The model sent a malformed get_last_order call twice")
    messages.append(reply)

    if reply.tool_calls:
        # One lookup, always for the customer the email came from: the model
        # does not get to choose whose history it reads.
        call = {**reply.tool_calls[0], "args": {"customer_id": state["customer_id"]}}
        result = get_last_order.invoke(call)
        messages.append(result)
        for extra in reply.tool_calls[1:]:
            messages.append(ToolMessage(result.content, tool_call_id=extra["id"]))

    # Step 2: the final answer, in a schema that allows "unknown".
    messages.append(HumanMessage(FINAL_V2))
    out = structured(llm, ExtractionV2).invoke(messages)
    return {
        "items": [item.model_dump() for item in out.items],
        "needs_clarification": out.needs_clarification,
        "clarification_reason": out.clarification_reason,
    }


def extractor(state: State, *, llm, db_path: Path) -> dict:
    """Turn the email into order items."""
    if state["version"] == "v2":
        return extract_v2(state, llm, db_path)
    return extract_v1(state, llm, db_path)
