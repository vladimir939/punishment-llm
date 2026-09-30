"""OpenRouter routing: spec rewrite, request shape, and provenance recording."""

from __future__ import annotations

import csv

import pytest

from harness.config import ConfigError, via_openrouter
from harness.models import CSV_COLUMNS, ProviderResponse
from harness.providers import REGISTRY
from harness.providers.openrouter_provider import OpenRouterProvider, verify_ablation


class TestSpecRewrite:
    def test_every_model_is_rewritten_to_openrouter(self, spec):
        routed = via_openrouter(spec)
        assert all(m.provider == "openrouter" for m in routed.models.values())
        assert routed.models["xai_frontier"].snapshot == (
            "x-ai/grok-4.6"
        )

    def test_no_batch_suffix_is_used(self, spec):
        """OpenRouter's ':batch' ids 404 over chat/completions.

        They are only reachable through /api/beta/batches, which this harness
        does not implement, so no model id may carry the suffix.
        """
        routed = via_openrouter(spec)
        assert not any(
            m.snapshot.endswith(":batch") for m in routed.models.values()
        )

    def test_fast_is_a_no_op_while_no_batch_ids_are_configured(self, spec):
        cheap = via_openrouter(spec)
        fast = via_openrouter(spec, fast=True)
        assert {m.snapshot for m in cheap.models.values()} == {
            m.snapshot for m in fast.models.values()
        }

    def test_experimental_content_is_untouched(self, spec):
        routed = via_openrouter(spec)
        assert routed.personas == spec.personas
        assert routed.arms == spec.arms
        assert routed.condition_sets == spec.condition_sets
        assert routed.persona_sets == spec.persona_sets

    def test_batch_is_disabled_because_openrouter_has_no_batch_endpoint(self, spec):
        routed = via_openrouter(spec)
        assert all(not m.supports_batch for m in routed.models.values())

    def test_missing_openrouter_id_is_an_error_not_a_silent_skip(self, edit_spec):
        from harness.config import load_spec

        def mutate(d):
            d["models"][0].pop("openrouter", None)

        loaded = load_spec(edit_spec(mutate))
        with pytest.raises(ConfigError, match="needs an `openrouter` model id"):
            via_openrouter(loaded)

    def test_unnamespaced_openrouter_id_is_rejected(self, edit_spec):
        from harness.config import load_spec

        def mutate(d):
            d["models"][0]["openrouter"] = "claude-opus-5"

        with pytest.raises(ConfigError, match="namespaced model id"):
            load_spec(edit_spec(mutate))

    def test_registry_knows_openrouter(self):
        assert REGISTRY["openrouter"] is OpenRouterProvider

    def test_cell_planning_still_works_after_rewrite(self, spec):
        from harness.render import build_cells

        routed = via_openrouter(spec)
        cells = build_cells(
            routed, routed.models["nonreasoning_anchor"], routed.arms["A"]
        )
        assert len(cells) == 544
        assert all(c.prompt for c in cells)


class TestRequestShape:
    def _provider(self, spec, model_id="xai_frontier"):
        routed = via_openrouter(spec)
        return OpenRouterProvider(routed.models[model_id])

    def test_thinking_on_uses_the_configured_effort(self, spec):
        params = self._provider(spec)._params("hi", True)
        assert params["extra_body"]["reasoning"] == {"effort": "medium"}

    def test_effort_comes_from_spec_not_a_hardcoded_value(self, spec):
        import dataclasses

        routed = via_openrouter(spec)
        for effort in ("low", "medium", "high"):
            m = dataclasses.replace(
                routed.models["xai_frontier"], reasoning_effort=effort
            )
            params = OpenRouterProvider(m)._params("hi", True)
            assert params["extra_body"]["reasoning"] == {"effort": effort}

    def test_bad_effort_is_rejected(self, edit_spec):
        from harness.config import ConfigError, load_spec

        def mutate(d):
            d["models"][0]["reasoning_effort"] = "maximum"

        with pytest.raises(ConfigError, match="reasoning_effort"):
            load_spec(edit_spec(mutate))

    def test_thinking_off_disables_rather_than_hiding(self, spec):
        params = self._provider(spec)._params("hi", False)
        # `exclude` would only hide the trace; the ablation needs it truly off.
        assert params["extra_body"]["reasoning"] == {"enabled": False}
        assert "exclude" not in params["extra_body"]["reasoning"]

    def test_pinned_provider_disables_fallbacks(self, spec):
        params = self._provider(spec)._params("hi", True)
        assert params["extra_body"]["provider"] == {
            "order": ["xai"],
            "allow_fallbacks": False,
        }

    def test_unpinned_model_sends_no_provider_block(self, spec):
        import dataclasses

        routed = via_openrouter(spec)
        unpinned = dataclasses.replace(
            routed.models["nonreasoning_anchor"], openrouter_only=()
        )
        params = OpenRouterProvider(unpinned)._params("hi", False)
        assert "provider" not in params["extra_body"]

    def test_null_temperature_is_not_sent(self, spec):
        assert "temperature" not in self._provider(spec)._params("hi", True)

    def test_numeric_temperature_is_sent(self, spec):
        params = self._provider(spec, "nonreasoning_anchor")._params("hi", False)
        assert params["temperature"] == 1.0

    def test_model_string_is_the_namespaced_id(self, spec):
        assert self._provider(spec)._params("hi", True)["model"] == (
            "x-ai/grok-4.6"
        )


class TestProvenanceRecording:
    def test_served_by_and_reasoning_tokens_are_csv_columns(self):
        assert "served_by" in CSV_COLUMNS
        assert "reasoning_tokens" in CSV_COLUMNS

    def test_served_by_reaches_the_csv(self, spec, tmp_path, fake_provider_factory):
        from tests.test_runner import read_rows, run_once

        routed = via_openrouter(spec)
        provider = fake_provider_factory(
            routed.models["nonreasoning_anchor"],
            responses=[
                ProviderResponse(
                    text="CHOICE: X\nREASON: r.",
                    served_by="deepseek/deepseek-v4-flash",
                    reasoning_tokens=0,
                    input_tokens=90,
                    output_tokens=15,
                )
            ],
        )
        path = tmp_path / "raw.csv"
        run_once(routed, path, provider, arms=["A"], models=["nonreasoning_anchor"], limit=1)
        row = read_rows(path)[0]
        assert row["served_by"] == "deepseek/deepseek-v4-flash"
        assert row["model_snapshot"] == "deepseek/deepseek-v4-flash"


class TestAblationVerification:
    def _write(self, path, rows):
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["model_id", "thinking_enabled", "reasoning_tokens"])
            w.writerows(rows)

    def test_flags_a_model_that_ignored_the_disable(self, tmp_path):
        path = tmp_path / "raw.csv"
        self._write(
            path,
            [["m", "true", 800], ["m", "true", 900], ["m", "false", 750]],
        )
        assert "WARNING" in verify_ablation("m", str(path))

    def test_passes_when_reasoning_really_stopped(self, tmp_path):
        path = tmp_path / "raw.csv"
        self._write(
            path, [["m", "true", 800], ["m", "true", 900], ["m", "false", 0]]
        )
        assert "genuinely off" in verify_ablation("m", str(path))

    def test_reports_when_the_ablation_has_not_run(self, tmp_path):
        path = tmp_path / "raw.csv"
        self._write(path, [["m", "true", 800]])
        assert "run the ablation first" in verify_ablation("m", str(path))
