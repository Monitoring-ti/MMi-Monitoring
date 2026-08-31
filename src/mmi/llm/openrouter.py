"""Cliente OpenRouter (API compatible con OpenAI)."""

from __future__ import annotations

import os

from openai import OpenAI

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"


def openrouter_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Define OPENROUTER_API_KEY en .env")
    base_url = os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    return OpenAI(api_key=api_key, base_url=base_url)


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> str:
    model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    client = openrouter_client()
    extra_headers: dict[str, str] = {}
    if referer := os.environ.get("OPENROUTER_HTTP_REFERER"):
        extra_headers["HTTP-Referer"] = referer
    if title := os.environ.get("OPENROUTER_APP_TITLE", "MMI by Monitoring"):
        extra_headers["X-Title"] = title

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_headers=extra_headers or None,
    )
    return (resp.choices[0].message.content or "").strip()
