from contextlib import closing
from pathlib import Path

from app.db import connect
from app.llm import structured
from app.schemas import ExtractionV1
from app.state import State

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


def catalog_text(db_path: Path) -> str:
    with closing(connect(db_path)) as conn:
        rows = conn.execute("SELECT sku, name FROM catalog ORDER BY rowid").fetchall()
    return "\n".join(f"- {row['sku']}: {row['name']}" for row in rows)


def extractor(state: State, *, llm, db_path: Path) -> dict:
    """Turn the email into order items."""
    if state["version"] != "v1":
        raise NotImplementedError("Extractor v2 is not built yet")

    email = state["email"]
    prompt = PROMPT_V1.format(
        customer_id=state["customer_id"],
        catalog=catalog_text(db_path),
        sender=email["from"],
        subject=email["subject"],
        body=email["body"],
    )

    # v1: no tools, and a schema where every item must have a qty.
    out = structured(llm, ExtractionV1).invoke(prompt)
    return {"items": [item.model_dump() for item in out.items]}
