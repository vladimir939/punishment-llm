"""Internal data model.

Everything the harness passes around is one of these. Nothing here talks to a
provider or touches the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RefusalReason(str, Enum):
    """Why a response failed to yield a usable choice. Written to the CSV."""

    NO_CHOICE_LINE = "no_choice_line"
    AMBIGUOUS = "ambiguous"
    REFUSED = "refused"
    OFF_FORMAT = "off_format"
    API_ERROR = "api_error"


class OptOrder(str, Enum):
    """Which label the "do nothing" option carried in the rendered prompt.

    Alternates deterministically by repeat index: even repeats put "do nothing"
    on X, odd repeats put it on Y. Controls for position/label bias at no extra
    cost in calls.
    """

    NOTHING_X = "nothing_x"
    NOTHING_Y = "nothing_y"

    @classmethod
    def for_rep(cls, rep: int) -> "OptOrder":
        return cls.NOTHING_X if rep % 2 == 0 else cls.NOTHING_Y

    @property
    def nothing_label(self) -> str:
        return "X" if self is OptOrder.NOTHING_X else "Y"

    @property
    def punish_label(self) -> str:
        return "Y" if self is OptOrder.NOTHING_X else "X"


@dataclass(frozen=True)
class Condition:
    id: str
    cost: int
    damage: int


@dataclass(frozen=True)
class Persona:
    id: str
    label: str
    text: str | None
    budget: str | None
    norms: str | None
    set: str

    @property
    def block(self) -> str:
        """The rendered PERSONA block, empty string for the no-persona control."""
        return "" if self.text is None else f"PERSONA:\n{self.text}\n\n"


@dataclass(frozen=True)
class ModelSpec:
    id: str
    provider: str
    snapshot: str
    temperature: float | None
    thinking: bool
    supports_batch: bool
    # OpenRouter model id, e.g. "anthropic/claude-opus-5". Only used when the
    # spec is loaded with --via openrouter.
    openrouter: str | None = None
    # Optional upstream provider slugs to pin to, e.g. ("anthropic",). When set,
    # fallbacks are disabled so the same backend serves every call.
    openrouter_only: tuple[str, ...] = ()
    # Deliberation depth for the thinking-on condition: "low" | "medium" | "high".
    # Reasoning tokens bill as output and are ~95% of this study's cost, so this
    # is the main cost lever. It must be reported in the paper.
    reasoning_effort: str = "high"


@dataclass(frozen=True)
class Arm:
    id: str
    purpose: str
    template: str
    conditions: str
    personas: str
    reps: int
    role: str
    allocation: str
    language: str


@dataclass(frozen=True)
class Capabilities:
    """What a provider implementation can actually honour for a given model.

    When a requested setting is unsupported the runner records the *effective*
    value, never the requested one, and warns once at startup.
    """

    temperature_settable: bool
    thinking_toggleable: bool
    returns_reasoning_trace: bool
    supports_batch: bool


@dataclass
class Cell:
    """One unit of work: a single API call to be made (or already made)."""

    model: ModelSpec
    arm: Arm
    persona: Persona
    rep: int
    thinking_enabled: bool
    # For single-choice arms this holds exactly one condition; for
    # multi-condition arms it holds all of them, in presentation order.
    conditions: tuple[Condition, ...]
    opt_order: OptOrder
    prompt: str = ""
    prompt_sha256: str = ""
    situation_order: str = ""

    @property
    def is_multi(self) -> bool:
        return len(self.conditions) > 1

    def keys(self) -> list[tuple[str, str, str, str, int, bool]]:
        """Natural keys for idempotency — one per CSV row this cell will emit."""
        return [
            (
                self.model.id,
                self.arm.id,
                self.persona.id,
                c.id,
                self.rep,
                self.thinking_enabled,
            )
            for c in self.conditions
        ]


@dataclass
class ProviderResponse:
    """Raw result of one API call. Never truncated, never interpreted."""

    text: str
    reasoning_trace: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    temperature_effective: float | None = None
    thinking_effective: bool = False
    error: str | None = None
    # Which upstream provider actually served the call. Empty for direct
    # providers; set by OpenRouter, where routing can vary between calls.
    served_by: str = ""
    reasoning_tokens: int = 0


@dataclass
class ParsedChoice:
    """Result of parsing one condition out of one response."""

    condition_id: str
    parsed_choice: str | None  # "punish" | "nothing" | None
    valid: bool
    refusal_reason: RefusalReason | None = None


@dataclass
class Observation:
    """One CSV row."""

    run_id: str
    timestamp_utc: str
    model_id: str
    provider: str
    model_snapshot: str
    temperature_requested: float | None
    temperature_effective: float | None
    thinking_enabled: bool
    arm: str
    template: str
    language: str
    role: str
    allocation: str
    persona_id: str
    persona_budget: str | None
    persona_norms: str | None
    condition_id: str
    cost: int
    damage: int
    opt_order: str
    situation_order: str
    rep: int
    prompt_sha256: str
    raw_response: str
    reasoning_trace: str
    parsed_choice: str | None
    valid: bool
    refusal_reason: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: int
    attempt: int
    served_by: str = ""
    reasoning_tokens: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


CSV_COLUMNS: tuple[str, ...] = (
    "run_id",
    "timestamp_utc",
    "model_id",
    "provider",
    "model_snapshot",
    "temperature_requested",
    "temperature_effective",
    "thinking_enabled",
    "arm",
    "template",
    "language",
    "role",
    "allocation",
    "persona_id",
    "persona_budget",
    "persona_norms",
    "condition_id",
    "cost",
    "damage",
    "opt_order",
    "situation_order",
    "rep",
    "prompt_sha256",
    "raw_response",
    "reasoning_trace",
    "parsed_choice",
    "valid",
    "refusal_reason",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "latency_ms",
    "attempt",
    "served_by",
)
