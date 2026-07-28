"""Managed workspace sessions with metadata, catalog tracking, and LRU cache.

Provides:
- :class:`WorkspaceSession` — a cached/open workspace with rich provenance metadata
- :class:`WorkspaceSessionManager` — open/close/list workspaces with optional LRU eviction
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Callable, Dict, List, Optional

from .filesystem import find_candidate_workspace_files, normalize_path, FilesystemPolicy
from .security import resolve_mutation_policy
from .server_connection import (
    ServerConnection,
    connect_to_server,
    get_remote_workspace,
)


class WorkspaceSessionError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass
class WorkspaceSession:
    """A managed workspace with full provenance and LRU metadata.

    Attributes:
        workspace_id: Short hash-based unique ID.
        path: The path or virtual path (``vivserver://...`` for server workspaces).
        workspace: The actual Vivisect workspace object.
        metadata: Dynamic metadata dict (architecture, platform, etc.).
        connection: Optional :class:`ServerConnection` for remote workspaces.

        # --- Phase V metadata ---
        selector_path: Original user-supplied selector (could be path, alias, etc.).
        binary_path: Absolute path to the binary if loaded from a binary.
        viv_path: Absolute path to the ``.viv`` file if loaded from one.
        alias: Stable alias derived from filename.
        source_kind: One of ``local_binary``, ``local_viv``, ``remote_workspace``.
        loaded_from_viv: Whether the workspace was loaded from an existing ``.viv``.
        created_from_binary: Whether the workspace was created by analyzing a binary.
        analysis_started: Whether analysis has begun.
        analysis_completed: Whether analysis has finished.
        estimated_size_bytes: Best-effort size estimate of the workspace.
        last_accessed_ts: Unix timestamp of most recent access.
        open_count: Number of times this session has been accessed.
    """

    workspace_id: str
    path: str
    workspace: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    connection: Optional[ServerConnection] = None

    # --- Phase V metadata ---
    selector_path: Optional[str] = None
    binary_path: Optional[str] = None
    viv_path: Optional[str] = None
    alias: Optional[str] = None
    source_kind: str = 'local_binary'
    loaded_from_viv: bool = False
    created_from_binary: bool = False
    analysis_started: bool = False
    analysis_completed: bool = False
    estimated_size_bytes: int = 0
    last_accessed_ts: float = field(default_factory=time.time)
    open_count: int = 1

    def touch(self) -> None:
        """Update the LRU timestamp and increment open count."""
        self.last_accessed_ts = time.time()
        self.open_count += 1

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            'workspace_id': self.workspace_id,
            'path': self.path,
            'metadata': dict(self.metadata),
            # Phase V fields
            'alias': self.alias,
            'source_kind': self.source_kind,
            'loaded_from_viv': self.loaded_from_viv,
            'analysis_started': self.analysis_started,
            'analysis_completed': self.analysis_completed,
            'estimated_size_bytes': self.estimated_size_bytes,
            'last_accessed_ts': self.last_accessed_ts,
            'open_count': self.open_count,
        }
        if self.connection is not None:
            d['connection'] = {
                'host': self.connection.host,
                'port': self.connection.port,
                'wsname': self.connection.wsname,
            }
        return d

    def __repr__(self) -> str:
        return (
            f'<WorkspaceSession {self.workspace_id} path={self.path!r} '
            f'kind={self.source_kind} viv={self.loaded_from_viv}>'
        )


# ---------------------------------------------------------------------------
# LRU Cache Manager
# ---------------------------------------------------------------------------


class WorkspaceSessionManager:
    """Manages open workspace sessions with optional LRU eviction.

    Maintains:
    - ``_sessions``: workspace_id -> WorkspaceSession
    - ``_path_index``: canonical path -> workspace_id
    - ``_alias_index``: alias -> workspace_id
    """

    def __init__(
        self,
        workspace_loader: Optional[Callable[[str], Any]] = None,
        analysis_service: Any = None,
        mutation_policy: Any = None,
        mode: str = 'hybrid',
        filesystem_policy: Optional[FilesystemPolicy] = None,
        max_cached: int = 8,
        max_cache_bytes: int = 2 * 1024 * 1024 * 1024,
        prefer_existing_viv: bool = True,
        force_reanalyze: bool = False,
        preserve_existing_viv: bool = True,
    ):
        self._sessions: Dict[str, WorkspaceSession] = {}
        self._path_index: Dict[str, str] = {}
        self._alias_index: Dict[str, str] = {}
        self.workspace_loader = workspace_loader
        self.analysis_service = analysis_service
        self.mutation_policy = resolve_mutation_policy(mutation_policy)
        self.mode = mode
        self.filesystem_policy = filesystem_policy or FilesystemPolicy()
        self.max_cached = max_cached
        self.max_cache_bytes = max_cache_bytes
        self.prefer_existing_viv = prefer_existing_viv
        self.force_reanalyze = force_reanalyze
        self.preserve_existing_viv = preserve_existing_viv

    # ---- ID generation ----

    def _make_workspace_id(self, path: str) -> str:
        return sha256(path.encode('utf-8')).hexdigest()[:12]

    # ---- Open / connect ----

    def open_workspace(self, path: str, workspace: Any = None) -> WorkspaceSession:
        """Open (or reuse) a workspace by local path, respecting ``.viv`` preference."""
        existing_id = self._path_index.get(path)
        if existing_id is not None:
            session = self._sessions[existing_id]
            session.touch()
            return session

        if workspace is None:
            if self.workspace_loader is None:
                raise WorkspaceSessionError('workspace loader is not configured')

            # Resolve best source: binary vs .viv
            viv_path, binary_path = find_candidate_workspace_files(
                path, self.filesystem_policy
            )

            if viv_path is not None and self.prefer_existing_viv and not self.force_reanalyze:
                source_kind = 'local_viv'
                loaded_from_viv = True
                created_from_binary = False
                actual_path = viv_path
                workspace = self.workspace_loader(actual_path)
            elif binary_path is not None:
                source_kind = 'local_binary'
                loaded_from_viv = False
                created_from_binary = True
                actual_path = binary_path
                workspace = self.workspace_loader(actual_path)
            else:
                # No file found on disk — fall through to the workspace_loader
                # with the original path (handles test fakes, virtual paths, etc.)
                workspace = self.workspace_loader(path)
                source_kind = 'local_binary'
                loaded_from_viv = False
                created_from_binary = True
                actual_path = path
        else:
            # workspace object provided directly
            source_kind = 'local_binary'
            loaded_from_viv = False
            created_from_binary = True
            actual_path = path

        workspace_id = self._make_workspace_id(actual_path)
        session = self._build_session(
            workspace_id=workspace_id,
            path=actual_path,
            workspace=workspace,
            source_kind=source_kind,
            loaded_from_viv=loaded_from_viv,
            created_from_binary=created_from_binary,
            original_path=path,
        )

        self._insert_session(session)
        return session

    def connect_server(self, host: str, port: int, wsname: str) -> WorkspaceSession:
        """Connect to a Vivisect Server and open a named workspace."""
        virtual_path = f'vivserver://{host}:{port}/{wsname}'
        existing_id = self._path_index.get(virtual_path)
        if existing_id is not None:
            session = self._sessions[existing_id]
            session.touch()
            return session

        server_proxy = connect_to_server(host, port)
        vw = get_remote_workspace(server_proxy, wsname)

        conn = ServerConnection(host=host, port=port, server=server_proxy, wsname=wsname)
        workspace_id = self._make_workspace_id(virtual_path)
        session = self._build_session(
            workspace_id=workspace_id,
            path=virtual_path,
            workspace=vw,
            source_kind='remote_workspace',
            loaded_from_viv=False,
            created_from_binary=False,
        )
        session.connection = conn
        session.metadata.update({
            'server_host': host,
            'server_port': port,
            'server_wsname': wsname,
            'server_type': 'vivremote',
        })

        self._insert_session(session)
        return session

    # ---- Session access ----

    def get_workspace(self, workspace_id: str) -> Any:
        session = self.get_session(workspace_id)
        return session.workspace

    def get_session(self, workspace_id: str) -> WorkspaceSession:
        session = self._sessions.get(workspace_id)
        if session is None:
            raise WorkspaceSessionError(f'unknown workspace id: {workspace_id}')
        session.touch()
        return session

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """Return sorted list by most recently accessed first."""
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.last_accessed_ts,
            reverse=True,
        )
        return [s.to_dict() for s in sessions]

    def close_workspace(self, workspace_id: str) -> bool:
        session = self._sessions.pop(workspace_id, None)
        if session is None:
            raise WorkspaceSessionError(f'unknown workspace id: {workspace_id}')
        self._path_index.pop(session.path, None)
        if session.alias:
            self._alias_index.pop(session.alias, None)
        return True

    # ---- Catalog queries ----

    def resolve_by_alias(self, alias: str) -> Optional[WorkspaceSession]:
        """Look up a session by its stable alias."""
        wid = self._alias_index.get(alias)
        if wid and wid in self._sessions:
            session = self._sessions[wid]
            session.touch()
            return session
        return None

    def resolve_by_path(self, path: str) -> Optional[WorkspaceSession]:
        """Look up a session by its canonical path."""
        wid = self._path_index.get(path)
        if wid and wid in self._sessions:
            session = self._sessions[wid]
            session.touch()
            return session
        return None

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Return catalog entries — includes all currently cached sessions."""
        return self.list_workspaces()

    # ---- LRU eviction ----

    def _evict_lru(self) -> None:
        """Evict sessions until under max_cached and max_cache_bytes.

        If ``max_cached`` is 0 (or negative) the cache is considered unlimited.
        """
        if self.max_cached <= 0:
            return

        while len(self._sessions) > self.max_cached:
            oldest = min(
                self._sessions.values(),
                key=lambda s: s.last_accessed_ts,
            )
            self.close_workspace(oldest.workspace_id)

        total_bytes = sum(
            s.estimated_size_bytes for s in self._sessions.values()
        )
        while total_bytes > self.max_cache_bytes and self._sessions:
            oldest = min(
                self._sessions.values(),
                key=lambda s: s.last_accessed_ts,
            )
            total_bytes -= oldest.estimated_size_bytes
            self.close_workspace(oldest.workspace_id)

    def _insert_session(self, session: WorkspaceSession) -> None:
        """Register a session, evicting LRU entries if needed."""
        self._sessions[session.workspace_id] = session
        self._path_index[session.path] = session.workspace_id
        if session.alias:
            self._alias_index[session.alias] = session.workspace_id
        self._evict_lru()

    # ---- Internal ----

    def _build_session(
        self,
        workspace_id: str,
        path: str,
        workspace: Any,
        source_kind: str = 'local_binary',
        loaded_from_viv: bool = False,
        created_from_binary: bool = False,
        original_path: Optional[str] = None,
    ) -> WorkspaceSession:
        metadata = self._metadata_for_workspace(workspace)
        from .filesystem import _suggest_alias

        # Determine binary/viv paths
        binary_path: Optional[str] = None
        viv_path: Optional[str] = None
        if source_kind == 'local_viv':
            viv_path = path
        elif source_kind == 'local_binary':
            binary_path = path

        return WorkspaceSession(
            workspace_id=workspace_id,
            path=path,
            workspace=workspace,
            metadata=metadata,
            selector_path=original_path or path,
            binary_path=binary_path,
            viv_path=viv_path,
            alias=_suggest_alias(path),
            source_kind=source_kind,
            loaded_from_viv=loaded_from_viv,
            created_from_binary=created_from_binary,
            estimated_size_bytes=_estimate_workspace_size(workspace),
        )

    def _metadata_for_workspace(self, workspace: Any) -> Dict[str, Any]:
        getter = getattr(workspace, 'getMeta', lambda name: None)
        return {
            'architecture': getter('Architecture'),
            'platform': getter('Platform'),
            'format': getter('Format'),
        }


# ---------------------------------------------------------------------------
# Size estimation helper
# ---------------------------------------------------------------------------


def _estimate_workspace_size(workspace: Any) -> int:
    """Best-effort workspace size estimation.

    Sums function count, segment sizes, and basic block count as a rough
    proxy for bytes in memory.  This is used ONLY for relative ordering in
    LRU eviction decisions — it does not need to be perfectly accurate.
    """
    total = 0
    # Functions
    try:
        total += len(workspace.getFunctions()) * 1024
    except Exception:
        pass
    # Segments
    try:
        for seg_name in workspace.getSegmentNames():
            seg = workspace.getSegment(seg_name)
            if seg is not None:
                total += getattr(seg, 'getSize', lambda: 0)()
    except Exception:
        pass
    # Basic blocks (coarse — 64 bytes each)
    try:
        total += len(workspace.getFunctions()) * 8 * 64
    except Exception:
        pass
    return total
