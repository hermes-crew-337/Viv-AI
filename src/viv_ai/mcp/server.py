from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .schemas import ToolResponse
from .session import WorkspaceSessionError, WorkspaceSessionManager
from .tools import build_default_registry


class VivAIMcpServer:
    def __init__(self, tool_registry: Optional[Dict[str, Callable[..., Dict[str, Any]]]] = None, session_manager: Optional[WorkspaceSessionManager] = None, workspace_loader=None, analysis_service=None):
        self.session_manager = session_manager or WorkspaceSessionManager(workspace_loader=workspace_loader, analysis_service=analysis_service)
        if session_manager is not None and analysis_service is not None:
            self.session_manager.analysis_service = analysis_service
        self.tool_registry = dict(tool_registry or build_default_registry())
        self.running = False

    def server_info(self) -> Dict[str, Any]:
        return {
            'name': 'viv_ai_mcp',
            'running': self.running,
            'tools': sorted(self.tool_registry.keys()),
        }

    def start(self) -> Dict[str, Any]:
        self.running = True
        return self.server_info()

    def stop(self) -> Dict[str, Any]:
        self.running = False
        return self.server_info()

    def call_tool(self, tool_name: str, **arguments) -> Dict[str, Any]:
        tool = self.tool_registry.get(tool_name)
        workspace_id = arguments.get('workspace_id')
        if tool is None:
            return ToolResponse.error_response(workspace_id, 'workspace', f'unknown tool: {tool_name}', provenance={'tool': tool_name}).to_dict()
        try:
            return tool(self.session_manager, **arguments)
        except WorkspaceSessionError as exc:
            return ToolResponse.error_response(workspace_id, 'workspace', str(exc), provenance={'tool': tool_name}).to_dict()
        except Exception as exc:
            return ToolResponse.error_response(workspace_id, 'workspace', f'{tool_name} failed: {exc}', provenance={'tool': tool_name}).to_dict()
