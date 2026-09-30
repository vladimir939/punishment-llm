"""Orchestration.

Every call is independent — no shared context between observations, ever. A
leaked conversation history would invalidate the entire dataset, so a fresh
single-message request is constructed for each cell and nothing is carried
between them.
"""

from __future__ import annotations

import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import Spec
from .costs import Estimate, estimate
from .models import (
    Cell,
    ModelSpec,
    Observation,
    ParsedChoice,
    ProviderResponse,
    RefusalReason,
)
from .parsing import parse_multi_condition, parse_single_choice
from .providers import Provider, ProviderError, get_provider
from .render import build_cells
from .storage import ResultStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Progress:
    total: int = 0
    completed: int = 0
    skipped: int = 0
    invalid: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    spend_usd: float = 0.0

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.completed - self.skipped)

    def line(self) -> str:
        return (
            f"  done {self.completed:>5}  remaining {self.remaining:>5}  "
            f"invalid {self.invalid:>4}  ~${self.spend_usd:0.2f}"
        )


@dataclass
class Plan:
    """The full set of cells a run will execute, grouped by model."""

    by_model: dict[str, list[Cell]] = field(default_factory=dict)

    @property
    def cells(self) -> list[Cell]:
        return [c for cells in self.by_model.values() for c in cells]

    def __len__(self) -> int:
        return len(self.cells)


def build_plan(
    spec: Spec,
    *,
    arms: list[str] | None = None,
    models: list[str] | None = None,
    ablation: bool = False,
) -> Plan:
    """Enumerate every call the requested subset requires."""
    plan = Plan()
    if ablation:
        ab = spec.thinking_ablation
        arm = spec.arms[ab.arm]
        for model_id in ab.models:
            if models and model_id not in models:
                continue
            model = spec.models[model_id]
            plan.by_model.setdefault(model_id, []).extend(
                build_cells(
                    spec, model, arm, thinking_enabled=not ab.thinking_off
                )
            )
        return plan

    wanted_arms = arms or sorted(spec.arms)
    wanted_models = models or [m.id for m in spec.models.values()]
    unknown_arms = [a for a in wanted_arms if a not in spec.arms]
    if unknown_arms:
        raise ValueError(f"unknown arm(s) {unknown_arms}; known: {sorted(spec.arms)}")
    unknown_models = [m for m in wanted_models if m not in spec.models]
    if unknown_models:
        raise ValueError(
            f"unknown model(s) {unknown_models}; known: {sorted(spec.models)}"
        )

    for model_id in wanted_models:
        model = spec.models[model_id]
        for arm_id in wanted_arms:
            plan.by_model.setdefault(model_id, []).extend(
                build_cells(spec, model, spec.arms[arm_id])
            )
    return plan


def estimate_plan(plan: Plan, spec: Spec, *, batch: bool = False) -> Estimate:
    total = Estimate(0, 0, 0, 0.0, True)
    for model_id, cells in plan.by_model.items():
        model = spec.models[model_id]
        use_batch = batch and model.supports_batch
        total = total + estimate(
            [c.prompt for c in cells],
            model.snapshot,
            thinking=any(c.thinking_enabled for c in cells),
            batch=use_batch,
            effort=model.reasoning_effort,
        )
    return total


def parse_cell(cell: Cell, response: ProviderResponse) -> list[ParsedChoice]:
    if response.error:
        reason = (
            RefusalReason.REFUSED
            if response.error == "refusal"
            else RefusalReason.API_ERROR
        )
        return [ParsedChoice(c.id, None, False, reason) for c in cell.conditions]
    if cell.is_multi:
        return parse_multi_condition(response.text, cell.conditions)
    (condition,) = cell.conditions
    return [parse_single_choice(response.text, cell.opt_order, condition.id)]


