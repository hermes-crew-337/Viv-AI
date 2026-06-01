from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..apply import apply_comment_suggestion, apply_function_rename
from ..models import MutationPolicy


class ReviewApplyPanel:
    def __init__(self, vw: Any, mutation_policy: MutationPolicy = MutationPolicy.REVIEW_BEFORE_APPLY):
        self.vw = vw
        self.mutation_policy = mutation_policy
        self._queue: List[Dict[str, Any]] = []
        self.target_va: Optional[int] = None
        self.pending_name: Optional[str] = None
        self.pending_comment: Optional[str] = None

    @property
    def current_target_va(self) -> Optional[int]:
        return self.target_va

    def _load_current(self) -> None:
        if not self._queue:
            self.target_va = None
            self.pending_name = None
            self.pending_comment = None
            return
        current = self._queue[0]
        self.target_va = current['va']
        self.pending_name = current.get('proposed_name')
        self.pending_comment = current.get('proposed_comment')

    def stage_suggestions(self, va: int, proposed_name: Optional[str] = None, proposed_comment: Optional[str] = None) -> None:
        if not proposed_name and not proposed_comment:
            return
        self._queue.append({
            'va': va,
            'proposed_name': proposed_name,
            'proposed_comment': proposed_comment,
        })
        if self.target_va is None:
            self._load_current()

    def preview_queue(self) -> List[Dict[str, Any]]:
        return [
            {
                'va': f"0x{item['va']:08x}",
                'has_name': bool(item.get('proposed_name')),
                'has_comment': bool(item.get('proposed_comment')),
            }
            for item in self._queue
        ]

    def preview_actions(self) -> List[Dict[str, Any]]:
        if self.target_va is None:
            return []
        actions: List[Dict[str, Any]] = []
        if self.pending_name:
            actions.append({'kind': 'function_rename', 'va': f'0x{self.target_va:08x}', 'name': self.pending_name})
        if self.pending_comment:
            actions.append({'kind': 'comment', 'va': f'0x{self.target_va:08x}', 'comment': self.pending_comment})
        return actions

    def _apply_current_only(self, approved: bool = False) -> Dict[str, Any]:
        if self.target_va is None:
            return {'applied': False, 'results': [], 'reason': 'no staged suggestions'}
        if self.mutation_policy == MutationPolicy.CONSERVATIVE_READONLY:
            return {'applied': False, 'results': [], 'reason': f'mutation policy {self.mutation_policy.value} blocks mutation'}
        if self.mutation_policy == MutationPolicy.REVIEW_BEFORE_APPLY and not approved:
            return {'applied': False, 'results': [], 'reason': f'mutation policy {self.mutation_policy.value} requires explicit review'}

        results = []
        direct_policy = MutationPolicy.DIRECT_APPLY_ENABLED
        if self.pending_name:
            results.append(apply_function_rename(self.vw, self.target_va, self.pending_name, direct_policy))
        if self.pending_comment:
            results.append(apply_comment_suggestion(self.vw, self.target_va, self.pending_comment, direct_policy))
        applied = all(item.get('applied') for item in results) if results else False
        return {'applied': applied, 'results': results, 'reason': 'applied' if applied else 'one or more suggestions failed'}

    def apply_current(self, approved: bool = False) -> Dict[str, Any]:
        result = self._apply_current_only(approved=approved)
        if result.get('applied') and self._queue:
            self._queue.pop(0)
            self._load_current()
        return result

    def skip_current(self) -> bool:
        """Skip (remove) the current item from the queue without applying."""
        if not self._queue:
            return False
        self._queue.pop(0)
        self._load_current()
        return True

    def apply_all(self, approved: bool = False) -> Dict[str, Any]:
        if not self._queue:
            return {'applied': False, 'results': [], 'reason': 'no staged suggestions'}

        all_results: List[Dict[str, Any]] = []
        while self._queue:
            result = self._apply_current_only(approved=approved)
            all_results.extend(result.get('results', []))
            if not result.get('applied'):
                return {'applied': False, 'results': all_results, 'reason': result.get('reason', 'one or more suggestions failed')}
            self._queue.pop(0)
            self._load_current()

        return {'applied': True, 'results': all_results, 'reason': 'applied'}
