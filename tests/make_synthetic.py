"""Generate synthetic raw.csv + humans.csv to smoke-test analysis/analyze.py.

Not part of the study. Its only job is to prove the analysis runs end to end
and recovers a slope it was given, before any real money is spent.

    python tests/make_synthetic.py --out /tmp/synth
    python analysis/analyze.py     # after pointing it at the synthetic dir
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.config import load_spec  # noqa: E402
from harness.models import CSV_COLUMNS, Observation, OptOrder  # noqa: E402
from harness.render import build_cells  # noqa: E402
from harness.storage import ResultStore  # noqa: E402

# True generating parameters. The analysis should recover these signs.
TRUE_SLOPES = {
    "xai_frontier": 0.0,  # insensitive, as hypothesised
    "qwen_frontier": 0.0,
    "nvidia_frontier": -0.01,
    "deepseek_frontier": 0.0,
    "nonreasoning_anchor": 0.0,
}
TRUE_HUMAN_SLOPE = -0.18
INVALID_RATE = 0.03


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "data"))
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--n-humans", type=int, default=84)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw_path = out / "raw.csv"
    if raw_path.exists():
        raw_path.unlink()

    spec = load_spec(ROOT / "spec.json", ROOT / "templates")

    with ResultStore(raw_path) as store:
        for model in spec.models.values():
            slope = TRUE_SLOPES[model.id]
            for arm_id, arm in spec.arms.items():
                for cell in build_cells(spec, model, arm):
                    # Persona shifts the level; cost shifts the slope.
                    level = rng.normal(0.0, 0.9)
                    persona_offset = (
                        hash(cell.persona.id) % 7 - 3
                    ) * 0.35
                    for condition in cell.conditions:
                        p = sigmoid(level + persona_offset + slope * condition.cost)
                        invalid = rng.random() < INVALID_RATE
                        punish = rng.random() < p
                        store.write(
                            Observation(
                                run_id=hashlib.md5(
                                    f"{cell.prompt_sha256}{condition.id}".encode()
                                ).hexdigest(),
                                timestamp_utc="2026-09-01T12:00:00+00:00",
                                model_id=model.id,
                                provider=model.provider,
                                model_snapshot=model.snapshot,
                                temperature_requested=model.temperature,
                                temperature_effective=model.temperature,
                                thinking_enabled=cell.thinking_enabled,
                                arm=arm_id,
                                template=arm.template,
                                language=arm.language,
                                role=arm.role,
                                allocation=arm.allocation,
                                persona_id=cell.persona.id,
                                persona_budget=cell.persona.budget,
                                persona_norms=cell.persona.norms,
                                condition_id=condition.id,
                                cost=condition.cost,
                                damage=condition.damage,
                                opt_order=cell.opt_order.value,
                                situation_order=cell.situation_order,
                                rep=cell.rep,
                                prompt_sha256=cell.prompt_sha256,
                                raw_response="CHOICE: X\nREASON: synthetic.",
                                reasoning_trace="",
                                parsed_choice=(
                                    None
                                    if invalid
                                    else ("punish" if punish else "nothing")
                                ),
                                valid=not invalid,
                                refusal_reason="off_format" if invalid else None,
                                input_tokens=180,
                                output_tokens=40,
                                latency_ms=900,
                                attempt=1,
                            )
                        )

            # The ablation: same model, thinking off, a slope that appears.
            if model.id in spec.thinking_ablation.models:
                for cell in build_cells(
                    spec, model, spec.arms["A"], thinking_enabled=False
                ):
                    level = rng.normal(0.0, 0.9)
                    for condition in cell.conditions:
                        p = sigmoid(level + 0.04 * condition.cost)
                        store.write(
                            Observation(
                                run_id=hashlib.md5(
                                    f"abl{cell.prompt_sha256}{condition.id}".encode()
                                ).hexdigest(),
                                timestamp_utc="2026-09-01T12:00:00+00:00",
                                model_id=model.id,
                                provider=model.provider,
                                model_snapshot=model.snapshot,
                                temperature_requested=model.temperature,
                                temperature_effective=model.temperature,
                                thinking_enabled=False,
                                arm="A",
                                template=spec.arms["A"].template,
                                language="en",
                                role="victim",
                                allocation="unfair",
                                persona_id=cell.persona.id,
                                persona_budget=cell.persona.budget,
                                persona_norms=cell.persona.norms,
                                condition_id=condition.id,
                                cost=condition.cost,
                                damage=condition.damage,
                                opt_order=cell.opt_order.value,
                                situation_order="",
                                rep=cell.rep,
                                prompt_sha256=cell.prompt_sha256,
                                raw_response="CHOICE: X\nREASON: synthetic.",
                                reasoning_trace="",
                                parsed_choice="punish"
                                if rng.random() < p
                                else "nothing",
                                valid=True,
                                refusal_reason=None,
                                input_tokens=180,
                                output_tokens=40,
                                latency_ms=400,
                                attempt=1,
                            )
                        )

    # Humans: a real negative slope, plus a few attention-check failures.
    conditions = [(5, 15), (10, 20), (15, 15), (20, 10)]
    lines = ["respondent_id,cost,damage,choice,order_version,attention_passed"]
    for rid in range(1, args.n_humans + 1):
        passed = rng.random() > 0.07
        version = 1 if rid % 2 else 2
        level = rng.normal(2.2, 0.8)
        for cost, damage in conditions:
            choice = int(rng.random() < sigmoid(level + TRUE_HUMAN_SLOPE * cost))
            lines.append(
                f"{rid},{cost},{damage},{choice},{version},"
                f"{'true' if passed else 'false'}"
            )
    (out / "humans.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {raw_path} and {out / 'humans.csv'}")
    print(f"true human slope {TRUE_HUMAN_SLOPE}; true model slopes {TRUE_SLOPES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
