"""One small client for Groq's chat API, shared by every stage that asks the model something.

Groq speaks the OpenAI chat format. Any failure (network, timeout, bad status, odd reply) becomes
LLMError with a fixed, generic message. We never put the response body, the key or the page text
into an error, because errors end up in logs.
"""

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_INPUT_CHARS = 8000  # cap what we send out: cost, and less of the page leaves the machine


class LLMError(Exception):
    """The model could not be used. The message is safe to show: it never holds keys or page text."""


def fence_page(text: str) -> str:
    """The page text as quoted data: cut to a fixed size and unable to close its own fence."""
    page = text[:MAX_INPUT_CHARS].replace("</page>", "")
    return f"<page>\n{page}\n</page>"


class GroqChat:
    def __init__(
        self, api_key: str, model: str, client: httpx.Client | None = None, timeout: float = 30.0
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": 1500,  # reasoning models spend some of this before answering
        }
        try:
            response = self._client.post(
                GROQ_URL, json=payload, headers={"Authorization": f"Bearer {self._api_key}"}
            )
        except httpx.HTTPError as exc:
            raise LLMError("The AI service could not be reached.") from exc
        if response.status_code == 429:
            raise LLMError("The AI service is rate limited. Try again later.")
        if response.status_code != 200:
            raise LLMError(f"The AI service returned status {response.status_code}.")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("The AI service gave an unreadable reply.") from exc
        return content or ""
