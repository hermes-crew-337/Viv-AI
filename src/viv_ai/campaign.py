"""Batch rename and comment campaign operations.

Campaign operations apply rename/comment actions to multiple functions or
addresses in a single request, respecting the session's mutation policy.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .apply import apply_comment_suggestion as _apply_comment, apply_function_rename as _apply_rename
from .models import MutationPolicy


def _make_proposal(vw: Any, fva: int, new_name: str, policy: MutationPolicy) -> Dict[str, Any]:
    """Apply (or propose) a function rename and return the structured result."""
    return _apply_rename(vw, fva, new_name, policy)


def campaign_renames(
    vw: Any,
    renames: List[Dict[str, Any]],
    policy: MutationPolicy,
) -> List[Dict[str, Any]]:
    """Apply a batch of function renames.

    Each item in *renames* must have 'fva' (int) and 'new_name' (str).
    Returns a list of result dicts in the same order, each with 'applied'
    and 'reason' fields.
    """
    results = []
    for item in renames:
        fva = int(item['fva'])
        new_name = str(item['new_name'])
        result = _make_proposal(vw, fva, new_name, policy)
        result['fva'] = f'0x{fva:08x}'
        result['proposal']['new_name'] = new_name
        results.append(result)
    return results


def campaign_comments(
    vw: Any,
    comments: List[Dict[str, Any]],
    policy: MutationPolicy,
) -> List[Dict[str, Any]]:
    """Apply a batch of address comments.

    Each item in *comments* must have 'va' (int) and 'comment' (str).
    Returns a list of result dicts.
    """
    results = []
    for item in comments:
        va = int(item['va'])
        comment = str(item['comment'])
        result = _apply_comment(vw, va, comment, policy)
        result['va'] = f'0x{va:08x}'
        result['proposal']['comment'] = comment
        results.append(result)
    return results
