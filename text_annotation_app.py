import streamlit as st
import pandas as pd
import json
import io
import html as html_module
import zipfile
from datetime import datetime, timezone

from utils.export import generate_latex_codebook, generate_markdown_codebook
from utils.prompt_preview import render_prompt_preview_page
from utils.persistence import (
    load_state_if_available,
    restore_session_state,
    clear_save,
    auto_save_if_needed,
)

DOCUMENT_PANE_HEIGHT = 620
ANNOTATION_PANE_HEIGHT = 572
EDITOR_PREVIEW_TEXT_HEIGHT = 360
EDITOR_PREVIEW_SECTION_HEIGHT = 360

def render_header(home_action=None):
    # Global CSS — injected once per page render
    global_css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Libre+Franklin:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

        :root {
            --cb-ink: #2f2b28;
            --cb-muted: #6d665f;
            --cb-border: #ddd5cd;
            --cb-panel: #f9f6f1;
            --cb-panel-strong: #f1ebe2;
            --cb-accent: #8a4f3d;
            --cb-accent-soft: #ede1d7;
        }

        /* Body font */
        html, body, [class*="css"],
        .stApp, .stMarkdown, [data-testid="stMarkdownContainer"] p,
        .stTextInput label, .stSelectbox label, .stCheckbox label,
        .stSlider label, .stTextArea label, .stFileUploader label,
        .stFileUploader section, .stDownloadButton button {
            font-family: "Libre Franklin", sans-serif !important;
        }

        /* Heading font */
        h1, h2, h3, h4, h5, h6,
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 {
            font-family: "Lora", serif !important;
            color: var(--cb-ink);
        }

        /* Subtle dividers */
        hr {
            border-color: var(--cb-border) !important;
        }

        /* Code blocks on prompt preview page */
        .stCodeBlock {
            border: 1px solid var(--cb-border);
            border-radius: 10px;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(233, 219, 204, 0.35), transparent 32%),
                linear-gradient(180deg, #fcfaf7 0%, #f6f1ea 100%);
        }

        /* Remove excess top padding from Streamlit's main content area */
        [data-testid="stAppViewBlockContainer"] {
            padding-top: 4.5rem !important;
            padding-bottom: 0.85rem !important;
            max-width: 1280px;
        }

        [data-testid="stMainBlockContainer"] {
            padding-top: 0 !important;
            padding-bottom: 0.5rem !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--cb-border);
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.72);
            box-shadow: 0 10px 30px rgba(72, 53, 34, 0.04);
        }

        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.56);
            border: 1px solid var(--cb-border);
            border-radius: 14px;
            padding: 0.75rem 0.9rem;
        }

        .stButton button, .stDownloadButton button {
            border-radius: 999px;
            border: 1px solid var(--cb-border);
        }

        .stProgress > div > div {
            background-color: var(--cb-accent);
        }

        .cb-kicker {
            color: var(--cb-accent);
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.6rem;
        }

        .cb-hero-title {
            font-family: "Lora", serif;
            font-size: clamp(2rem, 2.7vw, 3rem);
            line-height: 1.08;
            color: var(--cb-ink);
            margin: 0 0 0.8rem 0;
        }

        .cb-hero-copy {
            color: var(--cb-muted);
            line-height: 1.7;
            font-size: 1.04rem;
            margin-bottom: 1rem;
        }

        .cb-flow-step {
            padding: 1rem 1rem 0.95rem 1rem;
            border: 1px solid var(--cb-border);
            border-radius: 16px;
            background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(249,246,241,0.92));
            min-height: 9.2rem;
        }

        .cb-flow-step strong {
            display: block;
            color: var(--cb-ink);
            margin-bottom: 0.35rem;
        }

        .cb-flow-step p {
            margin: 0;
            color: var(--cb-muted);
            line-height: 1.55;
            font-size: 0.95rem;
        }

        .cb-flow-number {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2rem;
            height: 2rem;
            border-radius: 999px;
            background: var(--cb-accent-soft);
            color: var(--cb-accent);
            font-weight: 700;
            margin-bottom: 0.8rem;
        }

        .cb-subtle-note {
            color: var(--cb-muted);
            line-height: 1.6;
            font-size: 0.95rem;
        }

        .cb-toolbar-title {
            margin: 0;
            font-size: 1.4rem;
            line-height: 1.25;
        }

        .st-key-header_home {
            margin-top: 2.6rem;
        }

        .st-key-header_home button {
            all: unset;
            display: block;
            width: 100%;
            box-sizing: border-box;
            color: var(--cb-ink);
            padding: 0 0 0.3em 0;
            border-bottom: 1px solid var(--cb-border);
            cursor: pointer;
        }

        .st-key-header_home button p {
            margin: 0;
            font-family: "Lora", serif !important;
            font-weight: 700 !important;
            font-size: 2.25rem !important;
            line-height: 1.1 !important;
            color: inherit !important;
        }

        .st-key-header_home button:hover {
            color: var(--cb-accent);
        }

        .st-key-header_home button:focus,
        .st-key-header_home button:focus-visible {
            outline: none;
            box-shadow: none;
        }

        .cb-pane-label {
            color: var(--cb-muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.76rem;
            font-weight: 700;
            margin-bottom: 0.55rem;
        }

        .cb-document {
            color: var(--cb-ink);
            line-height: 1.72;
            font-size: 1rem;
            white-space: pre-wrap;
        }

        .cb-footer {
            margin-top: 0.8rem;
            padding: 0.55rem 0 0.1rem 0;
            color: #857d74;
            text-align: center;
            font-size: 0.88rem;
            border-top: 1px solid var(--cb-border);
        }

        .cb-footer a {
            color: #6f4a38 !important;
        }

        .cb-builder-meta {
            color: var(--cb-accent);
            font-size: 0.8rem;
            font-weight: 600;
            margin-bottom: 0.35rem;
        }

        .cb-builder-summary {
            color: var(--cb-muted);
            line-height: 1.55;
            font-size: 0.94rem;
            min-height: 2.9rem;
        }

        .cb-builder-empty {
            color: var(--cb-muted);
            font-style: italic;
            line-height: 1.55;
        }

        .cb-toolbar-inline {
            color: var(--cb-ink);
            font-size: 1.28rem;
            line-height: 1.35;
            margin: 0.1rem 0 0 0;
        }

        .cb-toolbar-inline-meta {
            color: var(--cb-muted);
            font-size: 0.96rem;
        }

        @media (max-width: 960px) {
            [data-testid="stAppViewBlockContainer"] {
                padding-top: 3.75rem !important;
                padding-bottom: 0.6rem !important;
            }

            .cb-flow-step {
                min-height: 0;
            }

            .st-key-header_home {
                margin-top: 1.85rem;
            }
        }

        /* Hide zero-height iframe containers (streamlit_js_eval, persistence) */
        iframe[height="0"] {
            display: none !important;
        }
        .stHtml:has(iframe[height="0"]),
        .element-container:has(iframe[height="0"]) {
            display: none !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        </style>
    """
    st.markdown(global_css, unsafe_allow_html=True)

    if home_action is None:
        def home_action():
            st.session_state.page = "landing"
            queue_auto_save()
            st.rerun()

    if st.button("📓 CodeBook Studio", key="header_home", help="Return to the landing page"):
        home_action()


def get_schema_sections(schema):
    return [(key, schema[key]) for key in schema if key.startswith("section")]


def get_annotation_column_name(section_content, annotation_content):
    return f"{section_content['section_name']}_{annotation_content['name']}"


def is_answered_value(value):
    if isinstance(value, str):
        return value.strip() != ""
    return pd.notna(value)


def format_saved_session_timestamp(updated_at):
    if not updated_at:
        return None
    try:
        dt = datetime.fromisoformat(updated_at)
        return dt.strftime("%B %d, %Y at %I:%M %p UTC")
    except (ValueError, TypeError):
        return updated_at


def format_last_save_caption(last_save):
    if not last_save:
        return None

    ago = (datetime.now(timezone.utc) - last_save).total_seconds()
    if ago < 60:
        return "Saved just now"
    if ago < 3600:
        return f"Saved {int(ago // 60)} min ago"
    return f"Saved at {last_save.strftime('%I:%M %p UTC')}"


def get_section_completion(section_content, annotation_values):
    annotations = section_content.get("annotations", {})
    total = len(annotations)
    completed = 0

    for annotation in annotations.values():
        full_column_name = get_annotation_column_name(section_content, annotation)
        if is_answered_value(annotation_values.get(full_column_name)):
            completed += 1

    return completed, total


def get_completed_sections(sections, annotation_values):
    completed_sections = 0
    for _, section_content in sections:
        completed, total = get_section_completion(section_content, annotation_values)
        if total > 0 and completed > 0:
            completed_sections += 1
    return completed_sections


def initialize_annotation_state(index, data, sections):
    cache_key = (index, id(data))
    if st.session_state.get("_annotation_cache_key") == cache_key:
        return

    annotations = {}
    for _, section_content in sections:
        for annotation in section_content.get("annotations", {}).values():
            full_column_name = get_annotation_column_name(section_content, annotation)
            current_value = data.at[index, full_column_name] if full_column_name in data.columns else None
            annotations[full_column_name] = None if pd.isna(current_value) else current_value

    st.session_state.annotations = annotations
    st.session_state._annotation_cache_key = cache_key


def queue_auto_save():
    st.session_state._pending_auto_save = True


def flush_queued_auto_save():
    if st.session_state.pop("_pending_auto_save", False):
        auto_save_if_needed()


def reset_working_session():
    keys_to_clear = [
        "custom_schema",
        "data",
        "uploaded_file",
        "column_names",
        "annotations_count",
        "annotations",
        "index",
        "previous_page",
        "active_annotation_section",
        "_annotation_cache_key",
        "_pending_auto_save",
        "csv_uploader",
        "json_uploader",
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)

    st.session_state.page = "landing"


def render_annotation_toolbar(index, data, sections):
    title_column = st.session_state.custom_schema["header_column"]
    current_title = data.iloc[index][title_column]
    completed_sections = get_completed_sections(sections, st.session_state.annotations)

    with st.container(border=True):
        title_col, progress_col, nav_col = st.columns([0.42, 0.3, 0.28], gap="medium")

        with title_col:
            safe_title = html_module.escape(str(current_title))
            st.markdown(
                f'<p class="cb-toolbar-inline"><span class="cb-toolbar-inline-meta">Item</span> '
                f'{safe_title} <span class="cb-toolbar-inline-meta">· '
                f'{completed_sections}/{len(sections)} sections touched</span></p>',
                unsafe_allow_html=True,
            )

        with progress_col:
            scrubbed_index = st.slider(
                "Item progress",
                min_value=1,
                max_value=len(data),
                value=index + 1,
                step=1,
                help="Drag to move quickly between items.",
                label_visibility="collapsed",
            )
            if scrubbed_index != index + 1:
                update_data(index, data)
                update_index(int(scrubbed_index))

        with nav_col:
            button_col1, button_col2 = st.columns(2, gap="small")
            with button_col1:
                if st.button("Prev", use_container_width=True, disabled=index == 0):
                    update_data(index, data)
                    update_index(index)
            with button_col2:
                if st.button("Next", use_container_width=True, disabled=index >= len(data) - 1):
                    update_data(index, data)
                    update_index(index + 2)


def render_text_pane(index, data):
    text_column = st.session_state.custom_schema["text_column"]
    current_text = data.iloc[index][text_column]
    safe_text = html_module.escape(str(current_text)).replace("\n", "<br>")

    with st.container(border=True, height=DOCUMENT_PANE_HEIGHT):
        st.markdown('<div class="cb-pane-label">Document text</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="cb-document">{safe_text}</div>', unsafe_allow_html=True)


def render_likert_selector(label, min_value, max_value, current_value, key, help_text=None, disabled=False):
    options = list(range(min_value, max_value + 1))
    default_value = None if pd.isna(current_value) else int(current_value)

    selected = st.segmented_control(
        label,
        options,
        default=default_value,
        key=key,
        help=help_text,
        disabled=disabled,
        width="stretch",
    )

    return selected


def build_codebook_bundle(schema):
    bundle_buffer = io.BytesIO()
    with zipfile.ZipFile(bundle_buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("codebook.json", json.dumps(schema, indent=4))
        bundle.writestr("codebook.tex", generate_latex_codebook(schema))
        bundle.writestr("codebook.md", generate_markdown_codebook(schema))

    bundle_buffer.seek(0)
    return bundle_buffer.getvalue()


def get_editor_preview_sample(header_column, text_column):
    sample_title = "Sample item"
    sample_text = "Upload data to preview how annotators will read and label a real text."
    sample_index = 1
    total_items = 1

    data = st.session_state.get("data")
    if data is not None and len(data) > 0:
        sample_row = data.iloc[0]
        return (
            str(sample_row.get(header_column, sample_title)),
            str(sample_row.get(text_column, sample_text)),
            sample_index,
            len(data),
        )

    uploaded_file = st.session_state.get("uploaded_file")
    if uploaded_file is not None:
        uploaded_file.seek(0)
        sample_df = pd.read_csv(uploaded_file, nrows=1)
        uploaded_file.seek(0)
        if not sample_df.empty:
            sample_row = sample_df.iloc[0]
            return (
                str(sample_row.get(header_column, sample_title)),
                str(sample_row.get(text_column, sample_text)),
                sample_index,
                total_items,
            )

    return sample_title, sample_text, sample_index, total_items


def render_editor_preview_annotation(annotation, key):
    label = annotation.get("name") or "Untitled annotation"
    tooltip = annotation.get("tooltip", "")

    if annotation["type"] == "checkbox":
        st.checkbox(label, help=tooltip, key=key, disabled=True)
    elif annotation["type"] == "likert":
        min_value = annotation.get("min_value", 0)
        max_value = annotation.get("max_value", 5)
        preview_value = 0 if min_value <= 0 <= max_value else min_value
        render_likert_selector(
            label,
            min_value,
            max_value,
            preview_value,
            key,
            help_text=tooltip,
            disabled=True,
        )
    elif annotation["type"] == "dropdown":
        options = [""] + annotation.get("options", [])
        st.selectbox(label, options, index=0, help=tooltip, key=key, disabled=True)
    elif annotation["type"] == "textbox":
        st.text_area(label, help=tooltip, key=key, height=100, disabled=True)

    if annotation.get("example"):
        with st.expander(f"Examples for {label}", expanded=False):
            st.write(annotation["example"], unsafe_allow_html=True)


def create_empty_annotation(annotation_type="checkbox"):
    annotation = {
        "name": "",
        "type": annotation_type,
        "tooltip": "",
        "example": "",
    }

    if annotation_type == "likert":
        annotation["min_value"] = 0
        annotation["max_value"] = 5
    elif annotation_type == "dropdown":
        annotation["options"] = []

    return annotation


def get_sorted_annotation_keys(section_content):
    def sort_key(annotation_key):
        suffix = annotation_key.split("_")[-1]
        return (0, int(suffix)) if suffix.isdigit() else (1, annotation_key)

    return sorted(section_content.get("annotations", {}).keys(), key=sort_key)


def get_annotation_response_summary(annotation):
    annotation_type = annotation.get("type", "checkbox")

    if annotation_type == "checkbox":
        return "Yes/no response"
    if annotation_type == "likert":
        return f"Scale {annotation.get('min_value', 0)} to {annotation.get('max_value', 5)}"
    if annotation_type == "dropdown":
        option_count = len(annotation.get("options", []))
        return f"{option_count} option{'s' if option_count != 1 else ''}"
    return "Free-text response"


def get_annotation_editor_state_key(section_key):
    return f"editor_selected_annotation_{section_key}"


def sync_schema_editor_state_from_widgets(schema):
    for section_key, section in get_schema_sections(schema):
        section_name_key = f"{section_key}_name"
        section_instruction_key = f"{section_key}_instructions"

        if section_name_key in st.session_state:
            section["section_name"] = st.session_state[section_name_key]
        if section_instruction_key in st.session_state:
            section["section_instruction"] = st.session_state[section_instruction_key]

        for annotation_key, annotation in section.get("annotations", {}).items():
            annotation_name_key = f"{section_key}_{annotation_key}_name"
            annotation_type_key = f"{section_key}_{annotation_key}_type"
            annotation_tooltip_key = f"{section_key}_{annotation_key}_tooltip"
            annotation_example_key = f"{section_key}_{annotation_key}_example"
            annotation_min_key = f"{section_key}_{annotation_key}_min_value"
            annotation_max_key = f"{section_key}_{annotation_key}_max_value"
            annotation_options_key = f"{section_key}_{annotation_key}_options"

            if annotation_name_key in st.session_state:
                annotation["name"] = st.session_state[annotation_name_key]
            if annotation_type_key in st.session_state:
                annotation["type"] = st.session_state[annotation_type_key]
            if annotation_tooltip_key in st.session_state:
                annotation["tooltip"] = st.session_state[annotation_tooltip_key]
            if annotation_example_key in st.session_state:
                annotation["example"] = st.session_state[annotation_example_key]
            if annotation_min_key in st.session_state:
                annotation["min_value"] = int(st.session_state[annotation_min_key])
            if annotation_max_key in st.session_state:
                annotation["max_value"] = int(st.session_state[annotation_max_key])
            if annotation_options_key in st.session_state:
                annotation["options"] = [
                    option.strip()
                    for option in st.session_state[annotation_options_key].split(",")
                    if option.strip()
                ]


def render_schema_workflow_preview(schema, header_column, text_column):
    sections = get_schema_sections(schema)
    if not sections:
        return

    sample_title, sample_text, sample_index, total_items = get_editor_preview_sample(header_column, text_column)
    section_keys = [section_key for section_key, _ in sections]
    option_labels = {
        section_key: section_content.get("section_name") or f"Section {idx + 1}"
        for idx, (section_key, section_content) in enumerate(sections)
    }

    active_section = st.session_state.get("editor_preview_section")
    if active_section not in section_keys:
        active_section = section_keys[0]
        st.session_state.editor_preview_section = active_section

    st.markdown("#### Annotation Workflow Preview")
    st.caption("This preview mirrors the annotation workspace using a sample text from your uploaded data.")

    with st.container(border=True):
        title_col, progress_col, nav_col = st.columns([0.44, 0.24, 0.32], gap="medium")

        with title_col:
            st.markdown('<div class="cb-pane-label">Current item</div>', unsafe_allow_html=True)
            st.markdown(f'<p class="cb-toolbar-title">{html_module.escape(sample_title)}</p>', unsafe_allow_html=True)

        with progress_col:
            if total_items > 1:
                st.slider(
                    "Preview item progress",
                    min_value=1,
                    max_value=total_items,
                    value=min(sample_index, total_items),
                    step=1,
                    disabled=True,
                    label_visibility="collapsed",
                )
            else:
                st.progress(1.0, text="1")
            st.caption(f"0/{len(sections)} sections touched")

        with nav_col:
            button_col1, button_col2 = st.columns(2, gap="small")
            with button_col1:
                st.button("Previous", key="preview_previous", use_container_width=True, disabled=True)
            with button_col2:
                st.button("Next", key="preview_next", use_container_width=True, disabled=True)

    preview_left, preview_right = st.columns([1.02, 0.98], gap="medium")

    with preview_left:
        with st.container(border=True, height=EDITOR_PREVIEW_TEXT_HEIGHT):
            st.markdown('<div class="cb-pane-label">Document text</div>', unsafe_allow_html=True)
            safe_text = html_module.escape(sample_text).replace("\n", "<br>")
            st.markdown(f'<div class="cb-document">{safe_text}</div>', unsafe_allow_html=True)

    with preview_right:
        preview_section = st.pills(
            "Preview section",
            section_keys,
            key="editor_preview_section",
            format_func=lambda key: option_labels[key],
            width="stretch",
            label_visibility="collapsed",
        )
        if preview_section is None:
            preview_section = active_section

        preview_content = dict(sections)[preview_section]
        preview_annotations = list(preview_content.get("annotations", {}).values())
        checkbox_only = preview_annotations and all(annotation["type"] == "checkbox" for annotation in preview_annotations)

        with st.container(border=True, height=EDITOR_PREVIEW_SECTION_HEIGHT):
            st.markdown('<div class="cb-pane-label">Annotation section</div>', unsafe_allow_html=True)
            st.subheader(option_labels[preview_section])

            section_instruction = preview_content.get("section_instruction", "")
            if section_instruction:
                with st.expander("Instructions", expanded=False):
                    st.write(section_instruction)

            if checkbox_only:
                checkbox_columns = st.columns(2, gap="medium")
                for idx, annotation in enumerate(preview_annotations):
                    with checkbox_columns[idx % 2]:
                        render_editor_preview_annotation(annotation, key=f"preview_{preview_section}_{idx}")
            else:
                for idx, annotation in enumerate(preview_annotations):
                    render_editor_preview_annotation(annotation, key=f"preview_{preview_section}_{idx}")


def sync_annotations_count():
    if "annotations_count" not in st.session_state:
        st.session_state.annotations_count = {}

    valid_section_keys = set()
    for section_key, section_value in get_schema_sections(st.session_state.custom_schema):
        valid_section_keys.add(section_key)
        existing_count = len(section_value.get("annotations", {}))
        st.session_state.annotations_count[section_key] = existing_count

    stale_keys = [key for key in st.session_state.annotations_count if key not in valid_section_keys]
    for key in stale_keys:
        st.session_state.annotations_count.pop(key, None)


def render_annotation_input(section_content, config, full_column_name, index):
    current_value = st.session_state.annotations.get(full_column_name)
    widget_key = f"{index}_{full_column_name}"

    if config["type"] == "checkbox":
        annotated = st.checkbox(
            config["name"],
            value=bool(current_value) if pd.notna(current_value) else False,
            key=widget_key,
            help=config["tooltip"],
        )
        st.session_state.annotations[full_column_name] = 1 if annotated else 0
    elif config["type"] == "likert":
        min_value = config.get("min_value", 0)
        max_value = config.get("max_value", 5)
        annotated = render_likert_selector(
            config["name"],
            min_value,
            max_value,
            current_value,
            widget_key,
            help_text=config["tooltip"],
        )
        st.session_state.annotations[full_column_name] = annotated
    elif config["type"] == "dropdown":
        options = [""] + config.get("options", [])
        if pd.isna(current_value) or current_value not in options:
            selected_index = 0
        else:
            selected_index = options.index(current_value)
        annotated = st.selectbox(
            config["name"],
            options,
            index=selected_index,
            key=widget_key,
            help=config["tooltip"],
        )
        st.session_state.annotations[full_column_name] = annotated if annotated else None
    elif config["type"] == "textbox":
        annotated = st.text_area(
            config["name"],
            value="" if pd.isna(current_value) else current_value,
            key=widget_key,
            help=config["tooltip"],
            height=120,
        )
        st.session_state.annotations[full_column_name] = annotated

    if config.get("example"):
        with st.expander(f"Examples for {config['name']}", expanded=False):
            st.write(config["example"], unsafe_allow_html=True)


def render_active_section(index, sections):
    section_keys = [section_key for section_key, _ in sections]
    if not section_keys:
        st.warning("Your CodeBook has no sections yet. Edit the CodeBook to add annotations.")
        return

    active_section = st.session_state.get("active_annotation_section")
    if active_section not in section_keys:
        active_section = section_keys[0]
        st.session_state.active_annotation_section = active_section

    option_labels = {
        section_key: section_content.get("section_name") or f"Section {idx + 1}"
        for idx, (section_key, section_content) in enumerate(sections)
    }

    selected_section = st.pills(
        "Annotation section",
        section_keys,
        key="active_annotation_section",
        format_func=lambda key: option_labels[key],
        width="stretch",
        label_visibility="collapsed",
    )
    if selected_section is None:
        selected_section = active_section

    section_content = dict(sections)[selected_section]
    completed, total = get_section_completion(section_content, st.session_state.annotations)
    annotations = list(section_content.get("annotations", {}).values())
    checkbox_only = annotations and all(annotation["type"] == "checkbox" for annotation in annotations)

    with st.container(border=True, height=ANNOTATION_PANE_HEIGHT):
        st.markdown('<div class="cb-pane-label">Annotation section</div>', unsafe_allow_html=True)
        st.subheader(option_labels[selected_section])
        st.caption(f"{completed}/{total} responses completed in this section")

        section_instruction = section_content.get("section_instruction", "")
        if section_instruction:
            with st.expander("Instructions", expanded=False):
                st.write(section_instruction)

        if checkbox_only:
            checkbox_columns = st.columns(2, gap="medium")
            for idx, config in enumerate(annotations):
                full_column_name = get_annotation_column_name(section_content, config)
                with checkbox_columns[idx % 2]:
                    render_annotation_input(section_content, config, full_column_name, index)
        else:
            for config in annotations:
                full_column_name = get_annotation_column_name(section_content, config)
                render_annotation_input(section_content, config, full_column_name, index)

def render_annotation_utilities(index, data):
    with st.expander("Utilities", expanded=True):
        utility_col1, utility_col2 = st.columns(2, gap="large")

        with utility_col1:
            st.markdown("##### Workflow")
            if st.button("Edit CodeBook", use_container_width=True):
                update_data(index, data)
                st.session_state.data = data
                st.session_state.page = "create_schema"
                queue_auto_save()
                st.rerun()

            if st.button("Preview LLM Prompts", use_container_width=True):
                update_data(index, data)
                st.session_state.data = data
                st.session_state.previous_page = "annotate"
                st.session_state.page = "prompt_preview"
                queue_auto_save()
                st.rerun()

        with utility_col2:
            st.markdown("##### Export")
            csv_data = st.session_state.data.copy()
            update_data(index, csv_data)
            csv = csv_data.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Annotated Data",
                data=csv,
                file_name="annotated-data.csv",
                mime="text/csv",
                use_container_width=True,
            )

            codebook_bundle = build_codebook_bundle(st.session_state.custom_schema)
            st.download_button(
                label="Download CodeBook",
                data=codebook_bundle,
                file_name="codebook.zip",
                mime="application/zip",
                use_container_width=True,
            )

def process_data(uploaded_file, text_column):
    if 'data' not in st.session_state or st.session_state.data is None:
        uploaded_file.seek(0)  # Reset file pointer
        df = pd.read_csv(uploaded_file)

        if text_column not in df.columns:
            raise ValueError(f"Selected column '{text_column}' not found in the uploaded file.")
    else:
        df = st.session_state.data

    for section_key, section_content in st.session_state.custom_schema.items():
        if "section" in section_key:
            for _, annotation_content in section_content["annotations"].items():
                full_column_name = f"{section_content['section_name']}_{annotation_content['name']}"
                if full_column_name not in df.columns:
                    df[full_column_name] = None

    return df

def find_last_annotated_row(data, custom_schema):
    for i in range(len(data) - 1, -1, -1):
        for key, content in custom_schema.items():
            if "section" in key:
                for _, config in content["annotations"].items():
                    full_column_name = f"{content['section_name']}_{config['name']}"
                    if pd.notna(data.at[i, full_column_name]):
                        return i + 1
    return 0

def annotation_page():
    if 'index' not in st.session_state or 'data' not in st.session_state or st.session_state.data is None:
        render_header()
        st.warning("Please upload a CSV file to start annotating.")
        if st.button("Return to Landing Page"):
            st.session_state.page = 'landing'
            st.session_state.pop('index', None)
            st.session_state.pop('data', None)
            st.rerun()
        return

    index = st.session_state.index - 1
    data = st.session_state.data

    if 'data' not in st.session_state or data is None:
        render_header()
        st.warning("Please upload a CSV file to start annotating.")
        return

    def go_to_landing_page():
        update_data(index, data)
        st.session_state.data = data
        st.session_state.page = "landing"
        queue_auto_save()
        st.rerun()

    render_header(home_action=go_to_landing_page)

    sections = get_schema_sections(st.session_state.custom_schema)
    initialize_annotation_state(index, data, sections)

    render_annotation_toolbar(index, data, sections)
    st.write("")

    left_column, right_column = st.columns([1.04, 0.96], gap="medium")
    with left_column:
        render_text_pane(index, data)
    with right_column:
        render_active_section(index, sections)

    render_annotation_utilities(index, data)
    flush_queued_auto_save()

def landing_page():
    render_header()

    # Check for saved session in localStorage (non-blocking)
    if not st.session_state.get("_save_checked", False):
        result = load_state_if_available()
        if result is not None:
            st.session_state._save_checked = True
            st.session_state._storage_available = result.get('_available', False)
            st.session_state._saved_data = result.get('data', {})

    saved_data = st.session_state.get('_saved_data', {})
    left_column, right_column = st.columns([0.58, 0.42], gap="large")

    with left_column:
        st.markdown('<div class="cb-kicker">Research-ready text annotation</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="cb-hero-title">Create one codebook, then annotate, export, and reuse it.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cb-hero-copy">CodeBook Studio keeps task design, human annotation, '
            'LLM prompt inspection, and appendix exports in the same workflow, so annotators and '
            'researchers spend less time juggling formats.</div>',
            unsafe_allow_html=True,
        )

        step_col1, step_col2, step_col3 = st.columns(3, gap="small")
        step_markup = [
            (
                "1",
                "Upload data",
                "Load a CSV, choose the text column, and optionally bring an existing CodeBook.",
            ),
            (
                "2",
                "Annotate efficiently",
                "Work through each text in a compact workstation designed to minimize page scrolling.",
            ),
            (
                "3",
                "Export once",
                "Download the annotated CSV and CodeBook outputs for reporting or downstream LLM evaluation.",
            ),
        ]
        for column, (number, title, body) in zip((step_col1, step_col2, step_col3), step_markup):
            with column:
                st.markdown(
                    f'<div class="cb-flow-step"><span class="cb-flow-number">{number}</span>'
                    f'<strong>{title}</strong><p>{body}</p></div>',
                    unsafe_allow_html=True,
                )

        st.write("")
        st.markdown("#### Research workflow")
        st.markdown(
            '<div class="cb-subtle-note">CodeBook Studio is built for computational social science workflows '
            'that need a consistent annotation scheme across human coding, LLM prompt preview, and research '
            'reporting. Exported JSON CodeBooks can be used directly in '
            '<a href="https://github.com/LorcanMcLaren/codebook-lab" target="_blank">CodeBook Lab</a> '
            'to run and evaluate LLM annotation experiments from the same task definition.</div>',
            unsafe_allow_html=True,
        )

    with right_column:
        with st.container(border=True):
            st.markdown("### Get Started")

            if saved_data:
                display_time = format_saved_session_timestamp(saved_data.get("updated_at", ""))
                if display_time:
                    st.info(f"Saved session available from {display_time}.")
                else:
                    st.info("Saved session available.")
                st.warning(
                    "Starting fresh will clear this saved session. Download your CodeBook and annotated data "
                    "first if you want to keep your progress."
                )

                resume_col, fresh_col = st.columns(2, gap="small")
                with resume_col:
                    if st.button("Resume Session", use_container_width=True):
                        restore_session_state(saved_data)
                        st.rerun()
                with fresh_col:
                    if st.button("Start Fresh", use_container_width=True):
                        clear_save()
                        reset_working_session()
                        st.rerun()
            else:
                uploaded_file = st.file_uploader(
                    "Upload your CSV data",
                    type=["csv"],
                    key="csv_uploader",
                    help="Choose the CSV that contains the text you want to annotate.",
                )

                if uploaded_file is not None:
                    temp_df = pd.read_csv(uploaded_file)
                    st.session_state.column_names = temp_df.columns.tolist()
                    st.session_state.uploaded_file = uploaded_file
                    st.session_state.index = 1

                    st.caption(f"{len(temp_df):,} rows loaded across {len(temp_df.columns)} columns")

                    schema_file = st.file_uploader(
                        "Optional CodeBook JSON",
                        type=["json"],
                        key="json_uploader",
                        help="Upload an existing CodeBook, or continue and create one in the next step.",
                    )

                    if schema_file is not None:
                        st.session_state.custom_schema = json.load(schema_file)
                    else:
                        st.session_state.custom_schema = {}

                    cta_label = "Start Annotating" if st.session_state.custom_schema else "Create CodeBook"
                    if st.button(cta_label, type="primary", use_container_width=True):
                        if st.session_state.custom_schema:
                            st.session_state.data = process_data(
                                st.session_state.uploaded_file,
                                st.session_state.custom_schema["text_column"],
                            )
                            last_annotated_row = find_last_annotated_row(
                                st.session_state.data,
                                st.session_state.custom_schema,
                            )
                            st.session_state.index = (
                                last_annotated_row + 1
                                if last_annotated_row < len(st.session_state.data)
                                else len(st.session_state.data)
                            )
                            st.session_state.page = "annotate"
                        else:
                            st.session_state.page = "create_schema"
                        queue_auto_save()
                        st.rerun()
                else:
                    st.caption("Start with a CSV file. You can attach a CodeBook after the upload step.")

    st.write("")
    st.markdown(
        '<div class="cb-subtle-note">If you use CodeBook Studio in research, please cite the software '
        'repository: <a href="https://github.com/LorcanMcLaren/codebook-studio" target="_blank">'
        'github.com/LorcanMcLaren/codebook-studio</a>.</div>',
        unsafe_allow_html=True,
    )
    flush_queued_auto_save()


def schema_creation_page():
    def go_to_landing_page():
        st.session_state.page = "landing"
        queue_auto_save()
        st.rerun()

    render_header(home_action=go_to_landing_page)
    _, intro_column, _ = st.columns([0.08, 0.84, 0.08])
    with intro_column:
        st.header("Create Your CodeBook")
        st.markdown(
            "Your CodeBook defines the annotation task: what questions annotators should answer "
            "for each text, and what response formats are available. The same CodeBook file can "
            "be used for human annotation in this app, passed directly to an LLM annotation "
            "pipeline, or exported as a LaTeX/Markdown appendix for your paper."
        )
        st.caption(
            "Tip: download the JSON CodeBook here and use it in "
            "[CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab) "
            "if you want to run LLM annotation experiments from the same task definition."
        )
        st.markdown(
            "**How it works:**\n"
            "- **Sections** group related annotations together (e.g. *Sentiment*, *Moral Foundations*)\n"
            "- Each section contains one or more **annotations** — individual questions or judgements\n"
            "- Each annotation has a **type** that determines the response format:\n"
            "  - **Checkbox** — binary yes/no (e.g. *Is anger present?*)\n"
            "  - **Likert** — a numeric scale with configurable endpoints (e.g. 1–5)\n"
            "  - **Dropdown** — select one option from a predefined list (e.g. *positive / negative*)\n"
            "  - **Textbox** — free-form text response\n\n"
            "Start by selecting which columns in your CSV contain the text to annotate and an "
            "optional header/title, then build your sections and annotations below."
        )
        st.divider()

        header_column_default = st.session_state.custom_schema.get("header_column", "")
        text_column_default = st.session_state.custom_schema.get("text_column", "")
        header_column = st.selectbox(
            "Header column",
            st.session_state.column_names,
            index=st.session_state.column_names.index(header_column_default)
            if header_column_default in st.session_state.column_names
            else 0,
            key="header_column_selector",
            help="The column used as a title or identifier for each text (displayed above the text during annotation)",
        )
        text_column = st.selectbox(
            "Text column",
            st.session_state.column_names,
            index=st.session_state.column_names.index(text_column_default)
            if text_column_default in st.session_state.column_names
            else 0,
            key="text_column_selector",
            help="The column containing the main text content that annotators will read and annotate",
        )

    # Initialize or update the session state for codebook creation
    if not st.session_state.custom_schema:
        st.session_state.custom_schema = {
            "header_column": header_column,
            "text_column": text_column,
            "section_1": {
                "section_name": "",
                "section_instruction": "",
                "annotations": {},
            },
        }

    sync_annotations_count()

    # Store the selected columns in custom_schema
    if st.session_state.custom_schema:
        st.session_state.custom_schema["header_column"] = header_column
        st.session_state.custom_schema["text_column"] = text_column
        sync_schema_editor_state_from_widgets(st.session_state.custom_schema)

    def add_section():
        existing_numbers = [
            int(section_key.split("_")[-1])
            for section_key, _ in get_schema_sections(st.session_state.custom_schema)
            if section_key.split("_")[-1].isdigit()
        ]
        next_number = max(existing_numbers, default=0) + 1
        new_section_key = f"section_{next_number}"
        st.session_state.custom_schema[new_section_key] = {
            "section_name": "",
            "section_instruction": "",
            "annotations": {},
        }
        st.session_state.annotations_count[new_section_key] = 0
        st.rerun()

    def delete_section(section_key):
        del st.session_state.custom_schema[section_key]
        st.session_state.annotations_count.pop(section_key, None)
        st.session_state.pop(get_annotation_editor_state_key(section_key), None)
        st.rerun()

    def add_annotation(section_key, annotation_type):
        annotations = st.session_state.custom_schema[section_key].setdefault("annotations", {})
        existing_numbers = [
            int(annotation_key.split("_")[-1])
            for annotation_key in annotations
            if annotation_key.split("_")[-1].isdigit()
        ]
        next_number = max(existing_numbers, default=0) + 1

        new_annotation_key = f"annotation_{next_number}"
        annotations[new_annotation_key] = create_empty_annotation(annotation_type)
        st.session_state.annotations_count[section_key] = len(annotations)
        st.session_state[get_annotation_editor_state_key(section_key)] = new_annotation_key
        st.rerun()

    def delete_annotation(section_key, annotation_key):
        annotations = st.session_state.custom_schema[section_key].get("annotations", {})
        if annotation_key in annotations:
            del annotations[annotation_key]

        annotation_keys = get_sorted_annotation_keys(st.session_state.custom_schema[section_key])
        editor_state_key = get_annotation_editor_state_key(section_key)
        if st.session_state.get(editor_state_key) == annotation_key:
            st.session_state[editor_state_key] = annotation_keys[0] if annotation_keys else None

        st.session_state.annotations_count[section_key] = len(annotation_keys)
        st.rerun()

    render_schema_workflow_preview(st.session_state.custom_schema, header_column, text_column)

    _, builder_column, _ = st.columns([0.08, 0.84, 0.08])
    with builder_column:
        st.divider()

        for section_key, section in get_schema_sections(st.session_state.custom_schema):
            section_title = f"Section {section_key.split('section_')[-1]}"
            annotation_keys = get_sorted_annotation_keys(section)
            editor_state_key = get_annotation_editor_state_key(section_key)
            selected_annotation_key = st.session_state.get(editor_state_key)
            if selected_annotation_key not in annotation_keys:
                selected_annotation_key = annotation_keys[0] if annotation_keys else None
                st.session_state[editor_state_key] = selected_annotation_key

            with st.container():
                left_column, right_column = st.columns([0.8, 0.2])
                with left_column:
                    st.subheader(section_title)
                with right_column:
                    if st.button("Delete Section", key=f"delete_section_{section_key}"):
                        delete_section(section_key)

                section["section_name"] = st.text_input(
                    "Section name",
                    key=f"{section_key}_name",
                    value=section.get("section_name", ""),
                    help="A descriptive name for this group of annotations (e.g. 'Discrete Emotions', 'Economic Sentiment')",
                )
                section["section_instruction"] = st.text_area(
                    "Section instructions",
                    key=f"{section_key}_instructions",
                    value=section.get("section_instruction", ""),
                    help="Instructions shown to annotators before this section's annotations. Explain the task and any guidelines.",
                )

                st.markdown("##### Add annotation")
                add_button_columns = st.columns(4, gap="small")
                add_types = ["checkbox", "dropdown", "likert", "textbox"]
                for column, annotation_type in zip(add_button_columns, add_types):
                    with column:
                        if st.button(
                            f"Add {annotation_type.title()}",
                            key=f"add_{annotation_type}_{section_key}",
                            use_container_width=True,
                        ):
                            add_annotation(section_key, annotation_type)

                builder_left, builder_right = st.columns([0.42, 0.58], gap="medium")

                with builder_left:
                    st.markdown("##### Annotation list")
                    st.caption("Select an annotation to edit it. The preview above updates from this same schema.")

                    if not annotation_keys:
                        with st.container(border=True):
                            st.markdown(
                                '<div class="cb-builder-empty">This section does not have any annotations yet. '
                                'Choose a response type above to add the first one.</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        for ann_idx, ann_key in enumerate(annotation_keys, start=1):
                            annotation = section["annotations"][ann_key]
                            display_name = annotation.get("name") or f"Annotation {ann_idx}"
                            description = annotation.get("tooltip", "").strip()
                            if description and len(description) > 120:
                                description = f"{description[:117].rstrip()}..."
                            if not description:
                                description = "No description yet. Add guidance so annotators and prompts interpret this field consistently."

                            with st.container(border=True):
                                st.markdown(f"**{html_module.escape(display_name)}**", unsafe_allow_html=True)
                                st.markdown(
                                    f'<div class="cb-builder-meta">{annotation.get("type", "checkbox").title()} · '
                                    f'{html_module.escape(get_annotation_response_summary(annotation))}</div>',
                                    unsafe_allow_html=True,
                                )
                                st.markdown(
                                    f'<div class="cb-builder-summary">{html_module.escape(description)}</div>',
                                    unsafe_allow_html=True,
                                )

                                card_action_left, card_action_right = st.columns([0.55, 0.45], gap="small")
                                with card_action_left:
                                    if ann_key == selected_annotation_key:
                                        st.button(
                                            "Editing",
                                            key=f"editing_annotation_{section_key}_{ann_key}",
                                            use_container_width=True,
                                            disabled=True,
                                        )
                                    elif st.button(
                                        "Edit",
                                        key=f"edit_annotation_{section_key}_{ann_key}",
                                        use_container_width=True,
                                    ):
                                        selected_annotation_key = ann_key
                                        st.session_state[editor_state_key] = ann_key
                                with card_action_right:
                                    if st.button(
                                        "Delete",
                                        key=f"delete_annotation_{section_key}_{ann_key}",
                                        use_container_width=True,
                                    ):
                                        delete_annotation(section_key, ann_key)

                with builder_right:
                    st.markdown("##### Focused editor")
                    if selected_annotation_key is None:
                        with st.container(border=True):
                            st.markdown(
                                '<div class="cb-builder-empty">Pick an annotation from the list, or add a new one '
                                'above to configure how it will appear during annotation.</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        annotation = section["annotations"][selected_annotation_key]
                        with st.container(border=True):
                            st.caption("Edits save into the CodeBook immediately.")
                            st.subheader(annotation.get("name") or "Untitled annotation")

                            identity_left, identity_right = st.columns([0.58, 0.42], gap="medium")
                            with identity_left:
                                annotation["name"] = st.text_input(
                                    "Name",
                                    key=f"{section_key}_{selected_annotation_key}_name",
                                    value=annotation.get("name", ""),
                                    help="The label for this annotation, shown to both human annotators and in LLM prompts (e.g. 'Anger', 'Spatial Distance', 'Positivity')",
                                )
                            with identity_right:
                                current_type = annotation.get("type", "checkbox")
                                annotation["type"] = st.selectbox(
                                    "Type",
                                    ["checkbox", "likert", "dropdown", "textbox"],
                                    key=f"{section_key}_{selected_annotation_key}_type",
                                    index=["checkbox", "likert", "dropdown", "textbox"].index(current_type),
                                )

                            annotation["tooltip"] = st.text_area(
                                "Description",
                                key=f"{section_key}_{selected_annotation_key}_tooltip",
                                value=annotation.get("tooltip", ""),
                                help="A detailed description of what this annotation measures. This is shown as help text during annotation and used as the main instruction in LLM prompts.",
                            )
                            annotation["example"] = st.text_area(
                                "Examples",
                                key=f"{section_key}_{selected_annotation_key}_example",
                                value=annotation.get("example", ""),
                                help='Provide examples to guide annotators. For LLM prompts, use the format: Text: \\n"example text"\\n\\nResponse: \\n{"response": "value"}',
                            )

                            if annotation["type"] == "likert":
                                likert_left, likert_right = st.columns(2, gap="small")
                                with likert_left:
                                    annotation["min_value"] = int(
                                        st.number_input(
                                            "Minimum value",
                                            key=f"{section_key}_{selected_annotation_key}_min_value",
                                            value=int(annotation.get("min_value", 0)),
                                            step=1,
                                        )
                                    )
                                with likert_right:
                                    annotation["max_value"] = int(
                                        st.number_input(
                                            "Maximum value",
                                            key=f"{section_key}_{selected_annotation_key}_max_value",
                                            value=int(annotation.get("max_value", 5)),
                                            step=1,
                                        )
                                    )
                            elif annotation["type"] == "dropdown":
                                options_str = st.text_area(
                                    "Options (comma-separated)",
                                    key=f"{section_key}_{selected_annotation_key}_options",
                                    value=",".join(annotation.get("options", [])),
                                    help="List the available choices, separated by commas (e.g. 'negative, positive' or 'Low, Medium, High')",
                                )
                                annotation["options"] = [
                                    option.strip() for option in options_str.split(",") if option.strip()
                                ]
                            else:
                                st.caption("No additional settings are needed for this response type.")

                            st.markdown("###### Annotation preview")
                            render_editor_preview_annotation(
                                annotation,
                                key=f"builder_preview_{section_key}_{selected_annotation_key}",
                            )

                st.divider()

        if st.button("Add New Section"):
            add_section()

        st.divider()
        codebook_bundle = build_codebook_bundle(st.session_state.custom_schema)
        st.download_button(
            label="Download CodeBook",
            data=codebook_bundle,
            file_name="codebook.zip",
            mime="application/zip",
        )

        if st.button("Preview LLM Prompts"):
            st.session_state.previous_page = 'create_schema'
            st.session_state.page = 'prompt_preview'
            queue_auto_save()
            st.rerun()

        if st.button("Start Annotating"):
            st.session_state.data = process_data(st.session_state.uploaded_file, text_column)
            st.session_state.page = 'annotate'
            queue_auto_save()
            st.rerun()

    flush_queued_auto_save()


def update_data(index, data):
    for annotation_option in st.session_state.annotations:
        data.at[index, annotation_option] = st.session_state.annotations[annotation_option]

def update_index(new_index):
    st.session_state.index = new_index
    queue_auto_save()
    st.rerun()

def prompt_preview_page():
    render_header()
    render_prompt_preview_page(st.session_state.custom_schema)

    previous = st.session_state.get('previous_page', 'annotate')
    label = "Back to Annotation" if previous == 'annotate' else "Back to CodeBook Editor"
    if st.button(label):
        st.session_state.page = previous
        queue_auto_save()
        st.rerun()

    flush_queued_auto_save()


if 'page' not in st.session_state:
    st.session_state.page = 'landing'

page_title = "CodeBook Studio"
page_icon = "📓"

if st.session_state.page == 'landing':
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide")
    landing_page()
elif st.session_state.page == 'annotate':
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide")
    annotation_page()
elif st.session_state.page == 'create_schema':
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide")
    schema_creation_page()
elif st.session_state.page == 'prompt_preview':
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide")
    prompt_preview_page()


# Add a footer
footer = """
<div class="cb-footer">
<p>Developed by <a href="https://www.lorcanmclaren.com" target="_blank">Lorcan McLaren</a></p>
</div>
"""
st.markdown(footer, unsafe_allow_html=True)
