from __future__ import annotations

import os

from typing import Any, Dict, Iterable, List, Tuple, Optional

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
    
    This function reads the following configuration sources in order of precedence:
    1. Object attributes (analysis_max_* if config is not None)
    2. Default hard-coded fallbacks
    
    For Phase T validation: see validate_analysis_limits() for schema checking.
    """
    DEFAULTS = {
        'max_nodes': 32,
        'max_edges': 64,
        'max_paths': 8,
        'max_constraints': 8,
        'max_effects': 8,
        'max_callers': 16,
        'max_callees': 16,
        'max_string_refs': 16,
        'max_import_refs': 16,
        'max_disassembly_items': 32,
        'max_functions': 64,
        'max_results': 32,
    }
    
    if config is None:
        return dict(DEFAULTS)
    
    result = {}
    for key, def_val in DEFAULTS.items():
        attr_name = key.replace('max_', 'analysis_max_')
        val = getattr(config, attr_name, def_val)
        # Clamp to int >= 0
        try:
            val = max(0, int(val)) if val is not None else def_val
        except (TypeError, ValueError):
            val = def_val
        result[key] = val
    
    return result


def validate_analysis_limits(config: Optional[Any] = None) -> Dict[str, Any]:
    """Validate analysis limits configuration and return normalized dict.
    
    Raises ValueError if any limit is invalid (non-integer or negative).
    Returns a normalized dict of all limits with values clamped to int >= 0.
    
    For Phase T: This function validates schema before limits are used anywhere,
    ensuring early failure with clear error messages.
    """
    ERROR_SUFFIX = " — use analysis_max_<key>=<int>= 0 in config"
    errors = []
    
    DEFAULTS = {
        'max_nodes': ('analysis_max_nodes', 32),
        'max_edges': ('analysis_max_edges', 64),
        'max_paths': ('analysis_max_paths', 8),
        'max_constraints': ('analysis_max_constraints', 8),
        'max_effects': ('analysis_max_effects', 8),
        'max_callers': ('analysis_max_callers', 16),
        'max_callees': ('analysis_max_callees', 16),
        'max_string_refs': ('analysis_max_string_refs', 16),
        'max_import_refs': ('analysis_max_import_refs', 16),
        'max_disassembly_items': ('analysis_max_disassembly_items', 32),
        'max_functions': ('analysis_max_functions', 64),
        'max_results': ('analysis_max_results', 32),
    }
    
    result = {}
    for key, (attr_name, def_val) in DEFAULTS.items():
        if config is not None:
            val = getattr(config, attr_name, def_val)
            if val is not None:
                try:
                    int_val = int(val)
                    if int_val < 0:
                        errors.append(f"{key}: {int_val} (negative value{ERROR_SUFFIX})")
                        continue
                    result[key] = int_val
                except (TypeError, ValueError):
                    errors.append(f"{key}: '{val}' (not an integer{ERROR_SUFFIX})")
                    continue
        
        if key not in result:
            result[key] = def_val
    
    if errors:
        raise ValueError("Invalid analysis limits:\n  - " + "\n  - ".join(errors))
    
    return result


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


def collect_dangerous_sinks(vw: Any) -> List[Dict[str, Any]]:
    """Collect all known dangerous function imports (sinks) for bug hunting."""
    dangerous = {
        "system", "popen", "execve", "execl", "execle", "execlp", "execv", "execvp",
        "memcpy", "memmove", "strcpy", "strncpy", "strcat", "strncat",
        "sprintf", "vsprintf", "gets", "printf", "fprintf", "dprintf", "snprintf", "vprintf", "vfprintf",
        "unserialize", "mmap",
    }
    items = []
    for lva, lsize, _ltype, tinfo in list(vw.getImports()):
        raw_sym = str(tinfo)
        # Strip Vivisect prefix (e.g., "*.system" -> "system")
        clean_sym = raw_sym.replace("*.", "").replace("*_", "").rstrip() if raw_sym.startswith("*") else raw_sym
        if clean_sym in dangerous:
            items.append({
                'va': hexva(lva),
                'symbol': str(tinfo),
                'clean_symbol': clean_sym,
                'category': _get_sink_category(clean_sym),
            })
    items.sort(key=lambda item: item['va'])
    return items


def collect_attacker_sources(vw: Any) -> List[Dict[str, Any]]:
    """Collect known attacker-accessible input points."""
    sources = {
        "argv", "environ", "read", "recv", "fgets", "gets", "mmap", "loadFileRaw",
    }
    items = []
    for lva, lsize, _ltype, tinfo in list(vw.getImports()):
        raw_sym = str(tinfo)
        clean_sym = raw_sym.replace("*.", "").replace("*_", "").rstrip() if raw_sym.startswith("*") else raw_sym
        if clean_sym in sources:
            items.append({
                'va': hexva(lva),
                'symbol': str(tinfo),
                'clean_symbol': clean_sym,
                'category': _get_source_category(clean_sym),
            })
    items.sort(key=lambda item: item['va'])
    return items


def _get_sink_category(symbol: str) -> str:
    """Classify a sink function."""
    cmd_inject = {"system", "popen", "execve", "execl", "execle", "execlp", "execv", "execvp"}
    mem_corrupt = {"memcpy", "memmove", "strcpy", "strncpy", "strcat", "strncat", "sprintf", "vsprintf", "gets"}
    format_str = {"printf", "fprintf", "dprintf", "snprintf", "vprintf", "vfprintf"}
    if symbol in cmd_inject:
        return "command_injection"
    if symbol in mem_corrupt:
        return "buffer_overflow"
    if symbol in format_str:
        return "format_string"
    if symbol == "unserialize":
        return "unsafe_deserialization"
    if symbol == "mmap":
        return "memory_mapped_input"
    return "unknown_sink"


def _get_source_category(symbol: str) -> str:
    """Classify an attacker source function."""
    cmd_source = {"argv", "environ"}
    file_source = {"read", "fgets", "gets", "loadFileRaw"}
    net_source = {"recv"}
    mem_source = {"mmap"}
    if symbol in cmd_source:
        return "command_line"
    if symbol in file_source:
        return "file_input"
    if symbol in net_source:
        return "network"
    if symbol in mem_source:
        return "memory_mapped"
    return "unknown_source"


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
