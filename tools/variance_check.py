"""Measure cost variance across repeated calls.

    python tools\\variance_check.py

A single measurement of reasoning-token usage is close to worthless: the same
model on the same prompt can vary tenfold. This sends N calls per candidate and
reports min/median/max, so the budget is built on a distribution rather than one
lucky or unlucky draw.

Also checks that every response actually parses, using the study's real parser.
"""

from __future__ import annotations

import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.config import load_spec  # noqa: E402
from harness.costs import price_for  # noqa: E402
from harness.models import OptOrder  # noqa: E402
from harness.parsing import parse_single_choice  # noqa: E402
from harness.render import build_cells  # noqa: E402

BASE_URL = "https://openrouter.ai/api/v1"
SAMPLES = 4
SLOT_CALLS = 1011

CANDIDATES = [
    ("mistralai/mistral-medium-3-5", "Mistral (FR)"),
    ("minimax/minimax-m3", "MiniMax (CN)"),
    ("nvidia/nemotron-3-ultra-550b-a55b", "NVIDIA (US)"),
    ("z-ai/glm-5.3", "Zhipu GLM (CN)"),
]


def main() -> int:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print('\nOPENROUTER_API_KEY is not set.')
        return 1
    from openai import OpenAI

    spec = load_spec(ROOT / "spec.json", ROOT / "templates")
    model = next(iter(spec.models.values()))
    # Four different personas, so we are not measuring one prompt repeatedly.
    cells = build_cells(spec, model, spec.arms["A"])
    prompts = [cells[i * 40].prompt for i in range(SAMPLES)]

    client = OpenAI(api_key=key, base_url=BASE_URL)

    print()
    print("=" * 76)
    print(f"Cost variance over {SAMPLES} calls each")
    print("=" * 76)
    print(f"{'model':<36} {'rsn min/med/max':>20} {'valid':>6} {'study $':>9}")
    print("-" * 76)

    rows = []
    for model_id, label in CANDIDATES:
        rsns, costs, valid = [], [], 0
        for prompt in prompts:
            try:
                r = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=16000,
                    extra_body={
                        "reasoning": {"effort": "medium"},
                        "usage": {"include": True},
                    },
                )
                if not getattr(r, "choices", None):
                    continue
                u = r.usage
                tin = getattr(u, "prompt_tokens", 0) or 0
                tout = getattr(u, "completion_tokens", 0) or 0
                d = getattr(u, "completion_tokens_details", None)
                rsn = 0
                if d is not None:
                    rsn = (
                        d.get("reasoning_tokens", 0)
                        if isinstance(d, dict)
                        else getattr(d, "reasoning_tokens", 0)
                    ) or 0
                pin, pout = price_for(model_id)
                rsns.append(rsn)
                costs.append(tin / 1e6 * pin + tout / 1e6 * pout)
                text = r.choices[0].message.content or ""
                if parse_single_choice(text, OptOrder.NOTHING_X, "c1").valid:
                    valid += 1
            except Exception as exc:  # noqa: BLE001
                print(f"{model_id:<36}  error: {str(exc)[:34]}")
                break
        if not costs:
            continue
        spread = f"{min(rsns)}/{int(statistics.median(rsns))}/{max(rsns)}"
        worst = max(costs) * SLOT_CALLS
        median = statistics.median(costs) * SLOT_CALLS
        print(
            f"{model_id:<36} {spread:>20} {valid}/{len(costs):<4} "
            f"{median:>5.2f} (worst {worst:.2f})"
        )
        rows.append((model_id, label, median, worst, valid, len(costs)))

    print("-" * 76)
    good = [r for r in rows if r[4] == r[5]]
    if good:
        good.sort(key=lambda r: r[3])  # rank by worst case, not median
        print("\nRanked by WORST case (what the budget must survive):")
        for model_id, label, median, worst, v, n in good:
            print(f"  worst ${worst:>7.2f}  median ${median:>6.2f}  {model_id}  {label}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
