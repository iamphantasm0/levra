from openai import AsyncOpenAI

from levra.config import llm_api_key

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Claude is reached through the OpenRouter gateway using the OpenAI-compatible
# SDK — hence `openai` in the dependency list and no `anthropic` package.
PARSER_MODEL = "anthropic/claude-sonnet-4-20250514"
NARRATOR_MODEL = "anthropic/claude-sonnet-4-20250514"


def build_client() -> AsyncOpenAI:
    """Build the LLM client.

    Raises ConfigError when the gateway key is absent, so a missing key is
    reported as a misconfiguration (503) rather than an opaque KeyError (500)
    part-way through handling a request.
    """
    return AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=llm_api_key())
