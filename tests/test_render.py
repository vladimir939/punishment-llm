"""Rendering: derived payoff arithmetic, counterbalancing, shuffling."""

from __future__ import annotations

import re

import pytest

from harness.models import OptOrder
from harness.render import build_cells, payoffs, shuffle_conditions


class TestPayoffArithmetic:
    def test_unfair_allocation(self):
        v = payoffs("unfair", cost=5, damage=15)
        assert v["a_keeps"] == 80 and v["b_gets"] == 20
        assert v["b_after"] == 45  # 50 - 5
        assert v["c_after"] == 45
        assert v["a_after"] == 65  # 80 - 15

    def test_fair_allocation(self):
        v = payoffs("fair", cost=10, damage=20)
        assert v["a_keeps"] == 50 and v["b_gets"] == 50
        assert v["b_after"] == 40  # 50 - 10
        assert v["a_after"] == 30  # 50 - 20

    @pytest.mark.parametrize(
        ("cost", "damage"), [(5, 15), (10, 20), (15, 15), (20, 10)]
    )
    def test_core_conditions_all_leave_positive_balances(self, cost, damage):
        v = payoffs("unfair", cost, damage)
        assert v["b_after"] > 0 and v["a_after"] > 0

    def test_unknown_allocation_raises(self):
        with pytest.raises(ValueError):
            payoffs("lopsided", 5, 15)


class TestRenderedText:
    def test_arithmetic_appears_correctly_in_the_prompt(self, spec):
        model = spec.models["xai_frontier"]
        cells = build_cells(spec, model, spec.arms["A"])
        cell = next(c for c in cells if c.conditions[0].id == "c1" and c.rep == 0)
        assert "Person A chose to keep $80 and give $20 to Person B." in cell.prompt
        assert "Pay $5 of your own money to reduce Person A's payoff by" in cell.prompt
        assert "$15." in cell.prompt
        assert "You would keep $45 and Person A would keep $65." in cell.prompt

    def test_no_placeholder_survives_rendering(self, spec):
        model = spec.models["xai_frontier"]
        for arm_id in spec.arms:
            for cell in build_cells(spec, model, spec.arms[arm_id])[:12]:
                leftovers = re.findall(r"\{[a-z_0-9]+\}", cell.prompt)
                assert not leftovers, f"arm {arm_id}: unfilled {leftovers}"

    def test_no_persona_control_has_no_persona_block(self, spec):
        model = spec.models["xai_frontier"]
        cell = next(
            c
            for c in build_cells(spec, model, spec.arms["A"])
            if c.persona.id == "NONE"
        )
        assert not cell.prompt.startswith("PERSONA:")
        assert cell.prompt.startswith("SITUATION:")

    def test_persona_block_present_for_a_real_persona(self, spec):
        model = spec.models["xai_frontier"]
        cell = next(
            c
            for c in build_cells(spec, model, spec.arms["A"])
            if c.persona.id == "P01"
        )
        assert cell.prompt.startswith("PERSONA:\nYou are Артем")

    def test_third_party_arm_uses_person_c(self, spec):
        model = spec.models["xai_frontier"]
        cell = build_cells(spec, model, spec.arms["F"])[0]
        assert "You are Person C." in cell.prompt
        assert "does not\naffect your own money" in cell.prompt

    def test_fair_arm_shows_a_fifty_fifty_split(self, spec):
        model = spec.models["xai_frontier"]
        cell = build_cells(spec, model, spec.arms["D"])[0]
        assert "keep $50 and give $50" in cell.prompt

    def test_prompt_hash_is_stable_and_matches_the_text(self, spec):
        import hashlib

        model = spec.models["xai_frontier"]
        cell = build_cells(spec, model, spec.arms["A"])[0]
        expected = hashlib.sha256(cell.prompt.encode("utf-8")).hexdigest()
        assert cell.prompt_sha256 == expected


