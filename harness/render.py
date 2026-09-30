"""Prompt rendering: derived payoffs, X/Y counterbalancing, situation shuffling.

All arithmetic that appears in a prompt is computed here, once, so the dry-run
output and the live call are guaranteed to be the same text.
"""

from __future__ import annotations

import hashlib
import random

from .config import ALLOCATION_PAYOFFS, Spec
from .models import Arm, Cell, Condition, ModelSpec, OptOrder, Persona


def payoffs(allocation: str, cost: int, damage: int) -> dict[str, int]:
    """Derived values for one condition.

    A divides their own $100; the punisher has a separate $50 wallet.
        b_after = 50 - cost
        c_after = 50 - cost
        a_after = a_keeps - damage
    """
    try:
        a_keeps, b_gets = ALLOCATION_PAYOFFS[allocation]
    except KeyError as exc:
        raise ValueError(f"unknown allocation {allocation!r}") from exc
    return {
        "a_keeps": a_keeps,
        "b_gets": b_gets,
        "cost": cost,
        "damage": damage,
        "b_after": 50 - cost,
        "c_after": 50 - cost,
        "a_after": a_keeps - damage,
    }


def situation_lines(
    spec: Spec, arm: Arm, conditions: tuple[Condition, ...]
) -> str:
    """Render the numbered SITUATION lines for a multi-condition prompt."""
    fragment = spec.templates["_situation_line_en"].strip("\n")
    return "\n".join(
        fragment.format(n=i, cost=c.cost, damage=c.damage)
        for i, c in enumerate(conditions, start=1)
    )


def shuffle_conditions(
    conditions: tuple[Condition, ...], run_key: str
) -> tuple[Condition, ...]:
    """Deterministic presentation-order shuffle, seeded from the run key.

    Seeded so a rerun reproduces the same order from the same key, and so the
    recorded `situation_order` always matches what was actually sent.
    """
    seed = int.from_bytes(hashlib.sha256(run_key.encode("utf-8")).digest()[:8], "big")
    order = list(conditions)
    random.Random(seed).shuffle(order)
    return tuple(order)


def run_key(
    model: ModelSpec,
    arm: Arm,
    persona: Persona,
    rep: int,
    thinking_enabled: bool,
) -> str:
    return f"{model.id}|{arm.id}|{persona.id}|{rep}|{int(thinking_enabled)}"


def render(spec: Spec, cell: Cell) -> Cell:
    """Fill the template for `cell` and record the prompt plus its sha256."""
    template = spec.template_for(cell.arm)
    order = cell.opt_order

    if cell.is_multi:
        # The multi-condition template states the 80/20 split inline and asks
        # for PAY/NOTHING per situation, so it takes no opt/payoff placeholders.
        prompt = template.format(
            persona_block=cell.persona.block,
            situation_lines=situation_lines(spec, cell.arm, cell.conditions),
        )
    else:
        (condition,) = cell.conditions
        values = payoffs(cell.arm.allocation, condition.cost, condition.damage)
        prompt = template.format(
            persona_block=cell.persona.block,
            opt1=order.nothing_label,
            opt2=order.punish_label,
            **values,
        )

    cell.prompt = prompt
    cell.prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cell.situation_order = (
        ",".join(c.id for c in cell.conditions) if cell.is_multi else ""
    )
    return cell


def build_cells(
    spec: Spec,
    model: ModelSpec,
    arm: Arm,
    *,
    thinking_enabled: bool | None = None,
) -> list[Cell]:
    """Enumerate every call this (model, arm) pair requires."""
    thinking = model.thinking if thinking_enabled is None else thinking_enabled
    conditions = spec.conditions_for(arm)
    personas = spec.personas_for(arm)

    reps = arm.reps
    if model.thinking:
        # Reasoning models are slower and dearer; cap repeats.
        reps = min(reps, spec.execution.reasoning_model_rep_cap)

    cells: list[Cell] = []
    for persona in personas:
        for rep in range(reps):
            key = run_key(model, arm, persona, rep, thinking)
            order = (
                OptOrder.for_rep(rep)
                if spec.execution.counterbalance_xy
                else OptOrder.NOTHING_X
            )
            if "multi_condition" in arm.template:
                presented = (
                    shuffle_conditions(conditions, key)
                    if spec.execution.shuffle_multi_condition_order
                    else conditions
                )
                cells.append(
                    render(
                        spec,
                        Cell(
                            model=model,
                            arm=arm,
                            persona=persona,
                            rep=rep,
                            thinking_enabled=thinking,
                            conditions=presented,
                            opt_order=order,
                        ),
                    )
                )
            else:
                for condition in conditions:
                    cells.append(
                        render(
                            spec,
                            Cell(
                                model=model,
                                arm=arm,
                                persona=persona,
                                rep=rep,
                                thinking_enabled=thinking,
                                conditions=(condition,),
                                opt_order=order,
                            ),
                        )
                    )
    return cells
