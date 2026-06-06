"""Symbolik path summarization and extraction for Viv-AI.

Provides two layers:
1. ``get_symbolik_path_dicts`` — bridge from Vivisect's SymbolikAnalysisContext
   to a plain list of path dicts, with longest-path-first ordering and
   timeout-safe generator consumption.
2. ``summarize_symbolik_paths`` — bounded-formatting pass over path dicts.
"""

import time
import queue
import threading
from typing import Any, Dict, Iterable, List, Optional

_EXHAUSTED = object()
"""Sentinel pushed into the generator-consumer queue when the generator ends."""


def _consume_via_queue(gen, max_count, per_item_timeout, total_deadline):
    """Pull up to *max_count* items from *gen* via a daemon thread + queue.

    Per-item timeout prevents hanging on a single path.  Total-deadline
    prevents the whole operation from exceeding the wall-clock budget.

    When a timeout fires we set a ``stop_event`` so the background thread
    cooperatively quits at the next path boundary — same pattern as
    ``vivisect.tools.graphutil.PathGenerator.__go__`` / ``stop()``.

    Returns a list of (index, item) tuples, where *index* is the original
    0-based position in the generator sequence.
    """
    q = queue.Queue()
    stop_event = threading.Event()
    t = threading.Thread(
        target=_gen_to_queue,
        args=(gen, q, stop_event),
        daemon=True,
    )
    t.start()

    items = []
    for idx in range(max_count):
        if time.time() > total_deadline:
            stop_event.set()
            break

        try:
            payload = q.get(timeout=per_item_timeout)
        except queue.Empty:
            stop_event.set()  # tell the worker: don't start the next path
            break

        if payload is _EXHAUSTED:
            break

        items.append((idx, payload))

    # Any early exit — tell the thread to stop so it doesn't keep running Z3
    # on paths nobody will read.  Setting after a normal exhaustion is a
    # harmless no-op (thread already returned from its ``for`` loop).
    stop_event.set()
    return items


def _gen_to_queue(gen, q, stop_event):
    """Thread target: drain *gen* into *q*, signalling exhaustion.

    Checks ``stop_event`` between each item so a management thread can
    request cooperative shutdown — same pattern as
    ``vivisect.tools.graphutil.PathGenerator.__go__``.
    """
    try:
        for item in gen:
            if stop_event.is_set():
                break
            q.put(item)
    finally:
        q.put(_EXHAUSTED)


def _extract_path_dict(path_idx, emu, effects, efftype_constrain):
    """Convert a single (emu, effects) tuple from Vivisect into a dict."""
    constraints = []
    effect_strs = []

    for eff in effects:
        try:
            eff.reduce(emu)
        except Exception:  # noqa: BLE001
            pass

        if getattr(eff, 'efftype', None) == efftype_constrain:
            try:
                constraints.append(str(eff))
            except Exception:  # noqa: BLE001
                constraints.append('<constraint>')

        try:
            effect_strs.append(str(eff))
        except Exception:  # noqa: BLE001
            effect_strs.append(f'<{type(eff).__name__}>')

    return_relation = ''
    if hasattr(emu, 'getFunctionReturn'):
        try:
            return_relation = str(emu.getFunctionReturn().reduce())
        except Exception:  # noqa: BLE001
            return_relation = '<return>'

    return {
        'path_id': f'p{path_idx}',
        'constraints': constraints,
        'effects': effect_strs,
        'return_relation': return_relation,
    }


def get_symbolik_path_dicts(
    workspace: Any,
    fva: int,
    max_paths: int = 100,
    per_path_timeout: float = 30.0,
    total_timeout: float = 120.0,
) -> list[dict[str, Any]]:
    """Collect symbolik path data from Vivisect for a function.

    Uses Vivisect's SymbolikAnalysisContext (available in both
    pip ``vivisect==1.3.2`` and the upstream fork) to trace symbolik
    execution paths through the function at *fva*.

    Path ordering
    -------------
    Uses ``vivisect.tools.graphutil.getLongPath()`` to yield paths
    longest-first (most complex / most interesting first).  Combined
    with lazy generation this means the first N yielded paths are the
    N longest paths through the function.

    Timeout safety
    --------------
    A single path's symbolic execution can take arbitrarily long
    (deep loops, complex constraints).  We consume the generator via
    a daemon thread + queue with a per-item timeout and a total
    wall-clock deadline so callers always get *some* result.

    Parameters
    ----------
    workspace : VivWorkspace
        The opened Vivisect workspace.
    fva : int
        Function VA to analyse.
    max_paths : int
        Maximum number of paths to consume (default 100).
    per_path_timeout : float
        Seconds to wait for a single path (default 30).
    total_timeout : float
        Total wall-clock timeout for the whole operation (default 120).

    Returns
    -------
    list[dict]
        Path dicts compatible with :func:`summarize_symbolik_paths`.

    Raises
    ------
    RuntimeError
        If the Vivisect symboliks module is not available.
    """
    try:
        from vivisect.symboliks.analysis import (
            getSymbolikAnalysisContext,
            EFFTYPE_CONSTRAIN,
        )
        from vivisect.tools import graphutil as viv_graph
    except ImportError:
        raise RuntimeError(
            'symbolik path provider is unavailable '
            '(vivisect.symboliks or vivisect.tools not installed)'
        )

    symctx = getSymbolikAnalysisContext(workspace)

    # Build symbolik graph once (expensive, but needed for getLongPath).
    sg = symctx.getSymbolikGraph(fva)

    # Path iterator prioritised by length — longest paths first.
    path_iter = symctx.getSymbolikPaths(
        fva,
        paths=viv_graph.getLongPath(sg),
        graph=sg,
    )

    deadline = time.time() + total_timeout

    consumed = _consume_via_queue(
        path_iter,
        max_count=max_paths,
        per_item_timeout=per_path_timeout,
        total_deadline=deadline,
    )

    return [
        _extract_path_dict(idx, emu, effects, EFFTYPE_CONSTRAIN)
        for idx, (emu, effects) in consumed
    ]


def summarize_symbolik_paths(
    paths: Iterable[Dict[str, Any]],
    max_paths: int = 8,
    max_constraints: int = 8,
    max_effects: int = 8,
) -> Dict[str, Any]:
    """Produce a bounded summary dict from a list of raw path dicts.

    Parameters
    ----------
    paths : iterable of dict
        Path dicts (as produced by :func:`get_symbolik_path_dicts`).
    max_paths : int
        Max paths to include in the summary.
    max_constraints : int
        Max constraints to show per path.
    max_effects : int
        Max effects to show per path.

    Returns
    -------
    dict
        ``{'paths': [...], 'path_count': N, 'truncated': {...}}``
    """
    path_list = list(paths)
    summary_paths = []
    for path in path_list[:max_paths]:
        constraints = list(path.get('constraints', ()))
        effects = list(path.get('effects', ()))
        summary_paths.append({
            'path_id': path.get('path_id'),
            'constraints': constraints[:max_constraints],
            'effects': effects[:max_effects],
            'return_relation': path.get('return_relation'),
            'truncated': {
                'constraints': max(0, len(constraints) - min(len(constraints), max_constraints)),
                'effects': max(0, len(effects) - min(len(effects), max_effects)),
            },
        })
    return {
        'paths': summary_paths,
        'path_count': len(path_list),
        'truncated': {
            'paths': max(0, len(path_list) - min(len(path_list), max_paths)),
        },
    }
