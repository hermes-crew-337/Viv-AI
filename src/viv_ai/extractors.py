import fnmatch
import json
from typing import Any, Dict, Iterable, List, Sequence

try:
    import vivisect  # type: ignore
except ImportError:  # pragma: no cover
    vivisect = None

from .graphs import summarize_graph


LOC_IMPORT = getattr(vivisect, 'LOC_IMPORT', 9)
LOC_STRING = getattr(vivisect, 'LOC_STRING', 2)
LOC_UNI = getattr(vivisect, 'LOC_UNI', 3)
REF_CODE = getattr(vivisect, 'REF_CODE', 1)


def _hex(va: int) -> str:
    return f'0x{va:08x}'


def _truncate(items: Sequence[Any], limit: int) -> tuple[list[Any], int]:
    trimmed = list(items[:limit])
    return trimmed, max(0, len(items) - len(trimmed))


def _safe_get_name(vw: Any, va: int) -> str:
    name = getattr(vw, 'getName', lambda _va: None)(va)
    return name or _hex(va)


def _is_function(vw: Any, va: int) -> bool:
    checker = getattr(vw, 'isFunction', None)
    if checker is not None:
        try:
            return bool(checker(va))
        except Exception:
            pass
    try:
        return va in set(vw.getFunctions())
    except Exception:
        return False


def _safe_repr_location(vw: Any, loc: Sequence[Any]) -> str:
    try:
        return vw.reprLocation(loc)
    except Exception:
        return str(loc[3])


def _collect_function_stats(vw: Any, fva: int) -> Dict[str, Any]:
    blocks = list(vw.getFunctionBlocks(fva))
    size = sum(int(block[1]) for block in blocks)
    caller_count = len(list(getattr(vw, 'getCallers', lambda _va: [])(fva)))
    return {
        'va': _hex(fva),
        'name': _safe_get_name(vw, fva),
        'size': size,
        'block_count': len(blocks),
        'caller_count': caller_count,
    }


def extract_binary_overview(vw: Any, max_entry_points: int = 8, max_imports: int = 32, max_exports: int = 32, max_strings: int = 32, max_top_functions: int = 16) -> Dict[str, Any]:
    entry_points = [_hex(va) for va in list(vw.getEntryPoints())]
    imports = [
        {'va': _hex(lva), 'size': int(lsize), 'symbol': str(tinfo)}
        for lva, lsize, _ltype, tinfo in list(vw.getImports())
    ]
    exports = [
        {'va': _hex(va), 'type': str(etype), 'name': str(name), 'file': str(filename)}
        for va, etype, name, filename in list(vw.getExports())
    ]
    strings = [
        {'va': _hex(lva), 'size': int(lsize), 'value': _safe_repr_location(vw, (lva, lsize, ltype, tinfo))}
        for lva, lsize, ltype, tinfo in list(vw.getLocations(LOC_STRING))
    ]

    top_functions = [_collect_function_stats(vw, fva) for fva in list(vw.getFunctions())]
    top_functions.sort(key=lambda item: (-item['caller_count'], -item['block_count'], item['va']))

    entry_points, ep_trunc = _truncate(entry_points, max_entry_points)
    imports, imp_trunc = _truncate(imports, max_imports)
    exports, exp_trunc = _truncate(exports, max_exports)
    strings, str_trunc = _truncate(strings, max_strings)
    top_functions, top_trunc = _truncate(top_functions, max_top_functions)

    return {
        'metadata': {
            'architecture': vw.getMeta('Architecture'),
            'platform': vw.getMeta('Platform'),
            'format': vw.getMeta('Format'),
        },
        'entry_points': entry_points,
        'imports': imports,
        'exports': exports,
        'strings': strings,
        'top_functions': top_functions,
        'truncated': {
            'entry_points': ep_trunc,
            'imports': imp_trunc,
            'exports': exp_trunc,
            'strings': str_trunc,
            'top_functions': top_trunc,
        },
    }


