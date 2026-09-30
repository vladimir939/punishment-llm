"""Response parsing.

This is the single most important correctness requirement in the project.
Reasoning models routinely mention both "X" and "Y" while deliberating, so a
naive substring search would corrupt the dataset silently — a full set of
plausible-looking garbage. Two defences, applied in order:

1. Reasoning blocks are stripped before scanning.
2. The choice is read only from a line that *begins* with ``CHOICE:``, and only
   from the **last** such line — the final answer, never an intermediate one.

Anything that does not yield exactly one of X/Y is invalid, and invalid rows are
kept with a ``refusal_reason``. Nothing is ever dropped.
"""

from __future__ import annotations

import re

from .models import Condition, OptOrder, ParsedChoice, RefusalReason

# Closed reasoning blocks emitted by some providers inside the visible text.
_REASONING_BLOCK = re.compile(
    r"<\s*(thinking|think|reasoning|scratchpad)\s*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)

# A line whose content starts with CHOICE:, tolerating leading whitespace, a
# list bullet, and markdown emphasis around the word.
_CHOICE_LINE = re.compile(
    r"^[ \t]*(?:[-*>+][ \t]*)?[*_`]{0,3}[ \t]*CHOICE[ \t]*[*_`]{0,3}[ \t]*:[ \t]*(?P<rest>.*)$",
    re.IGNORECASE | re.MULTILINE,
)

_SITUATION_LINE = re.compile(
    r"^[ \t]*(?:[-*>+][ \t]*)?[*_`]{0,3}[ \t]*SITUATION[ \t]*(?P<n>\d+)[ \t]*[*_`]{0,3}[ \t]*:[ \t]*(?P<rest>.*)$",
    re.IGNORECASE | re.MULTILINE,
)

_XY = re.compile(r"\b([XY])\b")
_PAY = re.compile(r"\bPAY\b", re.IGNORECASE)
_NOTHING = re.compile(r"\bNOTHING\b", re.IGNORECASE)

_REFUSAL_MARKERS = (
    "i can't",
    "i cannot",
    "i can not",
    "i won't",
    "i will not",
    "i'm unable",
    "i am unable",
    "unable to assist",
    "cannot assist",
    "can't assist",
    "cannot provide",
    "can't provide",
    "not comfortable",
    "as an ai",
    "i'm not able",
    "i am not able",
    "не могу",
    "не буду",
    "я не в состоянии",
    "не имею возможности",
)


def strip_reasoning(text: str) -> str:
    """Remove closed reasoning blocks from visible text."""
    return _REASONING_BLOCK.sub(" ", text)


def looks_like_refusal(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


def _letter_from_choice_line(rest: str) -> str | None:
    """Return 'X'/'Y' if the line yields exactly one, else None."""
    # Fast path: the whole remainder is just the letter, possibly wrapped.
    bare = rest.strip().strip("[](){}<>\"'`*_ .,:;-").upper()
    if bare in {"X", "Y"}:
        return bare
    letters = set(_XY.findall(rest.upper()))
    if len(letters) == 1:
        return letters.pop()
    return None


def parse_single_choice(
    raw_response: str,
    opt_order: OptOrder,
    condition_id: str,
) -> ParsedChoice:
    """Parse a single-condition response into punish/nothing."""
    if raw_response is None or not raw_response.strip():
        return ParsedChoice(condition_id, None, False, RefusalReason.OFF_FORMAT)

    visible = strip_reasoning(raw_response)
    matches = _CHOICE_LINE.findall(visible)

    if not matches:
        if looks_like_refusal(visible):
            return ParsedChoice(condition_id, None, False, RefusalReason.REFUSED)
        return ParsedChoice(condition_id, None, False, RefusalReason.NO_CHOICE_LINE)

    # Only the final answer counts.
    letter = _letter_from_choice_line(matches[-1])
    if letter is None:
        rest_upper = matches[-1].upper()
        if set(_XY.findall(rest_upper)) == {"X", "Y"}:
            return ParsedChoice(condition_id, None, False, RefusalReason.AMBIGUOUS)
        return ParsedChoice(condition_id, None, False, RefusalReason.OFF_FORMAT)

    choice = "nothing" if letter == opt_order.nothing_label else "punish"
    return ParsedChoice(condition_id, choice, True, None)


def parse_multi_condition(
    raw_response: str,
    conditions: tuple[Condition, ...],
) -> list[ParsedChoice]:
    """Parse a multi-condition response, one result per condition.

    `conditions` must be in **presentation order** — SITUATION 1 maps to
    conditions[0], and so on. The X/Y counterbalancing does not apply here; the
    model answers PAY / NOTHING directly.
    """
    if raw_response is None or not raw_response.strip():
        return [
            ParsedChoice(c.id, None, False, RefusalReason.OFF_FORMAT)
            for c in conditions
        ]

    visible = strip_reasoning(raw_response)
    refusal = looks_like_refusal(visible)

    # Keep only the last answer for each situation number, for the same reason
    # we keep only the last CHOICE: line.
    answers: dict[int, str] = {}
    for match in _SITUATION_LINE.finditer(visible):
        answers[int(match.group("n"))] = match.group("rest")

    results: list[ParsedChoice] = []
    for index, condition in enumerate(conditions, start=1):
        rest = answers.get(index)
        if rest is None:
            reason = (
                RefusalReason.REFUSED if refusal else RefusalReason.NO_CHOICE_LINE
            )
            results.append(ParsedChoice(condition.id, None, False, reason))
            continue
        pays, nothings = bool(_PAY.search(rest)), bool(_NOTHING.search(rest))
        if pays and nothings:
            results.append(
                ParsedChoice(condition.id, None, False, RefusalReason.AMBIGUOUS)
            )
        elif pays:
            results.append(ParsedChoice(condition.id, "punish", True, None))
        elif nothings:
            results.append(ParsedChoice(condition.id, "nothing", True, None))
        else:
            results.append(
                ParsedChoice(condition.id, None, False, RefusalReason.OFF_FORMAT)
            )
    return results
