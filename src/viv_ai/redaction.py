import re
from typing import Any

_SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r'password\s*=',
        r'password',
        r'secret',
        r'token',
        r'api[_-]?key',
        r'authorization:',
        r'bearer\s+',
    )
]


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, val in value.items():
            if isinstance(key, str) and any(pattern.search(key) for pattern in _SECRET_PATTERNS):
                redacted[key] = '<redacted:secret>'
            else:
                redacted[key] = redact_value(val)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in _SECRET_PATTERNS):
            return '<redacted:secret>'
    return value