def extract_function_overview(vw: Any, fva: int, max_callers: int = 16, max_callees: int = 16, max_string_refs: int = 16, max_import_refs: int = 16, max_disassembly_items: int = 32) -> Dict[str, Any]:
    blocks = list(vw.getFunctionBlocks(fva))
    callers = [_hex(va) for va in list(getattr(vw, 'getCallers', lambda _va: [])(fva))]
    callees: list[str] = []
    import_refs: list[dict[str, Any]] = []
    string_refs: list[dict[str, Any]] = []
    disassembly_slice: list[dict[str, Any]] = []

    seen_callees = set()
    seen_imports = set()
    seen_strings = set()

    for cbva, cbsize, _funcva in blocks:
        cur = cbva
        cbend = cbva + cbsize
        while cur < cbend:
            loc = vw.getLocation(cur)
            if loc is None:
                break
            lva, lsize, _ltype, _linfo = loc
            disassembly_slice.append({'va': _hex(lva), 'text': vw.reprVa(lva)})
            for xrfrom, xrto, rtype, rflags in list(vw.getXrefsFrom(lva)):
                if rtype == REF_CODE and _is_function(vw, xrto) and xrto not in seen_callees:
                    seen_callees.add(xrto)
                    callees.append(_hex(xrto))
                xloc = vw.getLocation(xrto)
                if xloc is None:
                    continue
                xlva, xlsize, xltype, xtinfo = xloc
                if xltype == LOC_IMPORT and xrto not in seen_imports:
                    seen_imports.add(xrto)
                    import_refs.append({'from_va': _hex(xrfrom), 'target_va': _hex(xlva), 'symbol': str(xtinfo)})
                if xltype in (LOC_STRING, LOC_UNI) and xrto not in seen_strings:
                    seen_strings.add(xrto)
                    string_refs.append({'from_va': _hex(xrfrom), 'target_va': _hex(xlva), 'value': _safe_repr_location(vw, xloc)})
            cur += max(1, int(lsize))

    callers, callers_trunc = _truncate(callers, max_callers)
    callees, callees_trunc = _truncate(callees, max_callees)
    string_refs, string_trunc = _truncate(string_refs, max_string_refs)
    import_refs, import_trunc = _truncate(import_refs, max_import_refs)
    disassembly_slice, disasm_trunc = _truncate(disassembly_slice, max_disassembly_items)

    graph_summary = summarize_graph(vw.getFunctionGraph(fva))
    return {
        'function': {
            'va': _hex(fva),
            'name': _safe_get_name(vw, fva),
            'size': sum(int(block[1]) for block in blocks),
            'block_count': len(blocks),
            'api': _normalize_api(getattr(vw, 'getFunctionApi', lambda _fva: None)(fva)),
        },
        'callers': callers,
        'callees': callees,
        'import_refs': import_refs,
        'string_refs': string_refs,
        'graph_summary': graph_summary,
        'disassembly_slice': disassembly_slice,
        'truncated': {
            'callers': callers_trunc,
            'callees': callees_trunc,
            'string_refs': string_trunc,
            'import_refs': import_trunc,
            'disassembly_slice': disasm_trunc,
        },
    }


def _normalize_api(api: Any) -> Dict[str, Any] | None:
    if not api:
        return None
    rettype, retname, callconv, funcname, callargs = api
    return {
        'return_type': rettype,
        'return_name': retname,
        'calling_convention': callconv,
        'name': funcname,
        'arguments': [{'type': argtype, 'name': argname} for argtype, argname in list(callargs)],
    }


def find_functions(vw: Any, name_glob: str | None = None, min_callers: int = 0, max_results: int = 32) -> List[Dict[str, Any]]:
    matches = []
    for fva in list(vw.getFunctions()):
        name = _safe_get_name(vw, fva)
        if name_glob and not fnmatch.fnmatch(name, name_glob):
            continue
        stats = _collect_function_stats(vw, fva)
        if min_callers > 0 and stats['caller_count'] < min_callers:
            continue
        matches.append(stats)
        if len(matches) >= max_results:
            break
    return matches
