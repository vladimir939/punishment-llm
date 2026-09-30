"""Google provider (official `google-genai` SDK).

Gemini 3.x controls reasoning depth with `thinking_level`. Thought summaries
are requested but not guaranteed; when absent, `reasoning_trace` is empty.
Confirm the parameter surface in the pilot before any bulk run.
"""

from __future__ import annotations

import time

from ..models import Capabilities, ProviderResponse
from .base import MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS_THINKING, Provider, ProviderError


class GoogleProvider(Provider):
    name = "google"
    env_var = "GOOGLE_API_KEY"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            temperature_settable=True,
            thinking_toggleable=True,
            returns_reasoning_trace=True,
            # No first-party batch endpoint is wired up here; falls back to sync.
            supports_batch=False,
        )

    def client(self):
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - env dependent
                raise ProviderError(
                    "the `google-genai` package is not installed "
                    "(pip install google-genai)"
                ) from exc
            self._client = genai.Client(api_key=self.api_key())
        return self._client

    def complete(self, prompt: str, *, thinking: bool) -> ProviderResponse:
        from google.genai import types

        config_kwargs: dict = {
            "max_output_tokens": (
                MAX_OUTPUT_TOKENS_THINKING if thinking else MAX_OUTPUT_TOKENS
            ),
            "thinking_config": types.ThinkingConfig(
                thinking_level="high" if thinking else "low",
                include_thoughts=thinking,
            ),
        }
        if self.model.temperature is not None:
            config_kwargs["temperature"] = self.model.temperature

        started = time.monotonic()
        try:
            response = self.client().models.generate_content(
                model=self.model.snapshot,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:
            raise ProviderError(f"google call failed: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        text_parts, thought_parts = [], []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                chunk = getattr(part, "text", None)
                if not chunk:
                    continue
                if getattr(part, "thought", False):
                    thought_parts.append(chunk)
                else:
                    text_parts.append(chunk)

        usage = getattr(response, "usage_metadata", None)
        return ProviderResponse(
            text="\n".join(text_parts),
            reasoning_trace="\n".join(thought_parts),
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            latency_ms=latency_ms,
            temperature_effective=self.effective_temperature(),
            thinking_effective=thinking,
        )
