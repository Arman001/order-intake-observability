from langchain_mistralai import ChatMistralAI

from app.config import MODEL


def get_llm() -> ChatMistralAI:
    return ChatMistralAI(model=MODEL, temperature=0)


def structured(llm, schema):
    """The model answers in the given schema.

    JSON-schema mode, not function calling: function calling would show the
    answer as a tool call in the trace, although no tool ran.
    """
    return llm.with_structured_output(schema, method="json_schema")
