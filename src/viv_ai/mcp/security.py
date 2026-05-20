from __future__ import annotations

from typing import Any

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
