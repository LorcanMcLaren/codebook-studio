"""Parse and serialize span-annotation values stored in CSV cells.

Spans are written into the CSV column as a JSON-encoded list of
``{"start": int, "end": int, "text": str, "label"?: str}`` objects. Empty
lists are stored as the empty string so downstream "answered?" checks treat
them as unanswered.
"""

import json

try:
    import pandas as pd  # only used for NaN detection
except ImportError:  # pragma: no cover - pandas is a hard dependency in the app
    pd = None


def parse_span_value(value):
    """Parse a stored span annotation value into a list of span dicts."""
    if value is None:
        return []
    if isinstance(value, list):
        return [dict(span) for span in value if isinstance(span, dict)]
    if pd is not None:
        try:
            if pd.isna(value):
                return []
        except (TypeError, ValueError):
            pass
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return []
        if isinstance(parsed, list):
            return [dict(span) for span in parsed if isinstance(span, dict)]
    return []


def serialize_span_value(spans):
    """Serialize a list of span dicts to a JSON string for CSV storage."""
    if not spans:
        return ""
    cleaned = []
    for span in spans:
        if not isinstance(span, dict):
            continue
        entry = {
            "start": int(span.get("start", 0)),
            "end": int(span.get("end", 0)),
        }
        if "text" in span and span["text"] is not None:
            entry["text"] = str(span["text"])
        if span.get("label"):
            entry["label"] = str(span["label"])
        cleaned.append(entry)
    if not cleaned:
        return ""
    return json.dumps(cleaned, ensure_ascii=False)
