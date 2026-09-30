"""Find out which models your OpenRouter account can actually use.

    python tools\\probe_models.py

Anthropic and OpenAI models return HTTP 403 ("violation of provider Terms Of
Service") on this account, so the study roster has to be rebuilt from vendors
that do serve it. This makes one tiny call per candidate (a few cents in total)
and prints a table of what works.

Prints a ready-to-use roster at the end.
"""

from __future__ import annotations

import os
import sys

BASE_URL = "https://openrouter.ai/api/v1"
PROMPT = "Reply with exactly: CHOICE: X"

# One strong reasoning-capable model per vendor, plus the two that are known to
# be blocked, so the output shows the contrast explicitly.
CANDIDATES: list[tuple[str, str, bool]] = [
    # (openrouter id, vendor label, wants reasoning)
    ("anthropic/claude-sonnet-5", "Anthropic (expected: blocked)", True),
    ("openai/gpt-5.6-sol", "OpenAI (expected: blocked)", True),
    ("google/gemini-3.7-flash", "Google", True),
    ("deepseek/deepseek-v4-pro", "DeepSeek (large)", True),
    ("deepseek/deepseek-v4-flash", "DeepSeek (small)", True),
    ("x-ai/grok-4.6", "xAI", True),
    ("qwen/qwen3.6-max-preview", "Alibaba Qwen", True),
    ("z-ai/glm-5.3", "Zhipu GLM", True),
    ("moonshotai/kimi-k2.6", "Moonshot Kimi", True),
    ("mistralai/mistral-medium-3-5", "Mistral", True),
    ("minimax/minimax-m3", "MiniMax", True),
    ("nvidia/nemotron-3-ultra-550b-a55b", "NVIDIA Nemotron", True),
]


def main() -> int:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("\nOPENROUTER_API_KEY is not set in this window.")
        print('Paste:  $env:OPENROUTER_API_KEY = "sk-or-v1-..."')
        return 1
    try:
        from openai import OpenAI
    except ImportError:
        print("\nRun first:  pip install openai")
        return 1

    client = OpenAI(api_key=key, base_url=BASE_URL)

    print()
    print("=" * 72)
    print("Which models will this account serve?")
    print("=" * 72)
    print(f"{'model':<40} {'result':<10} note")
    print("-" * 72)

    working: list[tuple[str, str, bool]] = []
    for model_id, label, wants_reasoning in CANDIDATES:
        extra = {"reasoning": {"effort": "high"}} if wants_reasoning else {}
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": PROMPT}],
                max_tokens=2000,
                extra_body=extra or None,
            )
            if not getattr(response, "choices", None):
                detail = str(getattr(response, "error", "no choices"))[:28]
                print(f"{model_id:<40} {'FAIL':<10} {detail}")
                continue
            msg = response.choices[0].message
            reasoned = bool(getattr(msg, "reasoning", "") or "")
            served = getattr(response, "provider", "?")
            note = f"{label}; reasoning={'yes' if reasoned else 'no'}; via {served}"
            print(f"{model_id:<40} {'OK':<10} {note}")
            working.append((model_id, label, reasoned))
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            text = str(exc)
            if "403" in text or "Terms Of Service" in text:
                short = "403 blocked for this account"
            elif "404" in text:
                short = "404 not available"
            else:
                short = f"{name}: {text[:40]}"
            print(f"{model_id:<40} {'FAIL':<10} {short}")

    print("-" * 72)
    print(f"\n{len(working)} of {len(CANDIDATES)} candidates work.\n")

    if not working:
        print("Nothing worked. Check credit at https://openrouter.ai/activity")
        return 1

    print("Models available to you, with reasoning support:")
    for model_id, label, reasoned in working:
        flag = "reasoning" if reasoned else "no reasoning trace"
        print(f"  {model_id:<40} {label}  [{flag}]")

    print()
    print("Send this whole table to Claude and it will rebuild spec.json around")
    print("the models that actually work, and recompute the cost.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
