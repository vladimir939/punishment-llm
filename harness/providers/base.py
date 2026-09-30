"""Provider interface.

One interface, four implementations. Adding a model means adding one entry to
spec.json, nothing else.

Each implementation reports its own capabilities. When a requested setting is
unsupported, the *effective* value is recorded in the output rather than the
requested one, and a warning is emitted once at startup. Nothing is ever
silently substituted.

API keys are read from environment variables only — never accepted as
arguments, never logged, never written to disk.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from ..models import Capabilities, ModelSpec, ProviderResponse

# Prompts are short and answers must be too; this ceiling exists to stop a
# runaway reasoning trace from costing real money, not to shape the answer.
MAX_OUTPUT_TOKENS = 4096
MAX_OUTPUT_TOKENS_THINKING = 16000


class ProviderError(RuntimeError):
    """A call failed in a way the runner should record as api_error."""


class MissingCredentials(ProviderError):
    """The provider's API key environment variable is not set."""


class Provider(ABC):
    """Base class for a single provider's API."""

    name: str = ""
    env_var: str = ""

    def __init__(self, model: ModelSpec) -> None:
        self.model = model
        self._client = None
        self._warned: set[str] = set()

    # -- credentials -------------------------------------------------------

    def api_key(self) -> str:
        key = os.environ.get(self.env_var)
        if not key:
            raise MissingCredentials(
                f"{self.env_var} is not set. Export it in your shell; never put "
                f"it in a file or pass it as an argument."
            )
        return key

    def has_credentials(self) -> bool:
        return bool(os.environ.get(self.env_var))

    # -- capabilities ------------------------------------------------------

    @abstractmethod
    def capabilities(self) -> Capabilities: ...

    def effective_temperature(self) -> float | None:
        """The temperature actually in force, given what the model allows."""
        caps = self.capabilities()
        if self.model.temperature is None:
            return None
        if not caps.temperature_settable:
            self.warn_once(
                f"{self.model.id}: temperature={self.model.temperature} was "
                f"requested but {self.model.snapshot} does not accept it. "
                f"Recording temperature_effective as null."
            )
            return None
        return self.model.temperature

    def effective_thinking(self, requested: bool) -> bool:
        caps = self.capabilities()
        if requested == self.model.thinking or caps.thinking_toggleable:
            return requested
        self.warn_once(
            f"{self.model.id}: thinking={requested} was requested but "
            f"{self.model.snapshot} cannot toggle it. Recording "
            f"thinking_enabled as {self.model.thinking}."
        )
        return self.model.thinking

    def warn_once(self, message: str) -> None:
        if message not in self._warned:
            self._warned.add(message)
            print(f"  [warn] {message}")

    # -- calls -------------------------------------------------------------

    @abstractmethod
    def complete(self, prompt: str, *, thinking: bool) -> ProviderResponse:
        """Make one independent call. No shared context between observations."""

    # -- batch (optional) --------------------------------------------------

    def submit_batch(self, items: list[tuple[str, str]], *, thinking: bool) -> str:
        """Submit (custom_id, prompt) pairs; return a batch id."""
        raise NotImplementedError(f"{self.name} has no batch endpoint")

    def poll_batch(self, batch_id: str) -> bool:
        """True once results are ready."""
        raise NotImplementedError(f"{self.name} has no batch endpoint")

    def fetch_batch(self, batch_id: str) -> dict[str, ProviderResponse]:
        """Download results keyed by custom_id."""
        raise NotImplementedError(f"{self.name} has no batch endpoint")
