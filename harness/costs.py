"""Token and cost estimation for --dry-run.

Prices are USD per million tokens and are a snapshot, not an oracle. Check them
against each provider's current pricing page before quoting a number anywhere
that matters. Unknown models fall back to UNKNOWN_PRICE and are flagged.
"""

from __future__ import annotations

from dataclasses import dataclass

# (input $/1M, output $/1M). Pulled live from the OpenRouter models API on
# 2026-09-02. Refresh with: tools/refresh_prices.py
PRICES: dict[str, tuple[float, float]] = {
    # Direct-provider names (used without --via openrouter).
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4.5": (1.00, 5.00),
    "gpt-5.6-sol": (2.00, 10.00),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-luna": (0.20, 1.20),
    "gemini-3.7-flash": (0.75, 3.75),
    "deepseek-v4-flash": (0.09, 0.17),
    "deepseek-v4-pro": (1.04, 2.08),
    # Active roster (verified working on this account, 2026-09-02).
    "x-ai/grok-4.6": (2.00, 6.00),
    "qwen/qwen3.6-max-preview": (1.03, 6.16),
    "mistralai/mistral-medium-3-5": (1.50, 7.50),  # dropped: see MEASURED_OUTPUT_TOKENS
    "z-ai/glm-5.3": (1.40, 4.40),
    "moonshotai/kimi-k2.6": (0.95, 4.00),
    "minimax/minimax-m3": (0.30, 1.20),
    "nvidia/nemotron-3-ultra-550b-a55b": (0.62, 3.12),
    # OpenRouter ids, including the half-price :batch variants.
    "anthropic/claude-opus-5": (5.00, 25.00),
    "anthropic/claude-opus-5:batch": (2.50, 12.50),
    "anthropic/claude-sonnet-5": (2.00, 10.00),
    "anthropic/claude-sonnet-5:batch": (1.00, 5.00),
    "anthropic/claude-haiku-4.5": (1.00, 5.00),
    "anthropic/claude-haiku-4.5:batch": (0.50, 2.50),
    "openai/gpt-5.6-sol": (2.00, 10.00),
    "openai/gpt-5.6-sol:batch": (1.00, 5.00),
    "openai/gpt-5.6-terra": (2.00, 12.00),
    "openai/gpt-5.6-terra:batch": (1.00, 6.00),
    "openai/gpt-5.6-luna": (0.20, 1.20),
    "openai/gpt-5.6-luna:batch": (0.10, 0.60),
    "google/gemini-3.7-flash": (0.75, 3.75),
    "google/gemini-3.7-flash:batch": (0.19, 0.94),
    "deepseek/deepseek-v4-flash": (0.09, 0.17),
    "deepseek/deepseek-v4-pro": (1.04, 2.08),
}

UNKNOWN_PRICE = (0.0, 0.0)


def price_for(snapshot: str) -> tuple[float, float]:
    """Look up a price, tolerating OpenRouter's namespaced ids.

    "anthropic/claude-opus-5" resolves to the same price as "claude-opus-5".
    OpenRouter bills close to upstream per-token rates, so this is a usable
    estimate — but it is an estimate, and the real figure is on your OpenRouter
    activity page.
    """
    if snapshot in PRICES:
        return PRICES[snapshot]
    if "/" in snapshot:
        return PRICES.get(snapshot.split("/", 1)[1], UNKNOWN_PRICE)
    return UNKNOWN_PRICE

# Batch endpoints are roughly half price where available.
BATCH_DISCOUNT = 0.5

# Rough characters-per-token. Only used for the dry-run estimate; the CSV
# always records the provider's own reported token counts.
CHARS_PER_TOKEN = 3.6

# Assumed completion length. Reasoning models emit far more, most of it
# thinking tokens, which are billed as output.
OUTPUT_TOKENS_NONTHINKING = 60
# Reasoning tokens bill as output and dominate the cost, so the estimate has to
# track the configured effort rather than assume the deepest setting.
OUTPUT_TOKENS_THINKING = {"low": 200, "medium": 400, "high": 900}

# Measured medians, 4 samples per model on real study prompts (2026-09-02).
# These override the generic table above where present, because a model that
# ignores `reasoning_effort` can cost 10x the guess -- Mistral Medium 3.5 was
# dropped from the roster for exactly that reason (median 5227 reasoning
# tokens/call, ~$46 for its slot).
MEASURED_OUTPUT_TOKENS: dict[str, int] = {
    "x-ai/grok-4.6": 426,
    "qwen/qwen3.6-max-preview": 800,
    "nvidia/nemotron-3-ultra-550b-a55b": 246,
    "deepseek/deepseek-v4-pro": 244,
    "deepseek/deepseek-v4-flash": 40,
}


@dataclass
class Estimate:
    calls: int
    input_tokens: int
    output_tokens: int
    usd: float
    priced: bool

    def __add__(self, other: "Estimate") -> "Estimate":
        return Estimate(
            calls=self.calls + other.calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            usd=self.usd + other.usd,
            priced=self.priced and other.priced,
        )


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / CHARS_PER_TOKEN))


def estimate(
    prompts: list[str],
    snapshot: str,
    *,
    thinking: bool,
    batch: bool = False,
    effort: str = "high",
) -> Estimate:
    """Estimate cost for a list of rendered prompts against one model."""
    price_in, price_out = price_for(snapshot)
    priced = price_in > 0 or price_out > 0
    per_call_out = MEASURED_OUTPUT_TOKENS.get(
        snapshot,
        OUTPUT_TOKENS_THINKING.get(effort, 900)
        if thinking
        else OUTPUT_TOKENS_NONTHINKING,
    )
    tokens_in = sum(estimate_tokens(p) for p in prompts)
    tokens_out = per_call_out * len(prompts)
    usd = (tokens_in / 1e6) * price_in + (tokens_out / 1e6) * price_out
    if batch:
        usd *= BATCH_DISCOUNT
    return Estimate(
        calls=len(prompts),
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        usd=usd,
        priced=priced,
    )
