"""OpenAI provider (official `openai` SDK, Responses API).

The GPT-5.6 family exposes reasoning depth as a request-level setting rather
than a separate model. Reasoning summaries are requested but not guaranteed;
when none is returned, `reasoning_trace` is empty and that is itself recorded.

The exact parameter surface should be confirmed by the eight-call pilot before
any bulk run.
"""

from __future__ import annotations

import time

from ..models import Capabilities, ProviderResponse
from .base import MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS_THINKING, Provider, ProviderError


class OpenAIProvider(Provider):
    name = "openai"
    env_var = "OPENAI_API_KEY"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            temperature_settable=False,
            thinking_toggleable=True,
            returns_reasoning_trace=True,
            supports_batch=True,
        )

    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - env dependent
                raise ProviderError(
                    "the `openai` package is not installed (pip install openai)"
                ) from exc
            self._client = OpenAI(api_key=self.api_key())
        return self._client

    def _params(self, prompt: str, thinking: bool) -> dict:
        return {
            "model": self.model.snapshot,
            "input": prompt,
            "max_output_tokens": (
                MAX_OUTPUT_TOKENS_THINKING if thinking else MAX_OUTPUT_TOKENS
            ),
            "reasoning": {
                "effort": "high" if thinking else "none",
                "summary": "auto" if thinking else None,
            },
        }

    @staticmethod
    def _split(response) -> tuple[str, str]:
        text = getattr(response, "output_text", "") or ""
        summaries: list[str] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", "") != "reasoning":
                continue
            for part in getattr(item, "summary", []) or []:
                summaries.append(getattr(part, "text", "") or "")
        return text, "\n".join(s for s in summaries if s)

    def complete(self, prompt: str, *, thinking: bool) -> ProviderResponse:
        started = time.monotonic()
        try:
            response = self.client().responses.create(**self._params(prompt, thinking))
        except Exception as exc:
            raise ProviderError(f"openai call failed: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        text, trace = self._split(response)
        usage = getattr(response, "usage", None)
        return ProviderResponse(
            text=text,
            reasoning_trace=trace,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            latency_ms=latency_ms,
            temperature_effective=self.effective_temperature(),
            thinking_effective=thinking,
        )

    # -- batch -------------------------------------------------------------

    def submit_batch(self, items: list[tuple[str, str]], *, thinking: bool) -> str:
        import io
        import json

        lines = [
            json.dumps(
                {
                    "custom_id": cid,
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": self._params(prompt, thinking),
                }
            )
            for cid, prompt in items
        ]
        payload = io.BytesIO("\n".join(lines).encode("utf-8"))
        payload.name = "batch.jsonl"
        uploaded = self.client().files.create(file=payload, purpose="batch")
        batch = self.client().batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/responses",
            completion_window="24h",
        )
        return batch.id

    def poll_batch(self, batch_id: str) -> bool:
        return self.client().batches.retrieve(batch_id).status in {
            "completed",
            "failed",
            "expired",
            "cancelled",
        }

    def fetch_batch(self, batch_id: str) -> dict[str, ProviderResponse]:
        import json

        batch = self.client().batches.retrieve(batch_id)
        out: dict[str, ProviderResponse] = {}
        if not getattr(batch, "output_file_id", None):
            return out
        content = self.client().files.content(batch.output_file_id).text
        for line in content.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            cid = record["custom_id"]
            body = (record.get("response") or {}).get("body")
            if not body:
                out[cid] = ProviderResponse(text="", error="batch_errored")
                continue
            text = "".join(
                part.get("text", "")
                for item in body.get("output", [])
                if item.get("type") == "message"
                for part in item.get("content", [])
                if part.get("type") == "output_text"
            )
            trace = "\n".join(
                part.get("text", "")
                for item in body.get("output", [])
                if item.get("type") == "reasoning"
                for part in item.get("summary", []) or []
            )
            usage = body.get("usage", {})
            out[cid] = ProviderResponse(
                text=text,
                reasoning_trace=trace,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                temperature_effective=self.effective_temperature(),
                thinking_effective=self.model.thinking,
            )
        return out