class TestCounterbalancing:
    def test_opt_order_alternates_by_repeat_index(self):
        assert OptOrder.for_rep(0) is OptOrder.NOTHING_X
        assert OptOrder.for_rep(1) is OptOrder.NOTHING_Y
        assert OptOrder.for_rep(2) is OptOrder.NOTHING_X
        assert OptOrder.for_rep(7) is OptOrder.NOTHING_Y

    def test_labels_flip_in_the_rendered_text(self, spec):
        model = spec.models["xai_frontier"]
        cells = build_cells(spec, model, spec.arms["A"])
        even = next(
            c for c in cells if c.rep == 0 and c.persona.id == "P01"
            and c.conditions[0].id == "c1"
        )
        odd = next(
            c for c in cells if c.rep == 1 and c.persona.id == "P01"
            and c.conditions[0].id == "c1"
        )
        assert "Option X: Do nothing." in even.prompt
        assert "Option Y: Pay $5" in even.prompt
        assert "Option Y: Do nothing." in odd.prompt
        assert "Option X: Pay $5" in odd.prompt

    def test_recorded_opt_order_matches_the_rendered_prompt(self, spec):
        model = spec.models["xai_frontier"]
        for cell in build_cells(spec, model, spec.arms["A"]):
            nothing = cell.opt_order.nothing_label
            assert f"Option {nothing}: Do nothing." in cell.prompt


class TestSituationShuffling:
    def test_shuffle_is_deterministic_for_a_given_key(self, spec):
        conds = spec.condition_sets["core"]
        assert shuffle_conditions(conds, "k1") == shuffle_conditions(conds, "k1")

    def test_different_keys_generally_differ(self, spec):
        conds = spec.condition_sets["core"]
        orders = {
            tuple(c.id for c in shuffle_conditions(conds, f"key{i}"))
            for i in range(40)
        }
        assert len(orders) > 1

    def test_shuffle_preserves_the_full_condition_set(self, spec):
        conds = spec.condition_sets["core"]
        out = shuffle_conditions(conds, "whatever")
        assert sorted(c.id for c in out) == sorted(c.id for c in conds)

    def test_recorded_order_matches_the_situation_lines(self, spec):
        model = spec.models["xai_frontier"]
        for cell in build_cells(spec, model, spec.arms["B"])[:8]:
            recorded = cell.situation_order.split(",")
            assert [c.id for c in cell.conditions] == recorded
            for i, condition in enumerate(cell.conditions, start=1):
                assert (
                    f"Situation {i}: pay ${condition.cost} to reduce "
                    f"Person A's payoff by ${condition.damage}."
                ) in cell.prompt


class TestCellEnumeration:
    def test_reasoning_models_are_rep_capped(self, spec):
        cap = spec.execution.reasoning_model_rep_cap
        thinking_model = spec.models["xai_frontier"]
        assert thinking_model.thinking
        reps = {c.rep for c in build_cells(spec, thinking_model, spec.arms["A"])}
        assert max(reps) == cap - 1

    def test_non_reasoning_models_use_the_full_reps(self, spec):
        model = spec.models["nonreasoning_anchor"]
        assert not model.thinking
        reps = {c.rep for c in build_cells(spec, model, spec.arms["A"])}
        assert max(reps) == spec.arms["A"].reps - 1

    def test_single_choice_arm_emits_one_cell_per_condition(self, spec):
        model = spec.models["nonreasoning_anchor"]
        arm = spec.arms["A"]
        cells = build_cells(spec, model, arm)
        expected = len(spec.personas_for(arm)) * arm.reps * len(spec.conditions_for(arm))
        assert len(cells) == expected
        assert all(len(c.conditions) == 1 for c in cells)

    def test_multi_condition_arm_emits_one_cell_per_repeat(self, spec):
        model = spec.models["nonreasoning_anchor"]
        arm = spec.arms["B"]
        cells = build_cells(spec, model, arm)
        assert len(cells) == len(spec.personas_for(arm)) * arm.reps
        assert all(len(c.conditions) == 4 for c in cells)

    def test_ablation_overrides_thinking(self, spec):
        model = spec.models["xai_frontier"]
        cells = build_cells(spec, model, spec.arms["A"], thinking_enabled=False)
        assert all(c.thinking_enabled is False for c in cells)
