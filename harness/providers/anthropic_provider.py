"""Anthropic provider (official `anthropic` SDK)."""

from __future__ import annotations

import time

from ..models import Capabilities, ProviderResponse
from .base import MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS_THINKING, Provider, ProviderError


class AnthropicProvider(Provider):
    name = "anthropic"
    env_var = "ANTHROPIC_API_KEY"

    def capabilities(self) -> Capabilities:
        # Sampling parameters are rejected on the current Opus/Sonnet 5 line;
        # thinking is toggled with the `thinking` parameter, and summarised
        # reasoning is returned when display="summarized" is requested.
        return Capabilities(
            temperature_settable=False,
            thinking_toggleable=True,
            returns_reasoning_trace=True,
            supports_batch=True,
        )

    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - env dependent
                raise ProviderError(
                    "the `anthropic` package is not installed (pip install anthropic)"
                ) from exc
            self._client = anthropic.Anthropic(api_key=self.api_key())
        return self._client

    def _params(self, prompt: str, thinking: bool) -> dict:
        params: dict = {
            "model": self.model.snapshot,
            "max_tokens": (
                MAX_OUTPUT_TOKENS_THINKING if thinking else MAX_OUTPUT_TOKENS
            ),
            "messages": [{"role": "user", "content": prompt}],
        }
        if thinking:
            params["thinking"] = {"type": "adaptive", "display": "summarized"}
            params["output_config"] = {"effort": "high"}
        else:
            # Disabling thinking is only accepted at effort `high` or below.
            params["thinking"] = {"type": "disabled"}
            params["output_config"] = {"effort": "high"}
        return params

    @staticmethod
    def _split(message) -> tuple[str, str]:
        text_parts, thinking_parts = [], []
        for block in message.content:
            kind = getattr(block, "type", "")
            if kind == "text":
                text_parts.append(block.text)
            elif kind == "thinking":
                thinking_parts.append(getattr(block, "thinking", "") or "")
            elif kind == "redacted_thinking":
                thinking_parts.append("[redacted]")
        return "\n".join(text_parts), "\n".join(p for p in thinking_parts if p)

    def complete(self, prompt: str, *, thinking: bool) -> ProviderResponse:
        started = time.monotonic()
        try:
            message = self.client().messages.create(**self._params(prompt, thinking))
        except Exception as exc:
            raise ProviderError(f"anthropic call failed: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        if getattr(message, "stop_reason", None) == "refusal":
            # A classifier declined. Recorded as data, not swallowed.
            return ProviderResponse(
                text="",
                reasoning_trace="",
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
                latency_ms=latency_ms,
                temperature_effective=None,
                thinking_effective=thinking,
                error="refusal",
            )

        text, trace = self._split(message)
        return ProviderResponse(
            text=text,
            reasoning_trace=trace,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            latency_ms=latency_ms,
            temperature_effective=self.effective_temperature(),
            thinking_effective=thinking,
        )

    # -- batch -------------------------------------------------------------

    def submit_batch(self, items: list[tuple[str, str]], *, thinking: bool) -> str:
        requests = [
            {"custom_id": cid, "params": self._params(prompt, thinking)}
            for cid, prompt in items
        ]
        batch = self.client().messages.batches.create(requests=requests)
        return batch.id

    def poll_batch(self, batch_id: str) -> bool:
        batch = self.client().messages.batches.retrieve(batch_id)
        return batch.processing_status == "ended"

    def fetch_batch(self, batch_id: str) -> dict[str, ProviderResponse]:
        out: dict[str, ProviderResponse] = {}
        for result in self.client().messages.batches.results(batch_id):
            kind = result.result.type
            if kind != "succeeded":
                out[result.custom_id] = ProviderResponse(
                    text="", error=f"batch_{kind}", thinking_effective=False
                )
                continue
            message = result.result.message
            text, trace = self._split(message)
            out[result.custom_id] = ProviderResponse(
                text=text,
                reasoning_trace=trace,
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
                temperature_effective=self.effective_temperature(),
                thinking_effective=self.model.thinking,
            )
        return out
