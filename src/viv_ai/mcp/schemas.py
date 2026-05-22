from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolRequest:
    workspace_id: Optional[str]
    request_scope: str
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'workspace_id': self.workspace_id,
            'request_scope': self.request_scope,
            'tool_name': self.tool_name,
            'arguments': dict(self.arguments),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolRequest':
        data = dict(data or {})
        return cls(
            workspace_id=data.get('workspace_id'),
            request_scope=data.get('request_scope', 'workspace'),
            tool_name=data.get('tool_name', ''),
            arguments=dict(data.get('arguments') or {}),
        )


class ToolResponse:
    def __init__(self, ok: bool, workspace_id: Optional[str], request_scope: str, data: Optional[Dict[str, Any]] = None, warnings: Optional[List[str]] = None, truncated: bool = False, provenance: Optional[Dict[str, Any]] = None, summary: str = '', error: Optional[str] = None):
        self.ok = ok
        self.workspace_id = workspace_id
        self.request_scope = request_scope
        self.data = dict(data or {})
        self.warnings = list(warnings or [])
        self.truncated = truncated
        self.provenance = dict(provenance or {})
        self.summary = summary
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ok': self.ok,
            'workspace_id': self.workspace_id,
            'request_scope': self.request_scope,
            'data': dict(self.data),
            'warnings': list(self.warnings),
            'truncated': self.truncated,
            'provenance': dict(self.provenance),
            'summary': self.summary,
            'error': self.error,
        }

    @classmethod
    def ok(cls, workspace_id: Optional[str], request_scope: str, data: Dict[str, Any], warnings: Optional[List[str]] = None, truncated: bool = False, provenance: Optional[Dict[str, Any]] = None, summary: str = '') -> 'ToolResponse':
        return cls(True, workspace_id, request_scope, data=data, warnings=warnings, truncated=truncated, provenance=provenance, summary=summary)

    @classmethod
    def error_response(cls, workspace_id: Optional[str], request_scope: str, error: str, warnings: Optional[List[str]] = None, provenance: Optional[Dict[str, Any]] = None) -> 'ToolResponse':
        return cls(False, workspace_id, request_scope, data={}, warnings=warnings, truncated=False, provenance=provenance, summary='', error=error)
