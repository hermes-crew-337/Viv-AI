from __future__ import annotations

from typing import Any, Dict


def render_analysis_result(result: Dict[str, Any]) -> str:
    lines = [f"Task: {result.get('task_type', 'unknown')}"]
    if result.get('error'):
        lines.append(f"Error: {result['error']}")
        return "\n".join(lines)

    provider = result.get('provider') or {}
    if provider:
        ptype = provider.get('type', 'unknown')
        model = provider.get('model', 'unknown')
        lines.append(f"Provider: {ptype}/{model}")

    lines.append(f"Cache: {'hit' if result.get('cache_hit') else 'miss'}")
    analysis = result.get('analysis') or {}
    if analysis.get('summary'):
        lines.append(f"Summary: {analysis['summary']}")
    if analysis.get('confidence'):
        lines.append(f"Confidence: {analysis['confidence']}")
    evidence = analysis.get('evidence') or []
    if evidence:
        lines.append('Evidence:')
        for item in evidence:
            lines.append(f"- {item}")
    return "\n".join(lines)
