"""CSV output and idempotency.

Append mode, flushed after every row, so an interrupted run loses nothing. On
startup the existing file is read and every key already present with
valid=true is skipped — a rerun after a crash resumes rather than duplicating,
and repeats are never renumbered.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Iterable, Iterator

from .models import CSV_COLUMNS, Observation

Key = tuple[str, str, str, str, int, bool]

# raw_response and reasoning_trace are stored in full and can be long.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def _fmt(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes", "t"}


class ResultStore:
    """Append-only CSV writer with a completed-key index."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._completed: set[Key] = set()
        self._handle = None
        self._writer = None
        if self.path.exists():
            self._completed = set(self._read_completed_keys())

    def _read_completed_keys(self) -> Iterator[Key]:
        with self.path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                return
            missing = set(CSV_COLUMNS) - set(reader.fieldnames)
            if missing:
                raise ValueError(
                    f"{self.path} exists but is missing column(s) {sorted(missing)}. "
                    f"Refusing to append to a file with a different schema."
                )
            for row in reader:
                if not _parse_bool(row.get("valid", "")):
                    continue
                yield (
                    row["model_id"],
                    row["arm"],
                    row["persona_id"],
                    row["condition_id"],
                    int(row["rep"]),
                    _parse_bool(row["thinking_enabled"]),
                )

    @property
    def completed(self) -> set[Key]:
        return self._completed

    def is_done(self, key: Key) -> bool:
        return key in self._completed

    def __enter__(self) -> "ResultStore":
        is_new = not self.path.exists() or self.path.stat().st_size == 0
        self._handle = self.path.open("a", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(
            self._handle, fieldnames=list(CSV_COLUMNS), extrasaction="ignore"
        )
        if is_new:
            self._writer.writeheader()
            self._handle.flush()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._handle is not None:
            self._handle.flush()
            self._handle.close()
            self._handle = None
            self._writer = None

    def write(self, observation: Observation) -> None:
        if self._writer is None or self._handle is None:
            raise RuntimeError("ResultStore must be used as a context manager")
        row = {col: _fmt(getattr(observation, col)) for col in CSV_COLUMNS}
        self._writer.writerow(row)
        self._handle.flush()
        if observation.valid:
            self._completed.add(
                (
                    observation.model_id,
                    observation.arm,
                    observation.persona_id,
                    observation.condition_id,
                    observation.rep,
                    observation.thinking_enabled,
                )
            )

    def write_all(self, observations: Iterable[Observation]) -> None:
        for observation in observations:
            self.write(observation)
