"""Measure the real cost per call of candidate models.

    python tools\\measure_cost.py

Token estimates are the least reliable number in any budget: a model that
ignores `reasoning_effort` can cost 20x the guess. This sends ONE real study
prompt to each candidate, reads the reported token counts, and projects the
whole study from the measurement. Costs a few cents.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.config import load_spec  # noqa: E402
from harness.costs import price_for  # noqa: E402
from harness.render import build_cells  # noqa: E402

BASE_URL = "https://openrouter.ai/api/v1"

# Candidates for the one expensive slot, plus the incumbent for comparison.
# (openrouter id, effort, label)
CANDIDATES = [
    ("mistralai/mistral-medium-3-5", "medium", "Mistral (incumbent)"),
    ("mistralai/mistral-medium-3-5", "low", "Mistral at low effort"),
    ("z-ai/glm-5.3", "medium", "Zhipu GLM"),
    ("moonshotai/kimi-k2.6", "medium", "Moonshot Kimi"),
    ("minimax/minimax-m3", "medium", "MiniMax"),
    ("nvidia/nemotron-3-ultra-550b-a55b", "medium", "NVIDIA Nemotron"),
]

# Calls this slot needs across all six arms, at the reasoning rep cap.
SLOT_CALLS = 1011


def main() -> int:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print('\nOPENROUTER_API_KEY is not set. Paste:')
        print('  $env:OPENROUTER_API_KEY = "sk-or-v1-..."')
        return 1
    try:
        from openai import OpenAI
    except ImportError:
        print("\nRun first:  pip install openai")
        return 1

    spec = load_spec(ROOT / "spec.json", ROOT / "templates")
    model = next(iter(spec.models.values()))
    prompt = build_cells(spec, model, spec.arms["A"])[0].prompt

    client = OpenAI(api_key=key, base_url=BASE_URL)

    print()
    print("=" * 78)
    print("Real cost per call, measured on one live study prompt")
    print("=" * 78)
    print(f"{'model':<38} {'effort':<7} {'rsn':>6} {'out':>6} {'study $':>9}")
    print("-" * 78)

    results = []
    for model_id, effort, label in CANDIDATES:
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=16000,
                extra_body={
                    "reasoning": {"effort": effort},
                    "usage": {"include": True},
                },
            )
            if not getattr(response, "choices", None):
                print(f"{model_id:<38} {effort:<7} {'FAILED':>6}")
                continue
            usage = response.usage
            tin = getattr(usage, "prompt_tokens", 0) or 0
            tout = getattr(usage, "completion_tokens", 0) or 0
            details = getattr(usage, "completion_tokens_details", None)
            rsn = 0
            if details is not None:
                rsn = (
                    details.get("reasoning_tokens", 0)
                    if isinstance(details, dict)
                    else getattr(details, "reasoning_tokens", 0)
                ) or 0
            pin, pout = price_for(model_id)
            per_call = tin / 1e6 * pin + tout / 1e6 * pout
            study = per_call * SLOT_CALLS
            text = (response.choices[0].message.content or "").strip()
            ok = "CHOICE:" in text.upper()
            flag = "" if ok else "  <- NO CHOICE LINE"
            print(
                f"{model_id:<38} {effort:<7} {rsn:>6} {tout:>6} {study:>9.2f}{flag}"
            )
            results.append((model_id, effort, label, study, ok))
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            short = "403 blocked" if "403" in msg else msg[:40]
            print(f"{model_id:<38} {effort:<7} {short}")

    print("-" * 78)
    usable = [r for r in results if r[4]]
    if usable:
        usable.sort(key=lambda r: r[3])
        print("\nCheapest usable options for this slot:")
        for model_id, effort, label, study, _ in usable[:4]:
            print(f"  ${study:>7.2f}   {model_id}  (effort={effort})  {label}")
        print("\nSend this table to Claude to pick and wire in a replacement.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
