from __future__ import annotations

from typing import Any

from ..config import AiConfig
from ..models import MutationPolicy


def resolve_mutation_policy(value: Any) -> MutationPolicy:
    if isinstance(value, MutationPolicy):
        return value
    if value is None:
        return MutationPolicy.CONSERVATIVE_READONLY
    return MutationPolicy(str(value))


def assert_apply_allowed(policy: MutationPolicy) -> None:
    if policy == MutationPolicy.CONSERVATIVE_READONLY:
        raise RuntimeError('readonly policy blocks mutation')
    if policy == MutationPolicy.REVIEW_BEFORE_APPLY:
        raise RuntimeError('review required before apply')


def assert_provider_allowed(config: AiConfig, provider: Any) -> None:
    capabilities = getattr(provider, 'capabilities', None)
    is_local_only = bool(getattr(capabilities, 'local_only', False))
    provider_name = getattr(getattr(provider, 'config', None), 'provider_type', provider.__class__.__name__)
    if config.local_only and not is_local_only:
        raise RuntimeError(f'local-only policy blocks provider: {provider_name}')
    if not config.remote_providers_enabled and not is_local_only:
        raise RuntimeError(f'remote providers are disabled: {provider_name}')
