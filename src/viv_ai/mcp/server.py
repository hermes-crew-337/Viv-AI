from __future__ import annotations

import enum
import signal
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Event, Lock, Thread, current_thread, main_thread
from typing import Any, Callable, Dict, Optional

from .schemas import ToolResponse
from .security import resolve_mutation_policy
from .session import WorkspaceSessionError, WorkspaceSessionManager
from .tools import build_default_registry, build_tool_metadata


class ServerMode(enum.Enum):
    """Workspace access mode for the MCP server."""
    LOCAL = 'local'
    REMOTE = 'remote'
    HYBRID = 'hybrid'


class _ToolTimeout(RuntimeError):
    pass


@dataclass
class _AsyncCallState:
    done: Event
    result: Optional[Dict[str, Any]] = None
    error: Optional[BaseException] = None


@contextmanager
def _time_limit(seconds: float):
    """Enforce a wall-clock timeout via SIGALRM (Unix-only).

    Falls through with no timeout enforcement on non-Unix platforms
    where signal.SIGALRM is unavailable (e.g. Windows).
    """
    if not hasattr(signal, 'SIGALRM'):
        # No SIGALRM available — timeout is a best-effort hint
        yield
        return

    def _handle_timeout(signum, frame):
        raise _ToolTimeout(f'timed out after {seconds:g}s')

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    signal.signal(signal.SIGALRM, _handle_timeout)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer != (0.0, 0.0):
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


class VivAIMcpServer:
    def __init__(self, tool_registry: Optional[Dict[str, Callable[..., Dict[str, Any]]]] = None, session_manager: Optional[WorkspaceSessionManager] = None, workspace_loader=None, analysis_service=None, mutation_policy=None, read_only: Optional[bool] = None, max_concurrent_tools: Optional[int] = None, max_tool_seconds: Optional[float] = None, mode: ServerMode = ServerMode.HYBRID):
        self.mode = mode
        self.session_manager = session_manager or WorkspaceSessionManager(workspace_loader=workspace_loader, analysis_service=analysis_service, mutation_policy=mutation_policy, mode=mode.value)
        if session_manager is not None:
            if analysis_service is not None:
                self.session_manager.analysis_service = analysis_service
            if mutation_policy is not None:
                self.session_manager.mutation_policy = resolve_mutation_policy(mutation_policy)
        # read_only is a high-level bool that overrides the mutation_policy
        # derived from config — IF mutation_policy wasn't explicitly provided.
        # When mutation_policy is explicitly set, it always takes precedence.
        if read_only is not None and mutation_policy is None:
            from ..models import MutationPolicy
            if read_only:
                self.session_manager.mutation_policy = MutationPolicy.CONSERVATIVE_READONLY
            elif self.session_manager.mutation_policy == MutationPolicy.CONSERVATIVE_READONLY:
                # No explicit mutation_policy was set, so flip to enabled
                self.session_manager.mutation_policy = MutationPolicy.DIRECT_APPLY_ENABLED
        config = getattr(getattr(self.session_manager, 'analysis_service', None), 'config', None)
        self.max_concurrent_tools = int(max_concurrent_tools if max_concurrent_tools is not None else getattr(config, 'mcp_max_concurrent_tools', 4))
        self.max_tool_seconds = float(max_tool_seconds if max_tool_seconds is not None else getattr(config, 'mcp_max_tool_seconds', 30))
        self._active_calls = 0
        self._call_lock = Lock()
        self.tool_registry = dict(tool_registry or build_default_registry())
        self.tool_metadata = build_tool_metadata()
        self.running = False

    def _release_active_call(self) -> None:
        with self._call_lock:
            self._active_calls -= 1

    def server_info(self) -> Dict[str, Any]:
        return {
            'name': 'viv_ai_mcp',
            'running': self.running,
            'tools': sorted(self.tool_registry.keys()),
            'tool_metadata': {name: self.tool_metadata[name] for name in sorted(self.tool_registry.keys()) if name in self.tool_metadata},
            'limits': {
                'max_concurrent_tools': self.max_concurrent_tools,
                'max_tool_seconds': self.max_tool_seconds,
            },
            'mutation_policy': self.session_manager.mutation_policy.value,
            'read_only': self.session_manager.mutation_policy.value == 'conservative_readonly',
            'mode': self.mode.value,
        }

    def start(self) -> Dict[str, Any]:
        self.running = True
        return self.server_info()

    def stop(self) -> Dict[str, Any]:
        self.running = False
        return self.server_info()

    def _run_tool_in_background(self, tool, arguments):
        state = _AsyncCallState(done=Event())

        def runner() -> None:
            try:
                state.result = tool(self.session_manager, **arguments)
            except BaseException as exc:
                state.error = exc
            finally:
                state.done.set()
                self._release_active_call()

        Thread(target=runner, daemon=True).start()
        return state

    def call_tool(self, tool_name: str, **arguments) -> Dict[str, Any]:
        tool = self.tool_registry.get(tool_name)
        workspace_id = arguments.get('workspace_id')
        if tool is None:
            return ToolResponse.error_response(workspace_id, 'workspace', f'unknown tool: {tool_name}', provenance={'tool': tool_name}).to_dict()
        with self._call_lock:
            if self._active_calls >= self.max_concurrent_tools:
                return ToolResponse.error_response(workspace_id, 'workspace', f'{tool_name} failed: concurrency limit reached', provenance={'tool': tool_name}).to_dict()
            self._active_calls += 1

        if self.max_tool_seconds > 0 and current_thread() is not main_thread():
            state = self._run_tool_in_background(tool, arguments)
            if not state.done.wait(timeout=self.max_tool_seconds):
                return ToolResponse.error_response(workspace_id, 'workspace', f'{tool_name} failed: timed out after {self.max_tool_seconds:g}s', provenance={'tool': tool_name}).to_dict()
            if state.error is not None:
                if isinstance(state.error, WorkspaceSessionError):
                    return ToolResponse.error_response(workspace_id, 'workspace', str(state.error), provenance={'tool': tool_name}).to_dict()
                return ToolResponse.error_response(workspace_id, 'workspace', f'{tool_name} failed: {state.error}', provenance={'tool': tool_name}).to_dict()
            return state.result or ToolResponse.error_response(workspace_id, 'workspace', f'{tool_name} failed: empty result', provenance={'tool': tool_name}).to_dict()

        try:
            if self.max_tool_seconds > 0:
                with _time_limit(self.max_tool_seconds):
                    return tool(self.session_manager, **arguments)
            return tool(self.session_manager, **arguments)
        except _ToolTimeout as exc:
            return ToolResponse.error_response(workspace_id, 'workspace', f'{tool_name} failed: {exc}', provenance={'tool': tool_name}).to_dict()
        except WorkspaceSessionError as exc:
            return ToolResponse.error_response(workspace_id, 'workspace', str(exc), provenance={'tool': tool_name}).to_dict()
        except Exception as exc:
            return ToolResponse.error_response(workspace_id, 'workspace', f'{tool_name} failed: {exc}', provenance={'tool': tool_name}).to_dict()
        finally:
            self._release_active_call()
