from .base import BaseProvider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatProvider
from .anthropic import AnthropicProvider
from .gemini import GeminiProvider

_PROVIDER_TYPES = {
    'ollama': OllamaProvider,
    'openai_compat': OpenAICompatProvider,
    'anthropic': AnthropicProvider,
    'gemini': GeminiProvider,
}


def create_provider(config):
    provider_cls = _PROVIDER_TYPES.get(config.provider_type)
    if provider_cls is None:
        raise ValueError(f'unsupported provider type: {config.provider_type}')
    return provider_cls(config)

__all__ = [
    'BaseProvider',
    'OllamaProvider',
    'OpenAICompatProvider',
    'AnthropicProvider',
    'GeminiProvider',
    'create_provider',
]
