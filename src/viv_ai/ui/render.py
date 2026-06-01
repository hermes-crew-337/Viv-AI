"""
Rich HTML rendering for Viv-AI analysis results.

Phase R: replaces plain-text render_analysis_result with a structured HTML formatter
that supports provenance badges, confidence colors, evidence lists, and provider footers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


_CONFIDENCE_COLORS = {
    'high': '#2e7d32',
    'medium': '#e65100',
    'low': '#b71c1c',
}


def _escape_html(text: str) -> str:
    """Escape HTML special characters for safe embedding."""
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def _provenance_html(analysis: Dict[str, Any], cache_hit: bool) -> str:
    """Render a small provenance badge showing cache state, provider, model, and timestamp."""
    provider = analysis.get('provider', {})
    ptype = provider.get('type', 'unknown')
    model = provider.get('model', 'unknown')
    now = datetime.now().strftime('%H:%M:%S')

    if cache_hit:
        color = '#9e9e9e'
        label = 'CACHED'
        bg = '#f5f5f5'
    else:
        color = '#1565c0'
        label = 'FRESH'
        bg = '#e3f2fd'

    return (
        f'<span style="display:inline-block;background:{bg};color:{color};'
        f'border:1px solid {color};border-radius:4px;padding:2px 8px;'
        f'font-size:11px;font-family:monospace;white-space:nowrap;">'
        f'<strong>{label}</strong> — {_escape_html(ptype)}/{_escape_html(model)} — {now}'
        f'</span>'
    )


def _confidence_html(confidence: Optional[str]) -> str:
    """Render a colored confidence badge."""
    if not confidence:
        return ''
    color = _CONFIDENCE_COLORS.get(confidence.lower(), '#757575')
    return (
        f'<span style="display:inline-block;background:{color};color:#fff;'
        f'border-radius:3px;padding:1px 6px;font-size:11px;font-weight:bold;'
        f'font-family:monospace;">'
        f'{_escape_html(confidence.upper())}'
        f'</span>'
    )


def _evidence_html(evidence: list) -> str:
    """Render evidence as a styled bullet list."""
    if not evidence:
        return ''
    items = ''.join(
        f'<li style="margin:2px 0;font-size:13px;">{_escape_html(str(item))}</li>'
        for item in evidence
    )
    return f'<ul style="margin:4px 0 8px 16px;padding:0;">{items}</ul>'


def _provider_footer_html(provider: Dict[str, Any], cache_hit: bool) -> str:
    """Render a faint footer row with provider and model info."""
    ptype = provider.get('type', '?')
    model = provider.get('model', '?')
    source = 'cache' if cache_hit else 'live'
    return (
        f'<div style="margin-top:12px;padding-top:6px;border-top:1px solid #e0e0e0;'
        f'font-size:11px;color:#9e9e9e;font-family:monospace;">'
        f'{_escape_html(ptype)}/{_escape_html(model)} · {source}'
        f'</div>'
    )


def _error_html(result: Dict[str, Any]) -> str:
    """Render an error result."""
    error = _escape_html(result.get('error', 'unknown error'))
    task = _escape_html(result.get('task_type', 'unknown'))
    va = result.get('va', '')
    addr = f' at {va}' if va else ''
    return (
        f'<div style="background:#ffebee;border:1px solid #ef5350;border-radius:6px;padding:12px;font-family:sans-serif;">'
        f'<div style="font-weight:bold;color:#c62828;font-size:14px;">Error — {task}{addr}</div>'
        f'<pre style="font-size:13px;margin:8px 0 0 0;color:#b71c1c;white-space:pre-wrap;">{error}</pre>'
        f'</div>'
    )


def _status_html(result: Dict[str, Any]) -> str:
    """Render a provider status result."""
    status = result.get('status') or {}
    parts = [
        '<div style="font-family:sans-serif;">',
        '<div style="font-weight:bold;font-size:14px;margin-bottom:8px;">Provider Status</div>',
        f'<table style="font-size:13px;border-collapse:collapse;">',
    ]
    rows = [
        ('Provider', status.get('provider_name', '?')),
        ('Type', status.get('provider_type', '?')),
        ('Endpoint', status.get('endpoint', '?')),
        ('Configured Model', status.get('configured_model', '?')),
    ]
    for label, value in rows:
        parts.append(
            f'<tr><td style="padding:2px 12px 2px 0;color:#616161;font-weight:bold;">{label}</td>'
            f'<td style="padding:2px 0;font-family:monospace;">{_escape_html(str(value))}</td></tr>'
        )

    available = status.get('available_models') or []
    if available:
        parts.append(
            f'<tr><td style="padding:2px 12px 2px 0;color:#616161;font-weight:bold;vertical-align:top;">'
            f'Available Models</td>'
            f'<td style="padding:2px 0;font-family:monospace;">'
        )
        for m in available:
            parts.append(f'{_escape_html(str(m))}<br>')
        parts.append('</td></tr>')

    issues = status.get('issues') or []
    if issues:
        for issue in issues:
            field = issue.get('field', '?')
            msg = issue.get('message', '')
            hint = issue.get('hint', '')
            parts.append(
                f'<tr><td style="padding:2px 12px 2px 0;color:#c62828;">⚠ {_escape_html(field)}</td>'
                f'<td style="padding:2px 0;font-size:12px;">{_escape_html(msg)}'
            )
            if hint:
                parts.append(f'<br><span style="color:#757575;">hint: {_escape_html(hint)}</span>')
            parts.append('</td></tr>')

    parts.append('</table></div>')
    return '\n'.join(parts)


def render_analysis_result(result: Dict[str, Any]) -> str:
    """Render an analysis result as a rich HTML string.

    Args:
        result: The analysis result dict (same shape as before).

    Returns:
        HTML string suitable for display in a QTextEdit or similar widget.
    """
    # Error path
    if result.get('error'):
        return _error_html(result)

    # Status path (provider status, etc.)
    status = result.get('status')
    if status:
        return _status_html(result)

    # Normal analysis result path
    task = _escape_html(result.get('task_type', 'analysis'))
    analysis = result.get('analysis') or {}
    cache_hit = bool(result.get('cache_hit'))
    provider = result.get('provider') or {}

    summary = analysis.get('summary', '')
    confidence = analysis.get('confidence')
    evidence = analysis.get('evidence') or []

    # Build summary section
    summary_html = f'<div style="font-size:14px;font-weight:bold;margin-bottom:8px;">{_escape_html(summary)}</div>' if summary else ''

    # Confidence badge
    confidence_html_str = _confidence_html(confidence)

    # Evidence
    evidence_html_str = _evidence_html(evidence)

    # Provenance badge (R4)
    provenance = _provenance_html(analysis, cache_hit) if analysis else ''

    # Provider footer
    footer = _provider_footer_html(provider, cache_hit) if provider else ''

    # Task type header with scope info
    va_str = result.get('va', '')
    task_header = _escape_html(task)
    if va_str:
        task_header += f' — {_escape_html(va_str)}'

    return (
        '<div style="font-family:sans-serif;padding:8px;">'
        f'<div style="color:#757575;font-size:11px;font-family:monospace;margin-bottom:4px;">{task_header}</div>'
        f'{summary_html}'
        f'{confidence_html_str} {provenance}'
        f'{evidence_html_str}'
        f'{footer}'
        '</div>'
    )


def render_plain_text_fallback(result: Dict[str, Any]) -> str:
    """Produce a plain-text fallback for non-HTML contexts (CLI, tests, logs).

    Keeps the same format as the pre-Phase-R renderer for backward compatibility.
    """
    lines = [f"Task: {result.get('task_type', 'unknown')}"]
    if result.get('error'):
        lines.append(f"Error: {result['error']}")
        return '\n'.join(lines)

    status = result.get('status') or {}
    if status:
        lines.append(f"Provider name: {status.get('provider_name', 'unknown')}")
        lines.append(f"Provider type: {status.get('provider_type', 'unknown')}")
        if status.get('endpoint'):
            lines.append(f"Endpoint: {status['endpoint']}")
        if status.get('configured_model'):
            lines.append(f"Configured model: {status['configured_model']}")
        available_models = status.get('available_models') or []
        if available_models:
            lines.append('Available models:')
            for model in available_models:
                lines.append(f"- {model}")
        issues = status.get('issues') or []
        if issues:
            lines.append('Issues:')
            for issue in issues:
                field = issue.get('field', 'unknown')
                message = issue.get('message', 'unknown issue')
                lines.append(f"- {field}: {message}")
                if issue.get('hint'):
                    lines.append(f"  hint: {issue['hint']}")
        return '\n'.join(lines)

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
    return '\n'.join(lines)
