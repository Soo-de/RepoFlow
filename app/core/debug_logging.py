# TEMPORARY: Remove this module when debug model logging is no longer needed.
# To remove: delete this file and remove the 3 import/call sites in pipeline.py.

import logging
from dataclasses import fields, asdict
from typing import Any

logger = logging.getLogger(__name__)

SENSITIVE_SUBSTRINGS = ("key", "token", "secret", "pat", "password", "credential")

MAX_STRING_LENGTH = 200


def _is_sensitive(field_name: str) -> bool:
    lower = field_name.lower()
    return any(s in lower for s in SENSITIVE_SUBSTRINGS)


def _truncate(value: str) -> str:
    if len(value) <= MAX_STRING_LENGTH:
        return value
    return value[:MAX_STRING_LENGTH] + f"... ({len(value)} chars total)"


def _format_value(key: str, value: Any) -> str:
    if _is_sensitive(key):
        return '"***REDACTED***"' if value else "None"

    if value is None:
        return "None"

    if isinstance(value, str):
        if not value:
            return '""'
        return f'"{_truncate(value)}"'

    if isinstance(value, list):
        if not value:
            return "[]"
        return repr(value)

    if isinstance(value, dict):
        if not value:
            return "{}"
        items = []
        for k, v in value.items():
            items.append(f"    {k}: {_format_value(k, v)}")
        return "{\n" + "\n".join(items) + "\n  }"

    return repr(value)


def _format_dataclass(obj: Any) -> dict[str, str]:
    """Convert a dataclass to an ordered dict of formatted field strings."""
    formatted = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if f.name.startswith("_"):
            continue
        formatted[f.name] = _format_value(f.name, value)
    return formatted


def log_model(label: str, obj: Any) -> None:
    """Log a dataclass or dict in a clean, readable format for debugging.

    Redacts sensitive fields, truncates long strings, and formats
    nested structures with indentation.
    """
    if not logger.isEnabledFor(logging.DEBUG):
        return

    try:
        if hasattr(obj, "__dataclass_fields__"):
            formatted = _format_dataclass(obj)
        elif isinstance(obj, dict):
            formatted = {k: _format_value(k, v) for k, v in obj.items()}
        else:
            logger.debug("[%s] %r", label, obj)
            return

        lines = [f"[{label}]"]
        for key, val in formatted.items():
            lines.append(f"  {key}: {val}")

        logger.debug("\n".join(lines))

    except Exception:
        logger.debug("[%s] (failed to format: %r)", label, type(obj).__name__)
