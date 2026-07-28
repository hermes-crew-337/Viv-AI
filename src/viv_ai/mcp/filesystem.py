"""Filesystem access policy and workspace catalog primitives for Viv-AI MCP.

Defines:
- :class:`FilesystemPolicy` — what paths are visible and valid
- Catalog functions: discover_files, find_candidate_workspace_files, get_file_info
"""

from __future__ import annotations

import fnmatch
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_VIV_SUFFIXES = frozenset({'.viv'})


@dataclass
class FilesystemPolicy:
    """Controls what filesystem paths the MCP server can access.

    Attributes:
        base_dir: Root directory for local file discovery and path validation.
        allow_root: If True, ``base_dir`` may be ``/`` (full filesystem access).
        server_mode: If True, server-oriented defaults apply (e.g. broader root).
    """

    base_dir: Optional[str] = None
    allow_root: bool = False
    server_mode: bool = False

    def __post_init__(self):
        if self.base_dir is not None:
            self._base_resolved = os.path.realpath(self.base_dir)
        else:
            self._base_resolved = None  # unrestricted when no explicit base_dir

    @property
    def effective_base(self) -> Optional[str]:
        return self._base_resolved

    def __repr__(self) -> str:
        return (
            f'FilesystemPolicy(base_dir={self.base_dir!r}, '
            f'allow_root={self.allow_root}, server_mode={self.server_mode})'
        )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def normalize_path(raw: str, policy: FilesystemPolicy) -> str:
    """Resolve *raw* to an absolute path and check it's under policy bounds.

    Raises :class:`ValueError` if the path escapes the allowed base.
    Returns the real (canonical) absolute path.
    """
    expanded = os.path.expanduser(raw)
    if not os.path.isabs(expanded):
        if policy.effective_base is not None:
            expanded = os.path.join(policy.effective_base, expanded)
        else:
            expanded = os.path.realpath(expanded)

    resolved = os.path.realpath(expanded)
    base = policy.effective_base

    # If no base_dir was set, all paths are allowed (unrestricted mode).
    if base is None:
        # Root-level access still requires explicit opt-in.
        if resolved == '/' and not policy.allow_root:
            raise ValueError(
                'Root filesystem access not allowed — use --allow-root to enable'
            )
        return resolved

    # Explicit base_dir was set — enforce path boundary.
    if not policy.server_mode and not resolved.startswith(base + '/'):
        if resolved != base:
            raise ValueError(
                f'Path {resolved} escapes allowed base {base}'
            )

    return resolved


def is_allowed_path(path: str, policy: FilesystemPolicy) -> bool:
    """Return True if *path* (unanchored) is valid under *policy*."""
    try:
        normalize_path(path, policy)
        return True
    except (ValueError, OSError):
        return False


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def discover_files(
    root: str,
    policy: FilesystemPolicy,
    limit: int = 100,
    offset: int = 0,
    suffixes: Optional[Tuple[str, ...]] = None,
    glob_pattern: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Recursive, bounded file listing under *root* (must be inside *policy*).

    Returns a list of dicts with keys: path, type (file/dir), size_bytes,
    is_viv, has_sibling_viv, suffix.
    Results are sorted by (dirs first, then alphabetically) and paginated.

    When *glob_pattern* is provided (e.g. ``*.bin``, ``**/*.exe``), it's matched
    against the filename portion using :func:`fnmatch.fnmatch`.  *suffixes* and
    *glob_pattern* are combined with AND logic.
    """
    resolved_root = normalize_path(root, policy)
    results: List[Dict[str, Any]] = []
    seen: int = 0
    skipped: int = offset

    def _walk(current_dir: str) -> None:
        nonlocal seen, skipped
        if len(results) >= limit:
            return
        try:
            entries = sorted(os.scandir(current_dir), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        for entry in entries:
            if len(results) >= limit:
                break

            # Build candidate dict
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False) and not entry.name.startswith('.')
            except OSError:
                continue

            if not is_dir and not is_file:
                continue

            if is_dir:
                # Recurse into subdirectories
                _walk(entry.path)
                continue

            # It's a regular file
            suffix = Path(entry.name).suffix.lower()
            if suffixes and suffix not in suffixes:
                continue
            if glob_pattern and not fnmatch.fnmatch(entry.name, glob_pattern):
                continue

            # Check .viv status
            is_viv = suffix in _VIV_SUFFIXES
            has_sibling = _has_sibling_viv(entry.path) if not is_viv else False

            if skipped > 0:
                skipped -= 1
                continue

            info = {
                'path': entry.path,
                'type': 'file',
                'size_bytes': entry.stat().st_size if hasattr(entry, 'stat') else 0,
                'is_viv': is_viv,
                'has_sibling_viv': has_sibling,
                'suffix': suffix,
            }
            results.append(info)
            seen += 1

    _walk(resolved_root)
    return results


def find_candidate_workspace_files(
    path: str,
    policy: FilesystemPolicy,
) -> Tuple[Optional[str], Optional[str]]:
    """For a given *path*, return ``(viv_path, binary_path)`` that exist.

    - If *path* is a ``.viv``, ``viv_path`` is the path itself.
    - If *path* is a binary, look for ``path.viv`` and ``path + '.viv'``
      in the same directory.
    Returns ``(None, None)`` if neither exists.
    """
    resolved = normalize_path(path, policy)
    p = Path(resolved)

    viv_path: Optional[str] = None
    binary_path: Optional[str] = None

    if p.suffix.lower() in _VIV_SUFFIXES:
        if p.exists():
            viv_path = str(p)
    else:
        if p.exists():
            binary_path = str(p)
        # Check for sibling .viv
        sibling_viv = p.with_suffix(p.suffix + '.viv')
        if sibling_viv.exists():
            viv_path = str(sibling_viv)
        elif p.with_suffix('.viv').exists():
            viv_path = str(p.with_suffix('.viv'))

    return viv_path, binary_path


def get_file_info(path: str, policy: FilesystemPolicy) -> Dict[str, Any]:
    """Stat-like metadata for a single path.

    Returns a dict with keys: path, exists, type, size_bytes, mtime,
    is_viv, has_sibling_viv, alias.
    """
    resolved = normalize_path(path, policy)
    try:
        st = os.stat(resolved)
    except FileNotFoundError:
        return {'path': resolved, 'exists': False}

    p = Path(resolved)
    is_viv = p.suffix.lower() in _VIV_SUFFIXES
    alias = _suggest_alias(resolved)

    return {
        'path': resolved,
        'exists': True,
        'type': 'dir' if stat.S_ISDIR(st.st_mode) else 'file',
        'size_bytes': st.st_size,
        'mtime': st.st_mtime,
        'is_viv': is_viv,
        'has_sibling_viv': _has_sibling_viv(resolved) if not is_viv else False,
        'alias': alias,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _has_sibling_viv(file_path: str) -> bool:
    """Check if a sibling ``.viv`` file exists next to *file_path*."""
    p = Path(file_path)
    # Try <name><ext>.viv first, then <name>.viv
    candidate1 = p.with_suffix(p.suffix + '.viv')
    candidate2 = p.with_suffix('.viv')
    return candidate1.exists() or candidate2.exists()


def _suggest_alias(path: str) -> str:
    """Derive a short stable alias from *path*."""
    p = Path(path)
    stem = p.stem if p.suffix else p.name
    # Strip double extensions like .bin.viv
    if stem.endswith('.viv'):
        stem = stem[:-4]
    return stem
