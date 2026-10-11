from typing import Literal

from pydantic import BaseModel


class ClassifierOutput(BaseModel):
    is_order: bool
    reason: str


class ItemV1(BaseModel):
    sku: str
    qty: int


class ExtractionV1(BaseModel):
    items: list[ItemV1]


class ItemV2(BaseModel):
    sku: str
    qty: int | None
    qty_source: Literal["explicit", "from_history", "unknown"]


class ExtractionV2(BaseModel):
    needs_clarification: bool
    clarification_reason: str | None = None
    items: list[ItemV2]
