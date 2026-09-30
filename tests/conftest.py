"""Shared fixtures. No test in this suite may hit a real API."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.config import load_spec  # noqa: E402
from harness.models import Capabilities, ProviderResponse  # noqa: E402
from harness.providers.base import Provider  # noqa: E402


@pytest.fixture
def project_root() -> Path:
    return ROOT


@pytest.fixture
def spec():
    return load_spec(ROOT / "spec.json", ROOT / "templates")


@pytest.fixture
def spec_dir(tmp_path: Path) -> Path:
    """A writable copy of spec.json + templates/, for validation tests."""
    shutil.copy(ROOT / "spec.json", tmp_path / "spec.json")
    shutil.copytree(ROOT / "templates", tmp_path / "templates")
    return tmp_path


@pytest.fixture
def edit_spec(spec_dir: Path):
    """Mutate the copied spec.json in place and return its path."""

    def _edit(mutate) -> Path:
        path = spec_dir / "spec.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return _edit


class FakeProvider(Provider):
    """Returns canned responses. Never opens a socket."""

    name = "fake"
    env_var = "FAKE_API_KEY"

    def __init__(self, model, responses=None, capabilities=None):
        super().__init__(model)
        self.responses = list(responses or [])
        self.calls: list[tuple[str, bool]] = []
        self._caps = capabilities or Capabilities(
            temperature_settable=True,
            thinking_toggleable=True,
            returns_reasoning_trace=True,
            supports_batch=False,
        )

    def capabilities(self) -> Capabilities:
        return self._caps

    def has_credentials(self) -> bool:
        return True

    def complete(self, prompt: str, *, thinking: bool) -> ProviderResponse:
        self.calls.append((prompt, thinking))
        if self.responses:
            item = self.responses.pop(0)
        else:
            item = "CHOICE: X\nREASON: default."
        if isinstance(item, ProviderResponse):
            return item
        return ProviderResponse(
            text=item,
            input_tokens=100,
            output_tokens=20,
            latency_ms=5,
            temperature_effective=self.effective_temperature(),
            thinking_effective=thinking,
        )


@pytest.fixture
def fake_provider_factory():
    return FakeProvider
