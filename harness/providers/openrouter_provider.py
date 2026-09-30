"""OpenRouter provider (OpenAI-compatible endpoint, one key for every model).

Trade-offs versus calling each provider directly, all of which the paper needs
to state:

* **No batch endpoint.** Everything runs `--sync`, so the roughly 50% batch
  discount is unavailable.
* **Routing varies.** OpenRouter picks an upstream provider per call and may
  pick a different one next time. The response reports which one actually
  served the request; that goes into the `served_by` CSV column. Pin the
  upstream with `openrouter_only` in spec.json once the pilot shows what you
  are getting.
* **Reasoning toggles are best-effort.** Some models silently ignore a request
  to disable reasoning. The ablation depends on it genuinely being off, so the
  pilot must confirm `reasoning_tokens` drops to zero — see `verify_ablation`.
"""

from __future__ import annotations

import time

from ..models import Capabilities, ProviderResponse
from .base import MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS_THINKING, Provider, ProviderError

BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(Provider):
    name = "openrouter"
    env_var = "OPENROUTER_API_KEY"

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
                    "OpenRouter uses the OpenAI-compatible client"
                ) from exc
            self._client = OpenAI(api_key=self.api_key(), base_url=BASE_URL)
        return self._client

    def _params(self, prompt: str, thinking: bool) -> dict:
        kwargs: dict = {
            "model": self.model.snapshot,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": (
                MAX_OUTPUT_TOKENS_THINKING if thinking else MAX_OUTPUT_TOKENS
            ),
        }
        if self.model.temperature is not None:
            kwargs["temperature"] = self.model.temperature

        extra: dict = {
            # effort=high when reasoning is wanted; enabled=false to turn it off
            # for the ablation. `exclude` is deliberately not used — it only
            # hides the trace, it does not stop the model reasoning.
            "reasoning": (
                {"effort": self.model.reasoning_effort}
                if thinking
                else {"enabled": False}
            ),
            # Report usage accounting so reasoning_tokens is populated.
            "usage": {"include": True},
        }
        if self.model.openrouter_only:
            extra["provider"] = {
                "order": list(self.model.openrouter_only),
                "allow_fallbacks": False,
            }
        kwargs["extra_body"] = extra
        return kwargs

    @staticmethod
    def _reasoning_tokens(usage) -> int:
        details = getattr(usage, "completion_tokens_details", None)
        if details is None:
            return 0
        if isinstance(details, dict):
            return int(details.get("reasoning_tokens", 0) or 0)
        return int(getattr(details, "reasoning_tokens", 0) or 0)

    def complete(self, prompt: str, *, thinking: bool) -> ProviderResponse:
        started = time.monotonic()
        try:
            response = self.client().chat.completions.create(
                **self._params(prompt, thinking)
            )
        except Exception as exc:
            raise ProviderError(f"openrouter call failed: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        if not getattr(response, "choices", None):
            # OpenRouter surfaces upstream failures as an error body rather than
            # an exception. Recorded as data, not swallowed.
            detail = getattr(response, "error", None) or "no choices returned"
            return ProviderResponse(
                text="", error=f"openrouter: {detail}", latency_ms=latency_ms
            )

        message = response.choices[0].message
        usage = getattr(response, "usage", None)
        return ProviderResponse(
            text=message.content or "",
            reasoning_trace=getattr(message, "reasoning", "") or "",
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            reasoning_tokens=self._reasoning_tokens(usage),
            latency_ms=latency_ms,
            temperature_effective=self.effective_temperature(),
            thinking_effective=thinking,
            # `provider` is the upstream that served it; `model` is what it
            # resolved to. Both matter for reproducibility.
            served_by=(
                f"{getattr(response, 'provider', '') or '?'}"
                f"/{getattr(response, 'model', '') or '?'}"
            ),
        )


def verify_ablation(model_id: str, csv_path: str) -> str:
    """Check that thinking actually turned off for the ablation.

    Some models silently ignore `reasoning: {enabled: false}`. The ablation is
    the discriminating test between mode collapse and shallow inference, so if
    reasoning did not really stop, the comparison is meaningless. Run this after
    the pilot.
    """
    import csv as _csv
    from collections import defaultdict

    totals: dict[bool, list[int]] = defaultdict(list)
    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        for row in _csv.DictReader(fh):
            if row.get("model_id") != model_id:
                continue
            on = row.get("thinking_enabled", "").lower() == "true"
            try:
                totals[on].append(int(row.get("reasoning_tokens") or 0))
            except ValueError:
                continue

    def mean(values: list[int]) -> float:
        return sum(values) / len(values) if values else 0.0

    on_mean, off_mean = mean(totals[True]), mean(totals[False])
    lines = [
        f"model {model_id}",
        f"  thinking on : {len(totals[True]):>4} rows, mean reasoning tokens {on_mean:.0f}",
        f"  thinking off: {len(totals[False]):>4} rows, mean reasoning tokens {off_mean:.0f}",
    ]
    if not totals[False]:
        lines.append("  -> no thinking-off rows yet; run the ablation first")
    elif off_mean > 0.1 * max(on_mean, 1.0):
        lines.append(
            "  -> WARNING: reasoning did not stop. The ablation is not valid "
            "for this model on OpenRouter; pin a provider or call it directly."
        )
    else:
        lines.append("  -> reasoning genuinely off. Ablation is valid.")
    return "\n".join(lines)
