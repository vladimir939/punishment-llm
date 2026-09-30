"""Find out why an OpenRouter call is failing.

    python tools\\diagnose.py

Makes up to five tiny calls (a few cents total) and prints the FULL error for
each, instead of the one-word `api_error` the CSV records. Each test changes one
thing, so the first one that succeeds tells you exactly what the problem was.
"""

from __future__ import annotations

import os
import sys

BASE_URL = "https://openrouter.ai/api/v1"
PROMPT = "Reply with exactly: CHOICE: X"


def line(char: str = "-") -> None:
    print(char * 70)


def main() -> int:
    key = os.environ.get("OPENROUTER_API_KEY")
    print()
    line("=")
    print("OpenRouter diagnostic")
    line("=")

    if not key:
        print("\nFAIL: OPENROUTER_API_KEY is not set in this window.\n")
        print("Paste this into PowerShell (with your real key), then run me again:")
        print('  $env:OPENROUTER_API_KEY = "sk-or-v1-..."')
        return 1
    print(f"\nKey found: {key[:12]}... ({len(key)} characters)")
    if not key.startswith("sk-or-"):
        print("  WARNING: an OpenRouter key normally starts with 'sk-or-'.")

    try:
        from openai import OpenAI
    except ImportError:
        print("\nFAIL: the `openai` package is not installed.")
        print("  Run: pip install openai")
        return 1

    client = OpenAI(api_key=key, base_url=BASE_URL)

    # Each test changes exactly one thing from the one before it.
    tests = [
        (
            "1. Cheapest model, nothing fancy",
            "deepseek/deepseek-v4-flash",
            {},
            "Is the key valid and does it have credit?",
        ),
        (
            "2. Sonnet 5, plain",
            "anthropic/claude-sonnet-5",
            {},
            "Does the Anthropic model work at all?",
        ),
        (
            "3. Sonnet 5 + reasoning",
            "anthropic/claude-sonnet-5",
            {"reasoning": {"effort": "high"}},
            "Is the reasoning parameter accepted?",
        ),
        (
            "4. Sonnet 5 + reasoning + provider pinning",
            "anthropic/claude-sonnet-5",
            {
                "reasoning": {"effort": "high"},
                "provider": {"order": ["anthropic"], "allow_fallbacks": False},
            },
            "Is the provider pinning the problem?",
        ),
        (
            "5. Sonnet 5 :batch  <-- what the harness currently uses",
            "anthropic/claude-sonnet-5:batch",
            {
                "reasoning": {"effort": "high"},
                "provider": {"order": ["anthropic"], "allow_fallbacks": False},
            },
            "Does the half-price :batch variant work synchronously?",
        ),
    ]

    results: list[tuple[str, bool, str]] = []
    for label, model, extra, question in tests:
        line()
        print(f"{label}")
        print(f"   model: {model}")
        print(f"   asking: {question}")
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": PROMPT}],
                max_tokens=2000 if extra.get("reasoning") else 50,
                extra_body=extra or None,
            )
            if not getattr(response, "choices", None):
                detail = getattr(response, "error", None) or "no choices returned"
                print(f"   RESULT: FAILED -> {detail}")
                results.append((label, False, str(detail)))
                continue
            text = (response.choices[0].message.content or "").strip()
            served = getattr(response, "provider", "?")
            print(f"   RESULT: OK")
            print(f"     replied  : {text[:60]!r}")
            print(f"     served by: {served}")
            results.append((label, True, ""))
        except Exception as exc:  # noqa: BLE001 - we want to see everything
            msg = f"{type(exc).__name__}: {exc}"
            print(f"   RESULT: FAILED")
            print(f"     {msg[:500]}")
            results.append((label, False, msg))

    line("=")
    print("SUMMARY")
    line("=")
    for label, ok, msg in results:
        mark = "OK  " if ok else "FAIL"
        print(f"  [{mark}] {label}")
        if not ok:
            print(f"         {msg[:160]}")

    ok_names = [label for label, ok, _ in results if ok]
    print()
    if not ok_names:
        print("Nothing worked. Most likely the key is wrong or has no credit.")
        print("Check https://openrouter.ai/credits and https://openrouter.ai/activity")
    elif results[-1][1]:
        print("Everything works, including :batch. The earlier failure was")
        print("probably temporary -- just re-run the STEP 10 command.")
    else:
        print("The :batch variant is the thing that fails.")
        print("Fix: run the harness with --fast, which drops ':batch'.")
        print("  python -m harness --sync --via openrouter --fast --arms A \\")
        print("      --models anthropic_frontier --limit 2")
        print()
        print("Cost goes from about $10.79 to about $22.90 for the whole study.")
        print("Send me the summary above and I can pin it down further.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
