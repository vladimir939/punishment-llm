"""Runner and storage: idempotency, invalid-row retention, retry-once."""

from __future__ import annotations

import csv

import pytest

from harness.models import CSV_COLUMNS, ProviderResponse
from harness.runner import Runner, build_plan
from harness.storage import ResultStore


def read_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def run_once(spec, path, provider, *, arms, models, limit=None, concurrency=1):
    """Run a plan against a fake provider, patching the registry lookup."""
    import harness.runner as runner_module

    plan = build_plan(spec, arms=arms, models=models)
    if limit is not None:
        for model_id in list(plan.by_model):
            plan.by_model[model_id] = plan.by_model[model_id][:limit]

    original = runner_module.get_provider
    runner_module.get_provider = lambda model: provider
    try:
        with ResultStore(path) as store:
            return Runner(
                spec, store, concurrency=concurrency, verbose=False
            ).run_sync(plan)
    finally:
        runner_module.get_provider = original


@pytest.fixture
def provider(spec, fake_provider_factory):
    return fake_provider_factory(spec.models["nonreasoning_anchor"])


class TestCsvSchema:
    def test_header_matches_the_documented_columns(self, spec, tmp_path, provider):
        path = tmp_path / "raw.csv"
        run_once(spec, path, provider, arms=["A"], models=["nonreasoning_anchor"], limit=3)
        with open(path, encoding="utf-8") as fh:
            header = fh.readline().strip().split(",")
        assert header == list(CSV_COLUMNS)

    def test_row_records_reproducibility_fields(self, spec, tmp_path, provider):
        path = tmp_path / "raw.csv"
        run_once(spec, path, provider, arms=["A"], models=["nonreasoning_anchor"], limit=1)
        row = read_rows(path)[0]
        assert row["model_snapshot"] == spec.models["nonreasoning_anchor"].snapshot
        assert row["timestamp_utc"]
        assert len(row["prompt_sha256"]) == 64
        assert row["opt_order"] in {"nothing_x", "nothing_y"}
        assert row["temperature_requested"] == "1.0"


class TestIdempotency:
    def test_second_run_over_the_same_config_adds_no_rows(
        self, spec, tmp_path, fake_provider_factory
    ):
        path = tmp_path / "raw.csv"
        p1 = fake_provider_factory(spec.models["nonreasoning_anchor"])
        run_once(spec, path, p1, arms=["A"], models=["nonreasoning_anchor"], limit=6)
        first = read_rows(path)
        assert len(first) == 6

        p2 = fake_provider_factory(spec.models["nonreasoning_anchor"])
        run_once(spec, path, p2, arms=["A"], models=["nonreasoning_anchor"], limit=6)
        assert len(read_rows(path)) == 6
        assert p2.calls == [], "second run must make no API calls"

    def test_reps_are_not_renumbered_on_resume(
        self, spec, tmp_path, fake_provider_factory
    ):
        path = tmp_path / "raw.csv"
        run_once(
            spec,
            path,
            fake_provider_factory(spec.models["nonreasoning_anchor"]),
            arms=["A"],
            models=["nonreasoning_anchor"],
            limit=4,
        )
        before = {(r["persona_id"], r["condition_id"], r["rep"]) for r in read_rows(path)}
        run_once(
            spec,
            path,
            fake_provider_factory(spec.models["nonreasoning_anchor"]),
            arms=["A"],
            models=["nonreasoning_anchor"],
            limit=8,
        )
        after = {(r["persona_id"], r["condition_id"], r["rep"]) for r in read_rows(path)}
        assert before <= after
        assert len(after) == len(read_rows(path)), "no duplicate natural keys"

    def test_invalid_rows_are_retried_on_the_next_run(
        self, spec, tmp_path, fake_provider_factory
    ):
        path = tmp_path / "raw.csv"
        bad = fake_provider_factory(
            spec.models["nonreasoning_anchor"], responses=["no choice here"] * 4
        )
        run_once(spec, path, bad, arms=["A"], models=["nonreasoning_anchor"], limit=2)
        assert all(r["valid"] == "false" for r in read_rows(path))

        good = fake_provider_factory(spec.models["nonreasoning_anchor"])
        run_once(spec, path, good, arms=["A"], models=["nonreasoning_anchor"], limit=2)
        assert good.calls, "an invalid key must be retried, not treated as done"