def to_observations(
    cell: Cell,
    response: ProviderResponse,
    parsed: list[ParsedChoice],
    *,
    run_id: str,
    attempt: int,
) -> list[Observation]:
    by_id = {c.id: c for c in cell.conditions}
    timestamp = _now()
    rows: list[Observation] = []
    for result in parsed:
        condition = by_id[result.condition_id]
        rows.append(
            Observation(
                run_id=run_id,
                timestamp_utc=timestamp,
                model_id=cell.model.id,
                provider=cell.model.provider,
                model_snapshot=cell.model.snapshot,
                temperature_requested=cell.model.temperature,
                temperature_effective=response.temperature_effective,
                thinking_enabled=cell.thinking_enabled,
                arm=cell.arm.id,
                template=cell.arm.template,
                language=cell.arm.language,
                role=cell.arm.role,
                allocation=cell.arm.allocation,
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
                # When a call fails there is no model text, so the error
                # detail goes here instead of being discarded. Invalid rows
                # are excluded from the slope analysis anyway.
                raw_response=(
                    response.text
                    or (f"[error] {response.error}" if response.error else "")
                ),
                reasoning_trace=response.reasoning_trace,
                parsed_choice=result.parsed_choice,
                valid=result.valid,
                refusal_reason=(
                    result.refusal_reason.value if result.refusal_reason else None
                ),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                reasoning_tokens=response.reasoning_tokens,
                latency_ms=response.latency_ms,
                attempt=attempt,
                served_by=response.served_by,
            )
        )
    return rows


def call_with_backoff(
    provider: Provider,
    prompt: str,
    *,
    thinking: bool,
    base: float,
    cap: float,
    tries: int = 5,
) -> ProviderResponse:
    """Exponential backoff with jitter on rate limits and 5xx.

    On final failure returns a response carrying an error — never raises, never
    crashes the run.
    """
    last = ""
    for attempt in range(tries):
        try:
            return provider.complete(prompt, thinking=thinking)
        except ProviderError as exc:
            last = str(exc)
            transient = any(
                token in last.lower()
                for token in ("rate", "429", "500", "502", "503", "504", "overload",
                              "timeout", "connection")
            )
            if not transient or attempt == tries - 1:
                break
            delay = min(cap, base * (2**attempt)) + random.uniform(0, base)
            time.sleep(delay)
    return ProviderResponse(text="", error=last or "api_error")


