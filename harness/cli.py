"""Command-line entry point.

    python -m harness --dry-run
    python -m harness --sync --arms A --models anthropic_frontier --limit 8
    python -m harness --batch --arms A,B,C
    python -m harness --ablation --sync
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_spec, via_openrouter
from .costs import price_for
from .runner import Runner, build_plan, estimate_plan
from .storage import ResultStore


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness",
        description="Costly-punishment data collection harness",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="render and print every prompt, with a count and a cost estimate; "
        "makes zero API calls",
    )
    mode.add_argument(
        "--sync", action="store_true", help="sequential calls with bounded concurrency"
    )
    mode.add_argument(
        "--batch",
        action="store_true",
        help="submit via each provider's batch endpoint where available",
    )

    parser.add_argument("--spec", default="spec.json", help="path to spec.json")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="with --via openrouter: drop the ':batch' suffix, so calls return "
        "immediately instead of queueing. Roughly doubles the cost.",
    )
    parser.add_argument(
        "--via",
        choices=["direct", "openrouter"],
        default="direct",
        help="route every model through one provider. 'openrouter' needs only "
        "OPENROUTER_API_KEY and uses the half-price ':batch' model ids from "
        "spec.json (add --fast for immediate, full-price calls). Records the "
        "upstream that served each call in served_by.",
    )
    parser.add_argument(
        "--templates", default=None, help="templates directory (default: ./templates)"
    )
    parser.add_argument("--out", default="data/raw.csv", help="output CSV path")
    parser.add_argument("--arms", type=_csv_list, default=None, help="e.g. --arms A,C")
    parser.add_argument(
        "--models", type=_csv_list, default=None, help="e.g. --models anthropic_frontier"
    )
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="run the thinking_ablation block from spec.json instead of the arms",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="cap the number of calls (pilot runs)"
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--show", type=int, default=6, help="prompts to print in full during --dry-run"
    )
    parser.add_argument("--poll-seconds", type=int, default=60)
    return parser


def do_dry_run(args, spec) -> int:
    plan = build_plan(
        spec, arms=args.arms, models=args.models, ablation=args.ablation
    )
    cells = plan.cells
    if args.limit:
        cells = cells[: args.limit]

    print(f"\n=== Dry run: {len(cells)} call(s), 0 API requests ===\n")

    shown = min(args.show, len(cells))
    for cell in cells[:shown]:
        header = (
            f"model={cell.model.id} arm={cell.arm.id} persona={cell.persona.id} "
            f"rep={cell.rep} opt_order={cell.opt_order.value} "
            f"conditions={','.join(c.id for c in cell.conditions)}"
        )
        print("-" * 78)
        print(header)
        print("-" * 78)
        print(cell.prompt)
        print(f"[sha256 {cell.prompt_sha256[:16]}…]\n")

    print("=" * 78)
    print("Calls per model x arm:")
    counts: dict[tuple[str, str], int] = {}
    for cell in plan.cells:
        key = (cell.model.id, cell.arm.id)
        counts[key] = counts.get(key, 0) + 1
    for (model_id, arm_id), count in sorted(counts.items()):
        print(f"  {model_id:<22} arm {arm_id}  {count:>5} calls")
    print(f"  {'TOTAL':<22}        {len(plan):>5} calls")

    rows = sum(len(c.conditions) for c in plan.cells)
    print(f"\nCSV rows this would produce: {rows}")

    est_sync = estimate_plan(plan, spec, batch=False)
    est_batch = estimate_plan(plan, spec, batch=True)
    print(
        f"\nEstimated tokens: {est_sync.input_tokens:,} in / "
        f"{est_sync.output_tokens:,} out"
    )
    print(f"Estimated cost (sync):  ${est_sync.usd:,.2f}")
    print(f"Estimated cost (batch): ${est_batch.usd:,.2f}")
    unpriced = sorted(
        {
            spec.models[m].snapshot
            for m in plan.by_model
            if price_for(spec.models[m].snapshot) == (0.0, 0.0)
        }
    )
    if unpriced:
        print(
            "\n  [warn] no price on file for: "
            + ", ".join(unpriced)
            + "\n         The figures above exclude them. Fill in harness/costs.py"
            "\n         from each provider's pricing page before quoting a total."
        )
    return 0


def do_live(args, spec) -> int:
    plan = build_plan(
        spec, arms=args.arms, models=args.models, ablation=args.ablation
    )
    if args.limit:
        remaining = args.limit
        for model_id in list(plan.by_model):
            cells = plan.by_model[model_id][:remaining]
            plan.by_model[model_id] = cells
            remaining -= len(cells)
            if remaining <= 0:
                break
        plan.by_model = {k: v for k, v in plan.by_model.items() if v}

    mode = "batch" if args.batch else "sync"
    print(f"\n=== Running {len(plan)} call(s) in {mode} mode ===")
    print(f"    output: {args.out}\n")

    with ResultStore(args.out) as store:
        runner = Runner(spec, store, concurrency=args.concurrency)
        progress = (
            runner.run_batch(plan, poll_seconds=args.poll_seconds)
            if args.batch
            else runner.run_sync(plan)
        )

    print("\n=== Finished ===")
    print(progress.line())
    print(
        f"    tokens: {progress.input_tokens:,} in / {progress.output_tokens:,} out"
    )
    if progress.invalid:
        print(
            f"    {progress.invalid} invalid row(s) written with valid=false — "
            f"this is data, not an error"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        spec = load_spec(args.spec, args.templates)
        if args.via == "openrouter":
            spec = via_openrouter(spec, fast=args.fast)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    print(f"Loaded spec v{spec.version} from {Path(args.spec).resolve()}")
    print(
        f"  {len(spec.models)} model(s), {len(spec.personas)} persona(s), "
        f"{len(spec.arms)} arm(s)"
    )
    if args.via == "openrouter":
        mode = "standard pricing, immediate" if args.fast else "batch pricing (~half), queued"
        print(f"  routing via OpenRouter -- {mode}")
        if args.batch:
            print("  [warn] use --sync via OpenRouter; batch is chosen by model id")

    if args.dry_run:
        return do_dry_run(args, spec)
    return do_live(args, spec)


if __name__ == "__main__":
    raise SystemExit(main())
