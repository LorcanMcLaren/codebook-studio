"""Python wrapper for the span_selector Streamlit component.

The component renders a span-selection surface (text plus highlights) in an
iframe and posts back ``{"kind": "add"|"remove", ...}`` events with a nonce so
each interaction triggers exactly one rerun-side action.
"""

from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent.parent / "components" / "span_selector"

_span_selector_component = components.declare_component(
    "cb_span_selector",
    path=str(_COMPONENT_DIR),
)


def span_selector(text, spans, hint=None, key=None):
    """Render the span-selector component.

    Args:
        text: The full document text. Span ``start``/``end`` are 0-indexed
            character offsets into this string.
        spans: List of dicts with keys ``annotation_key``, ``annotation_label``,
            ``start``, ``end``, ``color``, ``focused``, ``index``, and optional
            ``label``.
        hint: Optional caption shown above the document (e.g. "Selecting:
            Evidence").
        key: Streamlit component key.

    Returns:
        Either ``None`` (no interaction yet) or a dict shaped like
        ``{"kind": "add", "start": int, "end": int, "text": str, "nonce": float}``
        or ``{"kind": "remove", "annotation_key": str, "index": int,
        "nonce": float}``.
    """
    return _span_selector_component(
        text=text or "",
        spans=list(spans or []),
        hint=hint or "",
        key=key,
        default=None,
    )
