# What changed from v1 to v2

Three changes. Everything else in the pipeline is the same.

## 1. The Extractor can look up the last order

`app/tools.py` (new) and `app/nodes/extractor.py`

```diff
+ @tool
+ def get_last_order(customer_id: str) -> str:
+     """Look up the customer's most recent order: its date, items and quantities."""
+     order = last_order(db_path, customer_id)
+     return json.dumps(order) if order else "This customer has no previous orders."
```

```diff
- out = structured(llm, ExtractionV1).invoke(prompt)
+ with_tool = llm.bind_tools([get_last_order])
+ reply = with_tool.invoke(messages)
+ if reply.tool_calls:
+     result = get_last_order.invoke(call)
+     messages.append(result)
+ out = structured(llm, ExtractionV2).invoke(messages)
```

## 2. It can say "unknown"

`app/schemas.py`

```diff
  class Item(BaseModel):
      sku: str
-     qty: int
+     qty: int | None
+     qty_source: Literal["explicit", "from_history", "unknown"]

  class Extraction(BaseModel):
+     needs_clarification: bool
+     clarification_reason: str | None = None
      items: list[Item]
```

In v1 every item must have a number, so a model with nothing to go on has to
invent one. In v2 it can leave the quantity empty, or say it cannot tell what
is being ordered at all.

## 3. "Unknown" goes to a person

`app/nodes/validator.py`

```diff
+ if state["version"] == "v2":
+     if state.get("needs_clarification"):
+         return {"status": "needs_review", "reason": reason}
+     if unknown:
+         return {"status": "needs_review", "reason": f"unknown qty for {...}"}

  if not items:
      return {"status": "rejected", "reason": "no items"}
```

This check runs before the others. Otherwise an empty quantity would fail the
range check and be rejected, instead of being sent for review.

The snippets are shortened for reading. The files hold the full code, and the
class names there are `ItemV1`/`ItemV2` and `ExtractionV1`/`ExtractionV2`,
because both versions stay in the repo.
