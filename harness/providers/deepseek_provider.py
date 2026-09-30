"""DeepSeek provider (OpenAI-compatible chat completions endpoint).

DeepSeek V4 moved thinking from a separate model name to a request parameter.
There is no batch endpoint, so the runner falls back to --sync automatically.
"""

from __future__ import annotations

import time

from ..models import Capabilities, ProviderResponse
from .base import MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS_THINKING, Provider, ProviderError

BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(Provider):
    name = "deepseek"
    env_var = "DEEPSEEK_API_KEY"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            temperature_settable=True,
            thinking_toggleable=True,
            returns_reasoning_trace=True,
            supports_batch=False,
        )

    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - env dependent
                raise ProviderError(
                    "the `openai` package is not installed (pip install openai); "
                    "DeepSeek uses the OpenAI-compatible client"
                ) from exc
            self._client = OpenAI(api_key=self.api_key(), base_url=BASE_URL)
        return self._client

    def complete(self, prompt: str, *, thinking: bool) -> ProviderResponse:
        kwargs: dict = {
            "model": self.model.snapshot,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": (
                MAX_OUTPUT_TOKENS_THINKING if thinking else MAX_OUTPUT_TOKENS
            ),
            "extra_body": {"thinking": {"type": "enabled" if thinking else "disabled"}},
        }
        if self.model.temperature is not None:
            kwargs["temperature"] = self.model.temperature

        started = time.monotonic()
        try:
            response = self.client().chat.completions.create(**kwargs)
        except Exception as exc:
            raise ProviderError(f"deepseek call failed: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        message = response.choices[0].message
        usage = response.usage
        return ProviderResponse(
            text=message.content or "",
            reasoning_trace=getattr(message, "reasoning_content", "") or "",
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency_ms,
            temperature_effective=self.effective_temperature(),
            thinking_effective=thinking,
        )
