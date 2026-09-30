"""Compare cost of different study configurations.

    python tools/compare_costs.py

Prints what each option costs and what it costs you scientifically. No API
calls, no key needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.config import load_spec  # noqa: E402
from harness.costs import price_for  # noqa: E402
from harness.render import build_cells  # noqa: E402

IN_PER_CALL = 240          # measured from the rendered prompts
OUT_NOTHINK = 60           # "CHOICE: X" plus one sentence
OUT_THINK_HIGH = 900       # reasoning tokens dominate, and they bill as output
OUT_THINK_MED = 400        # roughly what effort="medium" produces


def calls_for(spec, model_id: str) -> tuple[int, int]:
    """(calls across all six arms, ablation calls)."""
    model = spec.models[model_id]
    total = sum(len(build_cells(spec, model, a)) for a in spec.arms.values())
    abl = (
        len(build_cells(spec, model, spec.arms["A"], thinking_enabled=False))
        if model_id in spec.thinking_ablation.models
        else 0
    )
    return total, abl


def cost(calls: int, or_id: str, thinking: bool, effort_high: bool = True) -> float:
    pin, pout = price_for(or_id)
    out = (OUT_THINK_HIGH if effort_high else OUT_THINK_MED) if thinking else OUT_NOTHINK
    return calls * IN_PER_CALL / 1e6 * pin + calls * out / 1e6 * pout


def main() -> int:
    spec = load_spec(ROOT / "spec.json", ROOT / "templates")
    counts = {mid: calls_for(spec, mid) for mid in spec.models}

    # (label, {model_id: (openrouter_id, thinking)}, effort_high, note)
    configs = [
        (
            "A. Current roster: Grok + Qwen + Nemotron + DeepSeek   <-- ACTIVE",
            {
                "xai_frontier": ("x-ai/grok-4.6", True),
                "qwen_frontier": ("qwen/qwen3.6-max-preview", True),
                "nvidia_frontier": ("nvidia/nemotron-3-ultra-550b-a55b", True),
                "deepseek_frontier": ("deepseek/deepseek-v4-pro", True),
                "nonreasoning_anchor": ("deepseek/deepseek-v4-flash", False),
            },
            False,
            "four labs; reasoning_effort=medium; measured token counts (ACTIVE spec)",
        ),
        (
            "A-high. Same roster at reasoning_effort=high",
            {
                "xai_frontier": ("x-ai/grok-4.6", True),
                "qwen_frontier": ("qwen/qwen3.6-max-preview", True),
                "nvidia_frontier": ("nvidia/nemotron-3-ultra-550b-a55b", True),
                "deepseek_frontier": ("deepseek/deepseek-v4-pro", True),
                "nonreasoning_anchor": ("deepseek/deepseek-v4-flash", False),
            },
            True,
            "deeper deliberation, roughly double the price",
        ),
        (
            "B. Swap Mistral for the cheaper MiniMax",
            {
                "xai_frontier": ("x-ai/grok-4.6", True),
                "qwen_frontier": ("qwen/qwen3.6-max-preview", True),
                "nvidia_frontier": ("minimax/minimax-m3", True),
                "deepseek_frontier": ("deepseek/deepseek-v4-pro", True),
                "nonreasoning_anchor": ("deepseek/deepseek-v4-flash", False),
            },
            False,
            "NVIDIA slot swapped for MiniMax",
        ),
        (
            "C. Three reasoning models only",
            {
                "xai_frontier": ("x-ai/grok-4.6", True),
                "qwen_frontier": ("qwen/qwen3.6-max-preview", True),
                "deepseek_frontier": ("deepseek/deepseek-v4-pro", True),
                "nonreasoning_anchor": ("deepseek/deepseek-v4-flash", False),
            },
            False,
            "matches v1's three-model scope",
        ),
    ]


    print(f"\nCall counts per model (from spec.json):")
    for mid, (total, abl) in counts.items():
        extra = f" + {abl} ablation" if abl else ""
        print(f"  {mid:22s} {total:>5} calls{extra}")

    print("\n" + "=" * 78)
    for label, models, effort_high, note in configs:
        total = 0.0
        rows = []
        for mid, (or_id, thinking) in models.items():
            n, abl = counts[mid]
            c = cost(n, or_id, thinking, effort_high)
            if abl:
                c += cost(abl, or_id, False, effort_high)
            rows.append((mid, or_id, n + abl, c))
            total += c
        print(f"\n{label}")
        print(f"  ({note})")
        for mid, or_id, n, c in rows:
            print(f"    {mid:22s} {or_id:34s} {n:>5} calls  ${c:6.2f}")
        print(f"    {'TOTAL':22s} {'':34s} {sum(r[2] for r in rows):>5} calls  ${total:6.2f}")
        print(f"    {'suggested top-up':22s} {'':34s} {'':>5}         ${total * 1.6:6.2f}")

    print("\n" + "=" * 78)
    print(
        "Top-up = total x 1.6, covering the pilot, retries on invalid responses,\n"
        "and the fact that reasoning-token counts are the least certain number\n"
        "here. Check real spend at https://openrouter.ai/activity as you go."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
