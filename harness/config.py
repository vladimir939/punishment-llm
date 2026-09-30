"""Load and validate spec.json + templates/.

Validation is strict and fails loudly. A typo in a persona id must never
silently produce a smaller dataset, so every cross-reference is checked and
every unrecognised key is an error.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Arm, Condition, ModelSpec, Persona

VALID_PROVIDERS = {"anthropic", "openai", "google", "deepseek", "openrouter"}
VALID_ROLES = {"victim", "third_party"}
VALID_ALLOCATIONS = {"fair", "unfair"}
VALID_BUDGETS = {"tight", "moderate", "comfortable"}
VALID_NORMS = {"strict", "loose"}

REQUIRED_MODEL_KEYS = {
    "id",
    "provider",
    "snapshot",
    "temperature",
    "thinking",
    "supports_batch",
}
MODEL_KEYS = REQUIRED_MODEL_KEYS | {
    "openrouter",
    "openrouter_only",
    "reasoning_effort",
}
VALID_EFFORTS = {"low", "medium", "high"}
PERSONA_KEYS = {"label", "text", "budget", "norms", "set"}
ARM_KEYS = {
    "_purpose",
    "template",
    "conditions",
    "personas",
    "reps",
    "role",
    "allocation",
    "language",
}
CONDITION_KEYS = {"id", "cost", "damage"}
EXECUTION_KEYS = {
    "reasoning_model_rep_cap",
    "counterbalance_xy",
    "shuffle_multi_condition_order",
    "max_retries_on_invalid",
    "backoff_base_seconds",
    "backoff_max_seconds",
}
TOP_LEVEL_KEYS = {
    "version",
    "models",
    "personas",
    "condition_sets",
    "persona_sets",
    "arms",
    "thinking_ablation",
    "execution",
}

# Allocation -> (a_keeps, b_gets)
ALLOCATION_PAYOFFS = {"unfair": (80, 20), "fair": (50, 50)}


class ConfigError(ValueError):
    """Raised for any malformed or internally inconsistent configuration."""


@dataclass
class Execution:
    reasoning_model_rep_cap: int
    counterbalance_xy: bool
    shuffle_multi_condition_order: bool
    max_retries_on_invalid: int
    backoff_base_seconds: float
    backoff_max_seconds: float


@dataclass
class ThinkingAblation:
    arm: str
    models: tuple[str, ...]
    thinking_off: bool


@dataclass
class Spec:
    version: str
    models: dict[str, ModelSpec]
    personas: dict[str, Persona]
    condition_sets: dict[str, tuple[Condition, ...]]
    persona_sets: dict[str, tuple[str, ...]]
    arms: dict[str, Arm]
    thinking_ablation: ThinkingAblation
    execution: Execution
    templates: dict[str, str]

    def conditions_for(self, arm: Arm) -> tuple[Condition, ...]:
        return self.condition_sets[arm.conditions]

    def personas_for(self, arm: Arm) -> tuple[Persona, ...]:
        return tuple(self.personas[pid] for pid in self.persona_sets[arm.personas])

    def template_for(self, arm: Arm) -> str:
        return self.templates[arm.template]


def _reject_unknown(obj: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(obj) - allowed
    if unknown:
        raise ConfigError(
            f"{where}: unrecognised key(s) {sorted(unknown)}. "
            f"Allowed: {sorted(allowed)}. Refusing to run on a config I do not "
            f"fully understand."
        )


def _require(obj: dict[str, Any], required: set[str], where: str) -> None:
    missing = required - set(obj)
    if missing:
        raise ConfigError(f"{where}: missing required key(s) {sorted(missing)}")


def _load_templates(templates_dir: Path) -> dict[str, str]:
    if not templates_dir.is_dir():
        raise ConfigError(f"templates directory not found: {templates_dir}")
    out: dict[str, str] = {}
    for path in sorted(templates_dir.glob("*.txt")):
        out[path.stem] = path.read_text(encoding="utf-8")
    if not out:
        raise ConfigError(f"no .txt templates found in {templates_dir}")
    return out


def _parse_models(raw: Any) -> dict[str, ModelSpec]:
    if not isinstance(raw, list) or not raw:
        raise ConfigError("spec.models must be a non-empty list")
    models: dict[str, ModelSpec] = {}
    for i, m in enumerate(raw):
        where = f"spec.models[{i}]"
        if not isinstance(m, dict):
            raise ConfigError(f"{where} must be an object")
        _require(m, REQUIRED_MODEL_KEYS, where)
        _reject_unknown(m, MODEL_KEYS, where)
        if m["provider"] not in VALID_PROVIDERS:
            raise ConfigError(
                f"{where}.provider={m['provider']!r} is not one of "
                f"{sorted(VALID_PROVIDERS)}"
            )
        snapshot = m["snapshot"]
        if not isinstance(snapshot, str) or not snapshot or "FILL_IN" in snapshot:
            raise ConfigError(
                f"{where}.snapshot is still a placeholder ({snapshot!r}). "
                f"Put the exact model string in before running."
            )
        if m["id"] in models:
            raise ConfigError(f"{where}: duplicate model id {m['id']!r}")
        temp = m["temperature"]
        if temp is not None and not isinstance(temp, (int, float)):
            raise ConfigError(f"{where}.temperature must be a number or null")

        openrouter = m.get("openrouter")
        if openrouter is not None:
            if not isinstance(openrouter, str) or "/" not in openrouter:
                raise ConfigError(
                    f"{where}.openrouter must be a namespaced model id such as "
                    f"'anthropic/claude-opus-5', got {openrouter!r}"
                )
        only = m.get("openrouter_only", [])
        if not isinstance(only, list) or any(not isinstance(s, str) for s in only):
            raise ConfigError(f"{where}.openrouter_only must be a list of strings")
        effort = m.get("reasoning_effort", "high")
        if effort not in VALID_EFFORTS:
            raise ConfigError(
                f"{where}.reasoning_effort={effort!r} must be one of "
                f"{sorted(VALID_EFFORTS)}"
            )

        models[m["id"]] = ModelSpec(
            id=m["id"],
            provider=m["provider"],
            snapshot=snapshot,
            temperature=None if temp is None else float(temp),
            thinking=bool(m["thinking"]),
            supports_batch=bool(m["supports_batch"]),
            openrouter=openrouter,
            openrouter_only=tuple(only),
            reasoning_effort=effort,
        )
    return models


def _parse_personas(raw: Any) -> dict[str, Persona]:
    if not isinstance(raw, dict) or not raw:
        raise ConfigError("spec.personas must be a non-empty object")
    personas: dict[str, Persona] = {}
    for pid, p in raw.items():
        where = f"spec.personas[{pid}]"
        if not isinstance(p, dict):
            raise ConfigError(f"{where} must be an object")
        _require(p, PERSONA_KEYS, where)
        _reject_unknown(p, PERSONA_KEYS, where)
        text = p["text"]
        if text is not None:
            if not isinstance(text, str) or not text.strip():
                raise ConfigError(f"{where}.text must be a non-empty string or null")
            if "REPLACE_WITH" in text:
                raise ConfigError(
                    f"{where}.text is still a placeholder. Paste the verbatim "
                    f"original persona text in before running."
                )
        if p["budget"] is not None and p["budget"] not in VALID_BUDGETS:
            raise ConfigError(
                f"{where}.budget={p['budget']!r} not in {sorted(VALID_BUDGETS)}"
            )
        if p["norms"] is not None and p["norms"] not in VALID_NORMS:
            raise ConfigError(
                f"{where}.norms={p['norms']!r} not in {sorted(VALID_NORMS)}"
            )
        personas[pid] = Persona(
            id=pid,
            label=p["label"],
            text=text,
            budget=p["budget"],
            norms=p["norms"],
            set=p["set"],
        )
    return personas


def _parse_condition_sets(raw: Any) -> dict[str, tuple[Condition, ...]]:
    if not isinstance(raw, dict) or not raw:
        raise ConfigError("spec.condition_sets must be a non-empty object")
    sets: dict[str, tuple[Condition, ...]] = {}
    for name, conds in raw.items():
        where = f"spec.condition_sets[{name}]"
        if not isinstance(conds, list) or not conds:
            raise ConfigError(f"{where} must be a non-empty list")
        parsed: list[Condition] = []
        seen: set[str] = set()
        for j, c in enumerate(conds):
            cwhere = f"{where}[{j}]"
            if not isinstance(c, dict):
                raise ConfigError(f"{cwhere} must be an object")
            _require(c, CONDITION_KEYS, cwhere)
            _reject_unknown(c, CONDITION_KEYS, cwhere)
            for numeric in ("cost", "damage"):
                v = c[numeric]
                if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                    raise ConfigError(
                        f"{cwhere}.{numeric} must be a positive integer, got {v!r}"
                    )
            if c["cost"] >= 50:
                raise ConfigError(
                    f"{cwhere}.cost={c['cost']} would leave the punisher with a "
                    f"non-positive balance from their $50 wallet"
                )
            if c["id"] in seen:
                raise ConfigError(f"{cwhere}: duplicate condition id {c['id']!r}")
            seen.add(c["id"])
            parsed.append(Condition(id=c["id"], cost=c["cost"], damage=c["damage"]))
        sets[name] = tuple(parsed)
    return sets


def _parse_persona_sets(
    raw: Any, personas: dict[str, Persona]
) -> dict[str, tuple[str, ...]]:
    if not isinstance(raw, dict) or not raw:
        raise ConfigError("spec.persona_sets must be a non-empty object")
    sets: dict[str, tuple[str, ...]] = {}
    for name, ids in raw.items():
        where = f"spec.persona_sets[{name}]"
        if not isinstance(ids, list) or not ids:
            raise ConfigError(f"{where} must be a non-empty list")
        unknown = [pid for pid in ids if pid not in personas]
        if unknown:
            raise ConfigError(
                f"{where} references unknown persona id(s) {unknown}. "
                f"Known ids: {sorted(personas)}"
            )
        if len(set(ids)) != len(ids):
            raise ConfigError(f"{where} contains duplicate persona ids")
        sets[name] = tuple(ids)
    return sets


def _parse_arms(
    raw: Any,
    condition_sets: dict[str, tuple[Condition, ...]],
    persona_sets: dict[str, tuple[str, ...]],
    templates: dict[str, str],
) -> dict[str, Arm]:
    if not isinstance(raw, dict) or not raw:
        raise ConfigError("spec.arms must be a non-empty object")
    arms: dict[str, Arm] = {}
    for aid, a in raw.items():
        where = f"spec.arms[{aid}]"
        if not isinstance(a, dict):
            raise ConfigError(f"{where} must be an object")
        _require(a, ARM_KEYS - {"_purpose"}, where)
        _reject_unknown(a, ARM_KEYS, where)
        if a["template"] not in templates:
            raise ConfigError(
                f"{where}.template={a['template']!r} has no matching file in "
                f"templates/. Available: {sorted(templates)}"
            )
        if a["conditions"] not in condition_sets:
            raise ConfigError(
                f"{where}.conditions={a['conditions']!r} is not a known condition set"
            )
        if a["personas"] not in persona_sets:
            raise ConfigError(
                f"{where}.personas={a['personas']!r} is not a known persona set"
            )
        if a["role"] not in VALID_ROLES:
            raise ConfigError(f"{where}.role must be one of {sorted(VALID_ROLES)}")
        if a["allocation"] not in VALID_ALLOCATIONS:
            raise ConfigError(
                f"{where}.allocation must be one of {sorted(VALID_ALLOCATIONS)}"
            )
        reps = a["reps"]
        if not isinstance(reps, int) or isinstance(reps, bool) or reps < 1:
            raise ConfigError(f"{where}.reps must be a positive integer, got {reps!r}")
        arms[aid] = Arm(
            id=aid,
            purpose=a.get("_purpose", ""),
            template=a["template"],
            conditions=a["conditions"],
            personas=a["personas"],
            reps=reps,
            role=a["role"],
            allocation=a["allocation"],
            language=a["language"],
        )
    return arms


def _parse_ablation(
    raw: Any, arms: dict[str, Arm], models: dict[str, ModelSpec]
) -> ThinkingAblation:
    where = "spec.thinking_ablation"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where} must be an object")
    allowed = {"_purpose", "arm", "models", "thinking_off"}
    _require(raw, allowed - {"_purpose"}, where)
    _reject_unknown(raw, allowed, where)
    if raw["arm"] not in arms:
        raise ConfigError(f"{where}.arm={raw['arm']!r} is not a known arm")
    unknown = [m for m in raw["models"] if m not in models]
    if unknown:
        raise ConfigError(f"{where}.models references unknown model id(s) {unknown}")
    return ThinkingAblation(
        arm=raw["arm"],
        models=tuple(raw["models"]),
        thinking_off=bool(raw["thinking_off"]),
    )


def _parse_execution(raw: Any) -> Execution:
    where = "spec.execution"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where} must be an object")
    _require(raw, EXECUTION_KEYS, where)
    _reject_unknown(raw, EXECUTION_KEYS, where)
    return Execution(
        reasoning_model_rep_cap=int(raw["reasoning_model_rep_cap"]),
        counterbalance_xy=bool(raw["counterbalance_xy"]),
        shuffle_multi_condition_order=bool(raw["shuffle_multi_condition_order"]),
        max_retries_on_invalid=int(raw["max_retries_on_invalid"]),
        backoff_base_seconds=float(raw["backoff_base_seconds"]),
        backoff_max_seconds=float(raw["backoff_max_seconds"]),
    )


def via_openrouter(spec: Spec, *, fast: bool = False) -> Spec:
    """Rewrite every model to route through OpenRouter.

    `fast=True` strips the ":batch" suffix from every model id, trading roughly
    double the cost for immediate responses. Use it if the batch queue turns out
    to be too slow to fit the schedule.

    One spec.json stays the single source of truth: personas, arms and
    conditions are untouched, and only the provider and model string change.
    A model with no `openrouter` id in spec.json is an error rather than a
    silent skip — a smaller dataset must never happen by accident.
    """
    missing = [m.id for m in spec.models.values() if not m.openrouter]
    if missing:
        raise ConfigError(
            f"--via openrouter needs an `openrouter` model id for: {missing}. "
            f"Add one to each entry in spec.json, e.g. "
            f'"openrouter": "anthropic/claude-opus-5".'
        )
    def resolve(m: ModelSpec) -> str:
        target = m.openrouter or m.snapshot
        return target[: -len(":batch")] if fast and target.endswith(":batch") else target

    rewritten = {
        mid: ModelSpec(
            id=m.id,
            provider="openrouter",
            snapshot=resolve(m),
            temperature=m.temperature,
            thinking=m.thinking,
            # OpenRouter has no batch endpoint; the runner falls back to sync.
            supports_batch=False,
            openrouter=m.openrouter,
            openrouter_only=m.openrouter_only,
            reasoning_effort=m.reasoning_effort,
        )
        for mid, m in spec.models.items()
    }
    return Spec(
        version=spec.version,
        models=rewritten,
        personas=spec.personas,
        condition_sets=spec.condition_sets,
        persona_sets=spec.persona_sets,
        arms=spec.arms,
        thinking_ablation=spec.thinking_ablation,
        execution=spec.execution,
        templates=spec.templates,
    )


def load_spec(spec_path: str | Path, templates_dir: str | Path | None = None) -> Spec:
    """Read spec.json and templates/, validating everything on the way in."""
    spec_path = Path(spec_path)
    if not spec_path.is_file():
        raise ConfigError(f"spec file not found: {spec_path}")
    templates_dir = (
        Path(templates_dir)
        if templates_dir is not None
        else spec_path.parent / "templates"
    )

    try:
        raw = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{spec_path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("spec.json must contain a JSON object at the top level")

    # Underscore-prefixed top-level keys are free-form notes.
    checked = {k: v for k, v in raw.items() if not k.startswith("_")}
    _require(checked, TOP_LEVEL_KEYS, "spec")
    _reject_unknown(checked, TOP_LEVEL_KEYS, "spec")

    templates = _load_templates(templates_dir)
    models = _parse_models(raw["models"])
    personas = _parse_personas(raw["personas"])
    condition_sets = _parse_condition_sets(raw["condition_sets"])
    persona_sets = _parse_persona_sets(raw["persona_sets"], personas)
    arms = _parse_arms(raw["arms"], condition_sets, persona_sets, templates)
    ablation = _parse_ablation(raw["thinking_ablation"], arms, models)
    execution = _parse_execution(raw["execution"])

    # The multi-condition template hard-codes four SITUATION lines, so an arm
    # using it must supply exactly four conditions.
    for arm in arms.values():
        if "multi_condition" in arm.template:
            n = len(condition_sets[arm.conditions])
            if n != 4:
                raise ConfigError(
                    f"spec.arms[{arm.id}] uses {arm.template} which expects 4 "
                    f"SITUATION lines, but condition set {arm.conditions!r} has {n}"
                )
        if "_situation_line" in arm.template:
            raise ConfigError(
                f"spec.arms[{arm.id}].template points at the situation-line "
                f"fragment, which is not a standalone prompt"
            )

    return Spec(
        version=str(raw["version"]),
        models=models,
        personas=personas,
        condition_sets=condition_sets,
        persona_sets=persona_sets,
        arms=arms,
        thinking_ablation=ablation,
        execution=execution,
        templates=templates,
    )
