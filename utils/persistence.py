import json
import hashlib
from io import StringIO
from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from streamlit_js_eval import streamlit_js_eval

STORAGE_KEY = "codebook_studio_save"
SAVE_VERSION = 1
MAX_SAVE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB warning threshold


def load_state_if_available():
    """Check localStorage availability and load save in one JS call.

    Returns None if JS hasn't executed yet (first render).
    Returns {'_available': bool, 'data': dict|{}} after JS executes.
    """
    raw = streamlit_js_eval(
        js_expressions=f"""
        (function() {{
            try {{
                localStorage.setItem('__test__', '1');
                localStorage.removeItem('__test__');
            }} catch (e) {{
                return JSON.stringify({{_available: false, data: null}});
            }}
            var saved = localStorage.getItem('{STORAGE_KEY}');
            return JSON.stringify({{_available: true, data: saved}});
        }})()
        """,
        key="__load_state_check__",
    )
    if raw is None or raw == 0:
        return None

    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {'_available': False, 'data': {}}

    available = result.get('_available', False)
    saved_str = result.get('data')

    if not available or not saved_str:
        return {'_available': available, 'data': {}}

    try:
        data = json.loads(saved_str)
    except (json.JSONDecodeError, TypeError):
        return {'_available': available, 'data': {}}

    if not isinstance(data, dict) or data.get('version') != SAVE_VERSION:
        return {'_available': available, 'data': {}}

    return {'_available': available, 'data': data}


def save_state():
    """Serialize current session state and write to localStorage (fire-and-forget)."""
    state = _serialize_state()
    if state is None:
        return

    json_str = json.dumps(state)

    if len(json_str.encode("utf-8")) > MAX_SAVE_SIZE_BYTES:
        st.warning(
            "Your session data exceeds 5 MB. Saving may fail in some browsers. "
            "Consider downloading your annotated data and CodeBook using the download buttons."
        )

    escaped = json_str.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    components.html(
        f"""
        <script>
        try {{
            localStorage.setItem("{STORAGE_KEY}", `{escaped}`);
        }} catch (e) {{
            console.error("CodeBook Studio: failed to save to localStorage", e);
        }}
        </script>
        """,
        height=0,
    )

    st.session_state._last_save_time = datetime.now(timezone.utc)
    st.session_state._last_save_hash = _state_hash(state)
    st.session_state._has_active_save = True
    st.session_state._saved_data = state
    st.session_state._save_checked = True


def restore_session_state(state):
    """Populate st.session_state from a loaded save."""
    st.session_state.custom_schema = state["custom_schema"]
    st.session_state.index = state.get("index", 1)
    st.session_state.column_names = state.get("column_names", [])
    st.session_state.annotations_count = state.get("annotations_count", {})
    st.session_state._has_active_save = True
    st.session_state._last_save_hash = _state_hash(state)

    csv_str = state.get("data_csv")
    if csv_str:
        st.session_state.data = pd.read_csv(StringIO(csv_str))
    else:
        st.session_state.data = None

    st.session_state.page = _infer_resume_page(state, st.session_state.data)

    updated_at = state.get("updated_at")
    if updated_at:
        try:
            st.session_state._last_save_time = datetime.fromisoformat(updated_at)
        except (ValueError, TypeError):
            st.session_state._last_save_time = datetime.now(timezone.utc)

    st.session_state._saved_data = state
    st.session_state._save_checked = True


def clear_save():
    """Remove the save from localStorage (fire-and-forget)."""
    components.html(
        f"""
        <script>
        try {{
            localStorage.removeItem("{STORAGE_KEY}");
        }} catch (e) {{
            console.error("CodeBook Studio: failed to clear localStorage", e);
        }}
        </script>
        """,
        height=0,
    )
    st.session_state._has_active_save = False
    st.session_state._last_save_hash = None
    st.session_state._saved_data = {}
    st.session_state._save_checked = True


def auto_save_if_needed():
    """Auto-save if user has previously saved and state has changed."""
    if not st.session_state.get("_storage_available", False):
        return

    state = _serialize_state()
    if state is None:
        return

    current_hash = _state_hash(state)
    if current_hash == st.session_state.get("_last_save_hash"):
        return

    # Perform the save (same as save_state but without the size warning)
    json_str = json.dumps(state)
    escaped = json_str.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    components.html(
        f"""
        <script>
        try {{
            localStorage.setItem("{STORAGE_KEY}", `{escaped}`);
        }} catch (e) {{
            console.error("CodeBook Studio: auto-save failed", e);
        }}
        </script>
        """,
        height=0,
    )

    st.session_state._last_save_time = datetime.now(timezone.utc)
    st.session_state._last_save_hash = current_hash
    st.session_state._has_active_save = True
    st.session_state._saved_data = state
    st.session_state._save_checked = True


def _serialize_state():
    """Convert current session state to a dict for localStorage."""
    schema = st.session_state.get("custom_schema")
    if not schema:
        return None

    data = st.session_state.get("data")
    csv_str = None
    if data is not None:
        data_for_save = data.copy()
        index = st.session_state.get("index", 1) - 1
        annotations = st.session_state.get("annotations", {})
        if 0 <= index < len(data_for_save) and annotations:
            for annotation_option, value in annotations.items():
                if annotation_option in data_for_save.columns:
                    data_for_save.at[index, annotation_option] = value
        csv_str = data_for_save.to_csv(index=False)

    return {
        "version": SAVE_VERSION,
        "custom_schema": schema,
        "data_csv": csv_str,
        "index": st.session_state.get("index", 1),
        "column_names": st.session_state.get("column_names", []),
        "annotations_count": st.session_state.get("annotations_count", {}),
        "page": st.session_state.get("page", "landing"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _state_hash(state):
    """Compute a quick hash of the serialized state for change detection."""
    normalized_state = {key: value for key, value in state.items() if key != "updated_at"}
    raw = json.dumps(normalized_state, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def _infer_resume_page(state, restored_data):
    """Resume to the most useful working page for the saved session."""
    saved_page = state.get("page", "annotate")

    if saved_page == "landing":
        if restored_data is not None:
            return "annotate"
        if state.get("custom_schema"):
            return "create_schema"

    return saved_page
