"""Parser tests.

The first test here is the one that matters most: a reasoning model that
mentions both X and Y while deliberating must not corrupt the dataset.
"""

from __future__ import annotations

import pytest

from harness.models import Condition, OptOrder, RefusalReason
from harness.parsing import (
    parse_multi_condition,
    parse_single_choice,
    strip_reasoning,
)

NOTHING_X = OptOrder.NOTHING_X
NOTHING_Y = OptOrder.NOTHING_Y


class TestReasoningIsIgnored:
    def test_xy_inside_thinking_block_is_ignored(self):
        raw = (
            "<thinking>\n"
            "If I pick X I keep $70. If I pick Y I lose $5 but they lose $15.\n"
            "CHOICE: X is tempting. Actually let me reconsider — maybe Y.\n"
            "</thinking>\n"
            "CHOICE: Y\n"
            "REASON: The split was unfair and $5 is a small price."
        )
        result = parse_single_choice(raw, NOTHING_X, "c1")
        assert result.valid
        assert result.parsed_choice == "punish"  # Y == punish under nothing_x

    def test_only_the_final_choice_line_counts(self):
        raw = (
            "Let me work through it.\n"
            "CHOICE: X\n"
            "Hmm, on reflection that is wrong.\n"
            "CHOICE: Y\n"
            "REASON: Reconsidered."
        )
        result = parse_single_choice(raw, NOTHING_X, "c1")
        assert result.valid and result.parsed_choice == "punish"

    def test_prose_mentioning_x_and_y_before_the_choice_line(self):
        raw = (
            "Weighing X against Y, and considering that X preserves my money "
            "while Y costs me, I have decided.\n"
            "CHOICE: X\n"
            "REASON: Not worth it."
        )
        result = parse_single_choice(raw, NOTHING_X, "c1")
        assert result.valid and result.parsed_choice == "nothing"

    @pytest.mark.parametrize("tag", ["thinking", "think", "reasoning", "scratchpad"])
    def test_strip_reasoning_handles_common_tags(self, tag):
        assert "secret" not in strip_reasoning(f"<{tag}>secret</{tag}> visible")


class TestNormalisation:
    @pytest.mark.parametrize(
        ("order", "letter", "expected"),
        [
            (NOTHING_X, "X", "nothing"),
            (NOTHING_X, "Y", "punish"),
            (NOTHING_Y, "X", "punish"),
            (NOTHING_Y, "Y", "nothing"),
        ],
    )
    def test_both_mappings(self, order, letter, expected):
        result = parse_single_choice(f"CHOICE: {letter}\nREASON: x.", order, "c1")
        assert result.valid and result.parsed_choice == expected

    @pytest.mark.parametrize(
        "line",
        [
            "CHOICE: X",
            "CHOICE: [X]",
            "choice: x",
            "  CHOICE:   X  ",
            "**CHOICE:** X",
            "- CHOICE: X",
            "CHOICE: Option X",
            "CHOICE: X.",
        ],
    )
    def test_tolerated_formatting(self, line):
        result = parse_single_choice(f"{line}\nREASON: r.", NOTHING_X, "c1")
        assert result.valid and result.parsed_choice == "nothing"


class TestInvalidResponses:
    def test_empty_response_is_off_format(self):
        result = parse_single_choice("", NOTHING_X, "c1")
        assert not result.valid
        assert result.refusal_reason is RefusalReason.OFF_FORMAT

    def test_whitespace_only_is_off_format(self):
        result = parse_single_choice("   \n\t ", NOTHING_X, "c1")
        assert result.refusal_reason is RefusalReason.OFF_FORMAT

    def test_no_choice_line(self):
        result = parse_single_choice(
            "I would probably keep the money.", NOTHING_X, "c1"
        )
        assert not result.valid
        assert result.refusal_reason is RefusalReason.NO_CHOICE_LINE

    def test_refusal(self):
        result = parse_single_choice(
            "I cannot role-play as a person making financial decisions.",
            NOTHING_X,
            "c1",
        )
        assert result.refusal_reason is RefusalReason.REFUSED

    def test_russian_refusal(self):
        result = parse_single_choice("Извините, я не могу.", NOTHING_X, "c1")
        assert result.refusal_reason is RefusalReason.REFUSED

    def test_echoed_template_is_ambiguous(self):
        result = parse_single_choice("CHOICE: [X or Y]", NOTHING_X, "c1")
        assert not result.valid
        assert result.refusal_reason is RefusalReason.AMBIGUOUS

    def test_choice_line_without_a_letter_is_off_format(self):
        result = parse_single_choice("CHOICE: maybe\nREASON: r.", NOTHING_X, "c1")
        assert not result.valid
        assert result.refusal_reason is RefusalReason.OFF_FORMAT

    def test_invalid_result_carries_the_condition_id(self):
        assert parse_single_choice("", NOTHING_X, "f3").condition_id == "f3"


CONDS = (
    Condition("c3", 15, 15),
    Condition("c1", 5, 15),
    Condition("c4", 20, 10),
    Condition("c2", 10, 20),
)


class TestMultiCondition:
    def test_one_result_per_condition_in_presentation_order(self):
        raw = (
            "SITUATION 1: NOTHING\n"
            "SITUATION 2: PAY\n"
            "SITUATION 3: NOTHING\n"
            "SITUATION 4: PAY\n"
            "REASON: Price matters."
        )
        results = parse_multi_condition(raw, CONDS)
        assert [r.condition_id for r in results] == ["c3", "c1", "c4", "c2"]
        assert [r.parsed_choice for r in results] == [
            "nothing",
            "punish",
            "nothing",
            "punish",
        ]
        assert all(r.valid for r in results)

    def test_missing_situation_is_invalid_but_others_survive(self):
        raw = "SITUATION 1: PAY\nSITUATION 2: PAY\nSITUATION 4: NOTHING"
        results = parse_multi_condition(raw, CONDS)
        assert [r.valid for r in results] == [True, True, False, True]
        assert results[2].refusal_reason is RefusalReason.NO_CHOICE_LINE

    def test_both_keywords_on_one_line_is_ambiguous(self):
        raw = "SITUATION 1: PAY or NOTHING\nSITUATION 2: PAY\n"
        results = parse_multi_condition(raw, CONDS)
        assert results[0].refusal_reason is RefusalReason.AMBIGUOUS

    def test_reasoning_block_is_ignored(self):
        raw = (
            "<thinking>SITUATION 1: PAY looks right... no, NOTHING.</thinking>\n"
            "SITUATION 1: NOTHING\nSITUATION 2: NOTHING\n"
            "SITUATION 3: NOTHING\nSITUATION 4: NOTHING\n"
        )
        results = parse_multi_condition(raw, CONDS)
        assert all(r.parsed_choice == "nothing" for r in results)

    def test_empty_response_yields_one_invalid_row_per_condition(self):
        results = parse_multi_condition("", CONDS)
        assert len(results) == len(CONDS)
        assert all(not r.valid for r in results)
