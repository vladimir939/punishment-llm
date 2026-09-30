"""Provider registry.

Adding a model means adding one entry to spec.json. Adding a *provider* means
adding one module here and one line in REGISTRY.
"""

from __future__ import annotations

from ..models import ModelSpec
from .anthropic_provider import AnthropicProvider
from .base import Capabilities, MissingCredentials, Provider, ProviderError
from .deepseek_provider import DeepSeekProvider
from .google_provider import GoogleProvider
from .openai_provider import OpenAIProvider
from .openrouter_provider import OpenRouterProvider

REGISTRY: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "google": GoogleProvider,
    "deepseek": DeepSeekProvider,
    "openrouter": OpenRouterProvider,
}


def get_provider(model: ModelSpec) -> Provider:
    try:
        cls = REGISTRY[model.provider]
    except KeyError as exc:
        raise ProviderError(
            f"no implementation for provider {model.provider!r}. "
            f"Known: {sorted(REGISTRY)}"
        ) from exc
    return cls(model)


__all__ = [
    "Capabilities",
    "MissingCredentials",
    "OpenRouterProvider",
    "Provider",
    "ProviderError",
    "REGISTRY",
    "get_provider",
]
