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
