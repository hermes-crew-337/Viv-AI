from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from ..extractors import LOC_STRING, LOC_UNI


def hexva(value: Any) -> str:
    ivalue = int(value, 0) if isinstance(value, str) else int(value)
    return f"0x{ivalue:08x}"


def parse_va(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def bounded(items: Iterable[Dict[str, Any]], max_results: int) -> Tuple[List[Dict[str, Any]], int]:
    seq = list(items)
    limit = max(1, int(max_results))
    if len(seq) <= limit:
        return seq, 0
    return seq[:limit], len(seq) - limit


def paginated(items: Iterable[Dict[str, Any]], offset: int, limit: int) -> Tuple[List[Dict[str, Any]], bool]:
    """Slice items with offset/limit pagination.

    Args:
        items: Iterable of items to paginate.
        offset: Number of items to skip (0-indexed).
        limit: Maximum number of items to return (clamped to >= 1).

    Returns:
        Tuple of (page slice, has_more) where has_more is True if more items exist
        after the current page.
    """
    seq = list(items)
    lo = max(0, int(offset))
    hi = lo + max(1, int(limit))
    page = seq[lo:hi]
    has_more = hi < len(seq)
    return page, has_more


def pagination_meta(total: int, offset: int, limit: int, has_more: bool) -> Dict[str, Any]:
    """Build a standard pagination metadata dict.

    Always reports the *effective* offset and limit — negative offsets are
    clamped to zero, zero/negative limits are clamped to one — so clients
    never see misleading raw-input values.

    Includes total count, current offset/limit, whether more results exist,
    and computed next_offset for convenience.
    """
    clamped_offset = max(0, int(offset))
    clamped_limit = max(1, int(limit))
    return {
        'total': total,
        'offset': clamped_offset,
        'limit': clamped_limit,
        'has_more': has_more,
        'next_offset': clamped_offset + clamped_limit if has_more else None,
    }


def analysis_limits_from_config(config: Any) -> Dict[str, int]:
    """Extract bounded-output limits from an AiConfig or compatible object.

    Returns a dict with keys for each bounded parameter, defaulting to safe values.
    If config is None, returns all defaults.
    """
    return {
        'max_nodes': getattr(config, 'analysis_max_nodes', 32) if config else 32,
        'max_edges': getattr(config, 'analysis_max_edges', 64) if config else 64,
        'max_paths': getattr(config, 'analysis_max_paths', 8) if config else 8,
        'max_constraints': getattr(config, 'analysis_max_constraints', 8) if config else 8,
        'max_effects': getattr(config, 'analysis_max_effects', 8) if config else 8,
        'max_callers': getattr(config, 'analysis_max_callers', 16) if config else 16,
        'max_callees': getattr(config, 'analysis_max_callees', 16) if config else 16,
        'max_string_refs': getattr(config, 'analysis_max_string_refs', 16) if config else 16,
        'max_import_refs': getattr(config, 'analysis_max_import_refs', 16) if config else 16,
        'max_disassembly_items': getattr(config, 'analysis_max_disassembly_items', 32) if config else 32,
        'max_functions': getattr(config, 'analysis_max_functions', 64) if config else 64,
        'max_results': getattr(config, 'analysis_max_results', 32) if config else 32,
    }


def collect_strings(vw: Any) -> List[Dict[str, Any]]:
    results = []
    for ltype in (LOC_STRING, LOC_UNI):
        for lva, lsize, _lt, _info in list(vw.getLocations(ltype)):
            loc = (lva, lsize, ltype, _info)
            value = getattr(vw, 'reprLocation', lambda x: x[3])(loc)
            results.append({'va': hexva(lva), 'size': int(lsize), 'value': value})
    results.sort(key=lambda item: item['va'])
    return results


def collect_imports(vw: Any) -> List[Dict[str, Any]]:
    items = [
        {'va': hexva(lva), 'size': int(lsize), 'symbol': str(tinfo)}
        for lva, lsize, _ltype, tinfo in list(vw.getImports())
    ]
    items.sort(key=lambda item: item['va'])
    return items


def collect_exports(vw: Any) -> List[Dict[str, Any]]:
    items = [
        {'va': hexva(va), 'type': str(etype), 'name': str(name), 'file': str(filename)}
        for va, etype, name, filename in list(vw.getExports())
    ]
    items.sort(key=lambda item: item['va'])
    return items


def collect_names(vw: Any) -> List[Dict[str, Any]]:
    getter = getattr(vw, 'getNames', None)
    if getter is None:
        return []
    items = [{'va': hexva(va), 'name': str(name)} for va, name in list(getter())]
    items.sort(key=lambda item: item['va'])
    return items


def collect_xrefs(vw: Any, va: int, direction: str) -> List[Dict[str, Any]]:
    if direction == 'to':
        refs = list(vw.getXrefsTo(va))
        items = [{'from_va': hexva(xrfrom), 'to_va': hexva(xrto), 'type': int(rtype), 'flags': int(rflags)} for xrfrom, xrto, rtype, rflags in refs]
    else:
        refs = list(vw.getXrefsFrom(va))
        items = [{'from_va': hexva(xrfrom), 'to_va': hexva(xrto), 'type': int(rtype), 'flags': int(rflags)} for xrfrom, xrto, rtype, rflags in refs]
    items.sort(key=lambda item: (item['from_va'], item['to_va']))
    return items
