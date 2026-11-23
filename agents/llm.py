import os
from functools import lru_cache

from langchain_ollama import ChatOllama

DEFAULT_MODEL = "qwen3:0.6b"

class LLMConfigurationError(Exception):
    pass

def get_llm() -> ChatOllama:
    return ChatOllama(
        model=DEFAULT_MODEL,
        temperature=0
    )


