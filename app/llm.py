from langchain_mistralai import ChatMistralAI

from app.config import MODEL


def get_llm() -> ChatMistralAI:
    return ChatMistralAI(model=MODEL, temperature=0)
