"""Config validation must fail loudly. A typo must never shrink the dataset."""

from __future__ import annotations

import pytest

from harness.config import ConfigError, load_spec


class TestValidSpec:
    def test_real_spec_loads(self, spec):
        assert spec.version == "2.0"
        assert set(spec.arms) == {"A", "B", "C", "D", "E", "F"}
        assert len(spec.personas) == 17

    def test_all_original_personas_are_pasted_in_verbatim(self, spec):
        for pid in [f"P{i:02d}" for i in range(1, 11)]:
            text = spec.personas[pid].text
            assert text and "REPLACE_WITH" not in text
            assert text.startswith("You are ")

    def test_no_persona_control_has_null_text(self, spec):
        assert spec.personas["NONE"].text is None
        assert spec.personas["NONE"].block == ""

    def test_budget_grid_is_a_full_three_by_two(self, spec):
        grid = {
            (p.budget, p.norms)
            for p in spec.personas.values()
            if p.set == "budget_grid"
        }
        assert grid == {
            (b, n)
            for b in ("tight", "moderate", "comfortable")
            for n in ("strict", "loose")
        }

    def test_every_template_referenced_by_an_arm_exists(self, spec):
        for arm in spec.arms.values():
            assert arm.template in spec.templates


class TestRejections:
    def test_unknown_persona_id_in_a_persona_set(self, edit_spec):
        path = edit_spec(lambda d: d["persona_sets"]["all"].append("P99"))
        with pytest.raises(ConfigError, match="unknown persona id"):
            load_spec(path)

    def test_typo_in_a_persona_set_is_not_silently_ignored(self, edit_spec):
        def mutate(d):
            d["persona_sets"]["subset"] = ["N01", "N3", "NONE"]

        with pytest.raises(ConfigError, match="unknown persona id"):
            load_spec(edit_spec(mutate))

    def test_missing_template(self, edit_spec):
        def mutate(d):
            d["arms"]["A"]["template"] = "does_not_exist"

        with pytest.raises(ConfigError, match="no matching file in"):
            load_spec(edit_spec(mutate))

    def test_situation_line_fragment_is_not_a_prompt(self, edit_spec):
        def mutate(d):
            d["arms"]["A"]["template"] = "_situation_line_en"

        with pytest.raises(ConfigError, match="not a standalone prompt"):
            load_spec(edit_spec(mutate))

    @pytest.mark.parametrize(
        ("field", "bad"), [("cost", 0), ("cost", -5), ("damage", 0), ("cost", "5")]
    )
    def test_malformed_condition_numbers(self, edit_spec, field, bad):
        def mutate(d):
            d["condition_sets"]["core"][0][field] = bad

        with pytest.raises(ConfigError, match="positive integer"):
            load_spec(edit_spec(mutate))

    def test_cost_above_the_punisher_wallet(self, edit_spec):
        def mutate(d):
            d["condition_sets"]["core"][0]["cost"] = 60

        with pytest.raises(ConfigError, match="non-positive balance"):
            load_spec(edit_spec(mutate))

    def test_duplicate_condition_id(self, edit_spec):
        def mutate(d):
            d["condition_sets"]["core"][1]["id"] = "c1"

        with pytest.raises(ConfigError, match="duplicate condition id"):
            load_spec(edit_spec(mutate))

    def test_unknown_key_anywhere_is_rejected(self, edit_spec):
        def mutate(d):
            d["arms"]["A"]["repetitions"] = 8

        with pytest.raises(ConfigError, match="unrecognised key"):
            load_spec(edit_spec(mutate))

    def test_placeholder_model_snapshot(self, edit_spec):
        def mutate(d):
            d["models"][0]["snapshot"] = "FILL_IN_EXACT_MODEL_STRING"

        with pytest.raises(ConfigError, match="still a placeholder"):
            load_spec(edit_spec(mutate))

    def test_placeholder_persona_text(self, edit_spec):
        def mutate(d):
            d["personas"]["P01"]["text"] = "REPLACE_WITH_ORIGINAL_TEXT"

        with pytest.raises(ConfigError, match="still a placeholder"):
            load_spec(edit_spec(mutate))

    def test_unknown_provider(self, edit_spec):
        def mutate(d):
            d["models"][0]["provider"] = "mistral"

        with pytest.raises(ConfigError, match="is not one of"):
            load_spec(edit_spec(mutate))

    def test_bad_allocation(self, edit_spec):
        def mutate(d):
            d["arms"]["A"]["allocation"] = "slightly_unfair"

        with pytest.raises(ConfigError, match="allocation must be one of"):
            load_spec(edit_spec(mutate))

    def test_bad_role(self, edit_spec):
        def mutate(d):
            d["arms"]["F"]["role"] = "bystander"

        with pytest.raises(ConfigError, match="role must be one of"):
            load_spec(edit_spec(mutate))

    def test_zero_reps(self, edit_spec):
        def mutate(d):
            d["arms"]["A"]["reps"] = 0

        with pytest.raises(ConfigError, match="reps must be a positive integer"):
            load_spec(edit_spec(mutate))

    def test_multi_condition_arm_needs_exactly_four_conditions(self, edit_spec):
        def mutate(d):
            d["arms"]["B"]["conditions"] = "single"

        with pytest.raises(ConfigError, match="expects 4 SITUATION lines"):
            load_spec(edit_spec(mutate))

    def test_ablation_referencing_an_unknown_model(self, edit_spec):
        def mutate(d):
            d["thinking_ablation"]["models"] = ["not_a_model"]

        with pytest.raises(ConfigError, match="unknown model id"):
            load_spec(edit_spec(mutate))

    def test_duplicate_model_id(self, edit_spec):
        def mutate(d):
            d["models"][1]["id"] = d["models"][0]["id"]

        with pytest.raises(ConfigError, match="duplicate model id"):
            load_spec(edit_spec(mutate))

    def test_missing_spec_file(self, tmp_path):
        with pytest.raises(ConfigError, match="spec file not found"):
            load_spec(tmp_path / "nope.json")

    def test_missing_templates_directory(self, spec_dir):
        import shutil

        shutil.rmtree(spec_dir / "templates")
        with pytest.raises(ConfigError, match="templates directory not found"):
            load_spec(spec_dir / "spec.json")

    def test_invalid_json(self, spec_dir):
        (spec_dir / "spec.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(ConfigError, match="not valid JSON"):
            load_spec(spec_dir / "spec.json")
