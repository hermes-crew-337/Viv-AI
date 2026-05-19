from typing import Any, Dict

from .models import MutationPolicy


def _result(applied: bool, reason: str, proposal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'applied': applied,
        'reason': reason,
        'proposal': proposal,
    }


def apply_function_rename(vw: Any, fva: int, new_name: str, policy: MutationPolicy) -> Dict[str, Any]:
    proposal = {'kind': 'function_rename', 'va': f'0x{fva:08x}', 'name': new_name}
    if policy == MutationPolicy.CONSERVATIVE_READONLY:
        return _result(False, 'readonly policy blocks mutation', proposal)
    if policy == MutationPolicy.REVIEW_BEFORE_APPLY:
        return _result(False, 'review required before apply', proposal)
    final_name = vw.makeName(fva, new_name)
    proposal['applied_name'] = final_name
    if not final_name:
        return _result(False, 'failed to apply function rename', proposal)
    if final_name != new_name:
        return _result(False, 'workspace applied a different name than requested', proposal)
    return _result(True, 'applied', proposal)


def apply_comment_suggestion(vw: Any, va: int, comment: str, policy: MutationPolicy) -> Dict[str, Any]:
    proposal = {'kind': 'comment', 'va': f'0x{va:08x}', 'comment': comment}
    if policy == MutationPolicy.CONSERVATIVE_READONLY:
        return _result(False, 'readonly policy blocks mutation', proposal)
    if policy == MutationPolicy.REVIEW_BEFORE_APPLY:
        return _result(False, 'review required before apply', proposal)
    vw.setComment(va, comment)
    return _result(True, 'applied', proposal)