class TestInvalidHandling:
    def test_invalid_rows_are_written_not_dropped(
        self, spec, tmp_path, fake_provider_factory
    ):
        path = tmp_path / "raw.csv"
        provider = fake_provider_factory(
            spec.models["nonreasoning_anchor"], responses=["I cannot help with that."] * 10
        )
        run_once(spec, path, provider, arms=["A"], models=["nonreasoning_anchor"], limit=3)
        rows = read_rows(path)
        assert len(rows) == 3
        assert all(r["valid"] == "false" for r in rows)
        assert all(r["refusal_reason"] == "refused" for r in rows)
        assert all(r["parsed_choice"] == "" for r in rows)

    def test_retry_exactly_once_then_record(
        self, spec, tmp_path, fake_provider_factory
    ):
        provider = fake_provider_factory(
            spec.models["nonreasoning_anchor"], responses=["garbage", "garbage"]
        )
        path = tmp_path / "raw.csv"
        run_once(spec, path, provider, arms=["A"], models=["nonreasoning_anchor"], limit=1)
        assert len(provider.calls) == 2, "one call plus exactly one retry"
        row = read_rows(path)[0]
        assert row["valid"] == "false" and row["attempt"] == "2"

    def test_retry_rescues_a_transient_bad_format(
        self, spec, tmp_path, fake_provider_factory
    ):
        provider = fake_provider_factory(
            spec.models["nonreasoning_anchor"], responses=["garbage", "CHOICE: Y\nREASON: r."]
        )
        path = tmp_path / "raw.csv"
        run_once(spec, path, provider, arms=["A"], models=["nonreasoning_anchor"], limit=1)
        row = read_rows(path)[0]
        assert row["valid"] == "true" and row["attempt"] == "2"
        assert row["parsed_choice"] == "punish"

    def test_api_error_becomes_a_row_not_a_crash(
        self, spec, tmp_path, fake_provider_factory
    ):
        provider = fake_provider_factory(
            spec.models["nonreasoning_anchor"],
            responses=[ProviderResponse(text="", error="boom")] * 4,
        )
        path = tmp_path / "raw.csv"
        run_once(spec, path, provider, arms=["A"], models=["nonreasoning_anchor"], limit=2)
        rows = read_rows(path)
        assert len(rows) == 2
        assert all(r["refusal_reason"] == "api_error" for r in rows)

    def test_full_response_is_stored_untruncated(
        self, spec, tmp_path, fake_provider_factory
    ):
        long_reason = "x" * 5000
        provider = fake_provider_factory(
            spec.models["nonreasoning_anchor"],
            responses=[f"CHOICE: X\nREASON: {long_reason}"],
        )
        path = tmp_path / "raw.csv"
        run_once(spec, path, provider, arms=["A"], models=["nonreasoning_anchor"], limit=1)
        assert long_reason in read_rows(path)[0]["raw_response"]


class TestMultiConditionRows:
    def test_one_row_per_condition_sharing_a_run_id(
        self, spec, tmp_path, fake_provider_factory
    ):
        answer = (
            "SITUATION 1: PAY\nSITUATION 2: NOTHING\n"
            "SITUATION 3: PAY\nSITUATION 4: NOTHING\nREASON: r."
        )
        provider = fake_provider_factory(spec.models["nonreasoning_anchor"], responses=[answer])
        path = tmp_path / "raw.csv"
        run_once(spec, path, provider, arms=["B"], models=["nonreasoning_anchor"], limit=1)
        rows = read_rows(path)
        assert len(rows) == 4
        assert len({r["run_id"] for r in rows}) == 1
        assert len({r["condition_id"] for r in rows}) == 4
        assert all(r["situation_order"] for r in rows)
        assert all(r["arm"] == "B" for r in rows)


class TestPlanning:
    def test_unknown_arm_is_rejected(self, spec):
        with pytest.raises(ValueError, match="unknown arm"):
            build_plan(spec, arms=["Z"])

    def test_unknown_model_is_rejected(self, spec):
        with pytest.raises(ValueError, match="unknown model"):
            build_plan(spec, models=["gpt-9"])

    def test_ablation_plan_flips_thinking_off(self, spec):
        plan = build_plan(spec, ablation=True)
        assert plan.by_model
        assert all(not c.thinking_enabled for c in plan.cells)
        assert all(c.arm.id == "A" for c in plan.cells)

    def test_full_volume_matches_the_study_design(self, spec):
        """A non-reasoning model runs the full uncapped repeat counts."""
        plan = build_plan(spec, models=["nonreasoning_anchor"])
        per_arm: dict[str, int] = {}
        for cell in plan.cells:
            per_arm[cell.arm.id] = per_arm.get(cell.arm.id, 0) + 1
        assert per_arm == {"A": 544, "B": 136, "C": 340, "D": 48, "E": 96, "F": 120}
        assert len(plan) == 1284
