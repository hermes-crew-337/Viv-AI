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
