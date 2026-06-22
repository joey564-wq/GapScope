"""LLM clients for GapScope — the network boundary, isolated here.

Only the recommendation step talks to an LLM. The client interface is a small
Protocol so the same calling code uses Gemini in production and a local Ollama
model in development, and tests can substitute a fake without any network.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Anything that turns a (system, user) prompt pair into a text response."""

    def complete(self, system: str, user: str) -> str: ...


class GeminiClient:
    """Google Gemini via the google-genai SDK.

    Uses the paid API tier (set GEMINI_API_KEY), which does not train on your
    inputs. Requests JSON directly with response_mime_type for reliable
    structured output.

    Install: pip install google-genai
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key_env: str = "GEMINI_API_KEY",
        temperature: float = 0.2,
    ) -> None:
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - optional dep
            raise ImportError(
                "GeminiClient requires google-genai. Install: pip install google-genai"
            ) from exc
        self._genai = genai
        self._client = genai.Client(api_key=os.environ[api_key_env])
        self._model = model
        self._temperature = temperature

    def complete(self, system: str, user: str) -> str:  # pragma: no cover - network
        resp = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config=self._genai.types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=self._temperature,
            ),
        )
        return resp.text or ""


class OllamaClient:
    """Local model via Ollama, for free offline development.

    No API key, no cost, and data never leaves your machine. Swap to
    GeminiClient for the deployed app.

    Run a model first, e.g.:  ollama run llama3.2
    """

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._host = host

    def complete(self, system: str, user: str) -> str:  # pragma: no cover - network
        import httpx

        resp = httpx.post(
            f"{self._host}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "format": "json",
            },
            timeout=120,
        )
        resp.raise_for_status()
        return str(resp.json()["message"]["content"])