class Runner:
    """Executes a plan against live providers."""

    def __init__(
        self,
        spec: Spec,
        store: ResultStore,
        *,
        concurrency: int = 4,
        verbose: bool = True,
    ) -> None:
        self.spec = spec
        self.store = store
        self.concurrency = max(1, concurrency)
        self.verbose = verbose
        self.progress = Progress()

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)

    def run_sync(self, plan: Plan) -> Progress:
        self.progress.total = sum(len(c.conditions) for c in plan.cells)
        for model_id, cells in plan.by_model.items():
            model = self.spec.models[model_id]
            provider = get_provider(model)
            if not provider.has_credentials():
                self._log(
                    f"  [skip] {model_id}: {provider.env_var} is not set; "
                    f"skipping {len(cells)} cell(s)"
                )
                self.progress.skipped += sum(len(c.conditions) for c in cells)
                continue
            self._warm_capabilities(provider, model)
            todo = [c for c in cells if not self._already_done(c)]
            self.progress.skipped += sum(
                len(c.conditions) for c in cells if c not in todo
            )
            self._log(
                f"  {model_id} ({model.snapshot}): {len(todo)} call(s) to make, "
                f"{len(cells) - len(todo)} already complete"
            )
            self._execute(provider, todo)
        return self.progress

    def _warm_capabilities(self, provider: Provider, model: ModelSpec) -> None:
        provider.effective_temperature()
        provider.effective_thinking(model.thinking)

    def _already_done(self, cell: Cell) -> bool:
        return all(self.store.is_done(k) for k in cell.keys())

    def _execute(self, provider: Provider, cells: list[Cell]) -> None:
        execution = self.spec.execution
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            for cell, rows in zip(
                cells,
                pool.map(lambda c: self._one_cell(provider, c), cells),
            ):
                for row in rows:
                    self.store.write(row)
                    self.progress.completed += 1
                    self.progress.input_tokens += row.input_tokens
                    self.progress.output_tokens += row.output_tokens
                    if not row.valid:
                        self.progress.invalid += 1
                if self.verbose and self.progress.completed % 25 == 0:
                    self._log(self.progress.line())
        _ = execution  # execution settings are consumed inside _one_cell

    def _one_cell(self, provider: Provider, cell: Cell) -> list[Observation]:
        execution = self.spec.execution
        run_id = uuid.uuid4().hex
        attempt = 1
        response = call_with_backoff(
            provider,
            cell.prompt,
            thinking=cell.thinking_enabled,
            base=execution.backoff_base_seconds,
            cap=execution.backoff_max_seconds,
        )
        parsed = parse_cell(cell, response)

        # On invalid, retry exactly once with the identical prompt in a fresh
        # context. If the second attempt is also invalid the row is written
        # anyway, with valid=false — invalid rows are a reported result.
        if any(not p.valid for p in parsed) and execution.max_retries_on_invalid > 0:
            attempt = 2
            retry = call_with_backoff(
                provider,
                cell.prompt,
                thinking=cell.thinking_enabled,
                base=execution.backoff_base_seconds,
                cap=execution.backoff_max_seconds,
            )
            retry_parsed = parse_cell(cell, retry)
            if sum(p.valid for p in retry_parsed) >= sum(p.valid for p in parsed):
                response, parsed = retry, retry_parsed

        return to_observations(cell, response, parsed, run_id=run_id, attempt=attempt)

    # -- batch -------------------------------------------------------------

    def run_batch(self, plan: Plan, poll_seconds: int = 60) -> Progress:
        """Submit via each provider's batch endpoint where available.

        Roughly half cost and higher throughput, up to 24-hour turnaround.
        Results are persisted to CSV immediately on retrieval because batch
        results expire server-side after about a month. Providers without batch
        support fall back to sync automatically.
        """
        self.progress.total = sum(len(c.conditions) for c in plan.cells)
        for model_id, cells in plan.by_model.items():
            model = self.spec.models[model_id]
            provider = get_provider(model)
            if not provider.has_credentials():
                self._log(f"  [skip] {model_id}: {provider.env_var} is not set")
                self.progress.skipped += sum(len(c.conditions) for c in cells)
                continue
            todo = [c for c in cells if not self._already_done(c)]
            if not todo:
                continue
            if not (model.supports_batch and provider.capabilities().supports_batch):
                self._log(f"  {model_id}: no batch endpoint, falling back to sync")
                self._warm_capabilities(provider, model)
                self._execute(provider, todo)
                continue

            by_cid = {uuid.uuid4().hex: cell for cell in todo}
            thinking = todo[0].thinking_enabled
            self._log(f"  {model_id}: submitting {len(by_cid)} request(s) as a batch")
            batch_id = provider.submit_batch(
                [(cid, cell.prompt) for cid, cell in by_cid.items()],
                thinking=thinking,
            )
            self._log(f"  {model_id}: batch {batch_id} submitted; polling")
            while not provider.poll_batch(batch_id):
                time.sleep(poll_seconds)
            results = provider.fetch_batch(batch_id)
            for cid, cell in by_cid.items():
                response = results.get(cid) or ProviderResponse(
                    text="", error="batch_missing"
                )
                parsed = parse_cell(cell, response)
                for row in to_observations(
                    cell, response, parsed, run_id=cid, attempt=1
                ):
                    self.store.write(row)
                    self.progress.completed += 1
                    if not row.valid:
                        self.progress.invalid += 1
            self._log(self.progress.line())
        return self.progress
