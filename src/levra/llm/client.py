import os

from openai import AsyncOpenAI

PARSER_MODEL = "anthropic/claude-sonnet-4-20250514"
NARRATOR_MODEL = "anthropic/claude-sonnet-4-20250514"


def build_client() -> AsyncOpenAI:
    key = os.environ["OPENROUTER_API_KEY"]
    return AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)