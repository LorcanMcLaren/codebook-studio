import streamlit as st
import pandas as pd
import copy
import json
import io
import base64
import html as html_module
import re
import zipfile
import urllib.request
import urllib.error
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from utils.export import generate_latex_codebook, generate_markdown_codebook
from utils.html_parser import parse_example_blocks, serialize_example_blocks
from utils.prompt_preview import render_prompt_preview_page
from utils import persistence as persistence_utils
from utils.codebook_diff import diff_schemas, group_by_section, field_label

load_state_if_available = persistence_utils.load_state_if_available
restore_session_state = persistence_utils.restore_session_state
clear_save = persistence_utils.clear_save
auto_save_if_needed = persistence_utils.auto_save_if_needed


def record_version(label=None):
    """Append a CodeBook version, with a local fallback for older deployments."""
    if hasattr(persistence_utils, "record_version"):
        return persistence_utils.record_version(label)

    schema = st.session_state.get("custom_schema")
    if not schema:
        return None

    now = datetime.now(timezone.utc)
    snapshot = {
        "id": "v_" + now.strftime("%Y%m%dT%H%M%S%f"),
        "saved_at": now.isoformat(),
        "label": (label or "").strip(),
        "schema": copy.deepcopy(schema),
    }

    versions = list(st.session_state.get("codebook_versions", []))
    versions.append(snapshot)
    st.session_state.codebook_versions = versions
    return snapshot


def delete_version(version_id):
    """Remove a saved CodeBook version."""
    if hasattr(persistence_utils, "delete_version"):
        return persistence_utils.delete_version(version_id)

    st.session_state.codebook_versions = [
        v for v in st.session_state.get("codebook_versions", [])
        if v.get("id") != version_id
    ]
    return None


def get_version(version_id):
    """Return a saved CodeBook version by id."""
    if hasattr(persistence_utils, "get_version"):
        return persistence_utils.get_version(version_id)

    for version in st.session_state.get("codebook_versions", []):
        if version.get("id") == version_id:
            return version
    return None


def restore_version(version_id):
    """Restore a saved CodeBook version."""
    if hasattr(persistence_utils, "restore_version"):
        return persistence_utils.restore_version(version_id)

    version = get_version(version_id)
    if not version:
        return False
    st.session_state.custom_schema = copy.deepcopy(version["schema"])
    return True

DOCUMENT_PANE_HEIGHT = 620
ANNOTATION_PANE_HEIGHT = 572
EDITOR_PREVIEW_SECTION_HEIGHT = 360
EDITOR_PREVIEW_SELECTOR_OFFSET = 46
EDITOR_PREVIEW_TEXT_HEIGHT = EDITOR_PREVIEW_SECTION_HEIGHT + EDITOR_PREVIEW_SELECTOR_OFFSET
APP_DIR = Path(__file__).resolve().parent
DEMO_TASKS_DIR = APP_DIR / "demo_tasks"
DEMO_TASKS = {
    "policy_sentiment": {
        "slug": "policy_sentiment",
        "title": "Policy Sentiment",
        "context": "Parliamentary speech and policy commentary",
        "description": "Code policy support, criticism, and mixed evaluations in short political texts.",
        "summary": "Checkbox, dropdown, Likert, and evidence textbox",
        "rows": 6,
    },
    "migration_framing": {
        "slug": "migration_framing",
        "title": "Migration Framing",
        "context": "News leads and campaign messaging",
        "description": "Identify humanitarian, economic, and security frames in migration coverage.",
        "summary": "Multi-label checkboxes, dominant frame dropdown, and evidence textbox",
        "rows": 6,
    },
    "campaign_rhetoric": {
        "slug": "campaign_rhetoric",
        "title": "Campaign Rhetoric",
        "context": "Stump speeches and campaign statements",
        "description": "Explore populist cues, anti-elite language, incivility, and tone.",
        "summary": "Checkboxes, incivility dropdown, Likert, and evidence textbox",
        "rows": 6,
    },
}

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

        .cb-hero-copy a {
            color: var(--cb-accent);
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

        .cb-demo-intro {
            color: var(--cb-muted);
            line-height: 1.65;
            font-size: 0.98rem;
            margin-bottom: 0.9rem;
        }

        .cb-demo-context {
            color: var(--cb-accent);
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }

        .cb-demo-copy {
            color: var(--cb-muted);
            line-height: 1.58;
            font-size: 0.94rem;
            min-height: 4.6rem;
            margin-bottom: 0.65rem;
        }

        .cb-demo-meta {
            color: var(--cb-ink);
            font-size: 0.8rem;
            line-height: 1.45;
            margin-bottom: 0.9rem;
        }

        .cb-session-notice {
            background: var(--cb-accent-soft);
            color: var(--cb-accent);
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            margin-bottom: 0.5rem;
            font-size: 0.92rem;
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

        .cb-footer a {
            color: #6f4a38 !important;
        }

        .cb-footer-divider {
            border-top: 1px solid var(--cb-border);
            margin-top: 0.8rem;
        }

        .cb-footer-credit {
            color: #857d74;
            font-size: 0.76rem !important;
            margin: 0;
        }

        .cb-footer-credit a {
            color: #6f4a38;
        }

        .st-key-footer_feedback button {
            background: none !important;
            border: none !important;
            box-shadow: none !important;
            color: var(--cb-accent) !important;
            font-size: 0.88rem !important;
            font-weight: 600 !important;
            padding: 0 !important;
        }

        .st-key-footer_feedback button:hover {
            text-decoration: underline;
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

        .cb-conditional-notice {
            border: 1px solid rgba(138, 79, 61, 0.18);
            border-radius: 16px;
            background: linear-gradient(180deg, rgba(237, 225, 215, 0.72), rgba(249, 246, 241, 0.92));
            padding: 0.95rem 1rem;
            margin: 0.2rem 0 0.4rem 0;
        }

        .cb-conditional-notice-title {
            color: var(--cb-accent);
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 0.3rem;
        }

        p.cb-conditional-notice-body,
        [data-testid="stMarkdownContainer"] p.cb-conditional-notice-body {
            color: var(--cb-ink);
            line-height: 1.5 !important;
            font-size: 0.8rem !important;
            margin: 0;
        }

        .cb-preview-surface-marker,
        .cb-preview-pane-marker {
            display: none;
        }

        [data-testid="stVerticalBlockBorderWrapper"]:has(.cb-preview-surface-marker) {
            border-color: rgba(138, 79, 61, 0.22);
            background:
                radial-gradient(circle at top right, rgba(237, 225, 215, 0.78), transparent 34%),
                linear-gradient(180deg, rgba(244, 238, 230, 0.96), rgba(250, 247, 242, 0.96));
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7), 0 12px 30px rgba(72, 53, 34, 0.05);
        }

        [data-testid="stVerticalBlockBorderWrapper"]:has(.cb-preview-pane-marker) {
            border-color: rgba(138, 79, 61, 0.18);
            background: rgba(255, 252, 247, 0.9);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
        }

        .cb-preview-kicker {
            color: var(--cb-accent);
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .cb-example-list {
            display: grid;
            gap: 0.7rem;
        }

        .cb-example-card {
            border: 1px solid rgba(221, 213, 205, 0.9);
            border-radius: 12px;
            background: rgba(249, 246, 241, 0.72);
            padding: 0.7rem 0.85rem;
        }

        .cb-example-response {
            display: inline-flex;
            align-items: center;
            padding: 0.18rem 0.6rem;
            border-radius: 999px;
            background: var(--cb-accent-soft);
            color: var(--cb-accent);
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.3rem;
        }

        .cb-example-text {
            color: var(--cb-ink);
            line-height: 1.38;
            font-size: 0.87rem;
        }

        .cb-disclosure-copy {
            color: var(--cb-ink);
            line-height: 1.42;
            font-size: 0.88rem;
            padding-bottom: 0.5rem;
        }

        .cb-example-list {
            padding-bottom: 0.5rem;
        }

        .stSelectbox [data-testid="stWidgetLabel"] p,
        .stTextArea [data-testid="stWidgetLabel"] p,
        .stSegmentedControl [data-testid="stWidgetLabel"] p,
        .stButtonGroup [data-testid="stWidgetLabel"] p {
            color: #8a837b !important;
            font-size: 0.78rem !important;
            font-weight: 400 !important;
        }

        .stButtonGroup [data-testid="stWidgetLabel"],
        .stSegmentedControl [data-testid="stWidgetLabel"] {
            width: 100% !important;
            justify-content: space-between !important;
        }

        [data-testid="stButtonGroup"] [role="radiogroup"]:has(> button:nth-child(5):last-child) > button,
        [data-testid="stButtonGroup"] [role="radiogroup"]:has(> button:nth-child(6):last-child) > button {
            flex: 1 1 calc(100% / 3 - 0.5rem) !important;
            max-width: calc(100% / 3 - 0.5rem) !important;
        }

        [data-testid="stButtonGroup"] [role="radiogroup"]:has(> button:nth-child(7):last-child) > button,
        [data-testid="stButtonGroup"] [role="radiogroup"]:has(> button:nth-child(8):last-child) > button {
            flex: 1 1 calc(100% / 4 - 0.5rem) !important;
            max-width: calc(100% / 4 - 0.5rem) !important;
        }

        .stTextArea [data-baseweb="textarea"] {
            border: 1px solid var(--cb-border) !important;
            border-radius: 14px !important;
            background: rgba(249, 246, 241, 0.82) !important;
        }

        .stElementContainer:has(.stTextArea) {
            flex-shrink: 0 !important;
        }

        .stTextArea {
            margin-bottom: 0.55rem !important;
        }

        .stTextArea textarea {
            min-height: 7rem !important;
            color: var(--cb-ink) !important;
            -webkit-text-fill-color: var(--cb-ink) !important;
            background: transparent !important;
        }

        .stTextArea textarea::placeholder {
            color: #9a938b !important;
            opacity: 1 !important;
        }

        .cb-textbox-preview {
            min-height: 6.8rem;
            border: 1px solid var(--cb-border);
            border-radius: 14px;
            background: rgba(249, 246, 241, 0.82);
            padding: 0.95rem 1rem;
            color: #9a938b;
            line-height: 1.45;
            font-size: 0.92rem;
        }

        .cb-field-spacer {
            height: 0.35rem;
        }

        .streamlit-expanderHeader {
            font-family: "Lora", serif !important;
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            line-height: 1.3 !important;
            color: var(--cb-ink) !important;
        }

        .streamlit-expanderHeader p,
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary > div,
        [data-testid="stExpander"] summary > div p,
        [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p,
        [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] span {
            font-family: "Lora", serif !important;
        }

        .streamlit-expanderHeader:hover {
            color: var(--cb-accent) !important;
        }

        .streamlit-expanderHeader svg {
            color: var(--cb-accent) !important;
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--cb-border) !important;
            border-radius: 16px !important;
            background: rgba(255, 255, 255, 0.4) !important;
            overflow: hidden;
        }

        [data-testid="stExpander"] details {
            border: none !important;
        }

        [data-testid="stExpander"] summary {
            padding: 0.05rem 0.15rem !important;
        }

        [data-testid="stExpanderDetails"] {
            padding-top: 0.5rem !important;
        }

        .cb-toolbar-inline {
            color: var(--cb-ink);
            font-size: 1rem;
            line-height: 1.35;
            margin: 0.1rem 0 0 0;
        }

        .cb-toolbar-inline-meta {
            color: var(--cb-muted);
            font-size: 0.82rem;
        }

        p.cb-toolbar-progress,
        [data-testid="stMarkdownContainer"] p.cb-toolbar-progress {
            color: #8a837b;
            font-size: 0.62rem !important;
            font-weight: 400 !important;
            line-height: 1.2 !important;
            margin: 0.12rem 0 0.24rem 0;
        }

        .cb-metadata-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 8px 0 14px 0;
        }

        .cb-metadata-chip {
            display: inline-flex;
            align-items: baseline;
            gap: 6px;
            background: #f5f3ee;
            border: 1px solid #e7e5e0;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.82rem;
            line-height: 1.3;
        }

        .cb-metadata-key {
            color: #8a837b;
            font-weight: 600;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }

        .cb-metadata-value {
            color: var(--cb-ink);
        }

        p.cb-secondary-copy,
        [data-testid="stMarkdownContainer"] p.cb-secondary-copy {
            color: #8a837b;
            font-size: 0.72rem !important;
            font-weight: 400 !important;
            line-height: 1.2 !important;
            margin: 0.14rem 0 0.38rem 0;
        }

        p.cb-utility-subheading,
        [data-testid="stMarkdownContainer"] p.cb-utility-subheading {
            font-family: "Lora", serif !important;
            color: var(--cb-ink);
            font-size: 0.88rem !important;
            font-weight: 600 !important;
            line-height: 1.25 !important;
            margin: 0 0 0.35rem 0;
        }

        .st-key-annotation_prev button p,
        .st-key-annotation_next button p,
        .st-key-utility_edit_codebook button p,
        .st-key-utility_prompt_preview button p,
        .st-key-utility_download_data button p,
        .st-key-utility_download_codebook button p {
            font-size: 0.92rem !important;
        }

        .st-key-annotation_prev button,
        .st-key-annotation_next button,
        .st-key-preview_previous button,
        .st-key-preview_next button {
            min-height: 2.4rem !important;
            padding-top: 0.35rem !important;
            padding-bottom: 0.35rem !important;
        }

        .st-key-preview_previous button p,
        .st-key-preview_next button p {
            font-size: 0.92rem !important;
        }

        .st-key-annotation_progress,
        .st-key-preview_progress {
            max-width: 78%;
            margin-left: auto;
            margin-right: auto;
        }

        .st-key-annotation_progress {
            margin-top: -0.15rem;
            margin-bottom: -0.2rem;
        }

        .st-key-preview_progress {
            margin-top: -0.15rem;
            margin-bottom: -0.1rem;
        }

        .st-key-annotation_progress [data-baseweb="slider"] *,
        .st-key-preview_progress [data-baseweb="slider"] * {
            font-size: 0.82rem !important;
        }

        p.cb-section-title,
        [data-testid="stMarkdownContainer"] p.cb-section-title {
            font-family: "Lora", serif !important;
            color: var(--cb-ink);
            font-size: 1.1rem;
            font-weight: 600;
            line-height: 1.3;
            margin: 0 0 0.2rem 0;
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


def get_annotation_widget_key(index, full_column_name):
    return f"{index}_{full_column_name}"


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


def get_section_display_name(section_key, section_content):
    section_number = section_key.split("_")[-1]
    fallback = f"Section {section_number}" if section_number.isdigit() else section_key.replace("_", " ").title()
    return section_content.get("section_name") or fallback


def get_annotation_display_name(section_key, section_content, annotation_key, annotation):
    annotation_number = annotation_key.split("_")[-1]
    fallback = (
        f"Annotation {annotation_number}"
        if annotation_number.isdigit()
        else annotation_key.replace("_", " ").title()
    )
    annotation_name = annotation.get("name") or fallback
    return f"{get_section_display_name(section_key, section_content)} -> {annotation_name}"


def serialize_condition_target(section_key, annotation_key):
    return f"{section_key}::{annotation_key}"


def deserialize_condition_target(reference):
    if not reference or "::" not in str(reference):
        return None, None
    section_key, annotation_key = str(reference).split("::", 1)
    if not section_key or not annotation_key:
        return None, None
    return section_key, annotation_key


def get_annotation_entries(schema):
    entries = []
    for section_key, section_content in get_schema_sections(schema):
        for annotation_key in get_sorted_annotation_keys(section_content):
            annotation = section_content.get("annotations", {}).get(annotation_key, {})
            entries.append((section_key, section_content, annotation_key, annotation))
    return entries


def get_annotation_lookup(schema):
    return {
        (section_key, annotation_key): (section_content, annotation)
        for section_key, section_content, annotation_key, annotation in get_annotation_entries(schema)
    }


def get_annotation_condition(annotation):
    condition = annotation.get("condition")
    if not isinstance(condition, dict):
        return None

    section_key = condition.get("section_key")
    annotation_key = condition.get("annotation_key")
    if not section_key or not annotation_key:
        return None

    return {
        "section_key": section_key,
        "annotation_key": annotation_key,
        "value": condition.get("value"),
    }


def normalize_annotation_response_value(annotation, value):
    if pd.isna(value):
        return None

    annotation_type = annotation.get("type", "checkbox")
    if annotation_type == "checkbox":
        lowered = str(value).strip().lower()
        if lowered in {"1", "true", "yes"}:
            return 1
        if lowered in {"0", "false", "no"}:
            return 0
        return value

    if annotation_type == "likert":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    if annotation_type == "textbox":
        return str(value).strip()

    return str(value)


def get_condition_response_options(annotation, include_current=None):
    annotation_type = annotation.get("type", "checkbox")

    if annotation_type == "checkbox":
        options = [1, 0]
    elif annotation_type == "dropdown":
        options = list(annotation.get("options", []))
    elif annotation_type == "likert":
        min_value = int(annotation.get("min_value", 0))
        max_value = int(annotation.get("max_value", 5))
        if min_value > max_value:
            min_value, max_value = max_value, min_value
        options = list(range(min_value, max_value + 1))
    else:
        return None

    normalized_current = normalize_annotation_response_value(annotation, include_current)
    if normalized_current is not None and normalized_current not in options:
        options = [normalized_current] + options

    return options


def format_condition_value(annotation, value):
    normalized_value = normalize_annotation_response_value(annotation, value)
    if normalized_value is None:
        return "an answer"

    if annotation.get("type") == "checkbox":
        return "Yes" if normalized_value == 1 else "No"

    return str(normalized_value)


def get_annotation_condition_summary(schema, annotation):
    condition = get_annotation_condition(annotation)
    if not condition:
        return ""

    target_entry = get_annotation_lookup(schema).get((condition["section_key"], condition["annotation_key"]))
    if not target_entry:
        return "Condition saved, but the trigger annotation is missing."

    target_section_content, target_annotation = target_entry
    target_label = get_annotation_display_name(
        condition["section_key"],
        target_section_content,
        condition["annotation_key"],
        target_annotation,
    )
    expected_value = format_condition_value(target_annotation, condition.get("value"))
    return f"Shown only when {target_label} = {expected_value}"


def get_condition_requirement_text(schema, condition):
    target_entry = get_annotation_lookup(schema).get((condition["section_key"], condition["annotation_key"]))
    if not target_entry:
        return "the codebook's prerequisite response has been recorded"

    target_section_content, target_annotation = target_entry
    target_name = target_annotation.get("name") or get_annotation_display_name(
        condition["section_key"],
        target_section_content,
        condition["annotation_key"],
        target_annotation,
    )
    section_name = get_section_display_name(condition["section_key"], target_section_content)
    expected_value = format_condition_value(target_annotation, condition.get("value"))
    return f'the recorded response to "{target_name}" in "{section_name}" is "{expected_value}"'


def render_conditional_notice(title, body):
    safe_title = html_module.escape(title)
    safe_body = html_module.escape(body)
    st.markdown(
        (
            '<div class="cb-conditional-notice">'
            f'<div class="cb-conditional-notice-title">{safe_title}</div>'
            f'<p class="cb-conditional-notice-body">{safe_body}</p>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def get_section_condition_notice(schema, section_key, section_content):
    requirements = []
    seen_requirements = set()

    for annotation_key in get_sorted_annotation_keys(section_content):
        annotation = section_content.get("annotations", {}).get(annotation_key, {})
        condition = get_annotation_condition(annotation)
        if not condition:
            continue

        requirement_text = get_condition_requirement_text(schema, condition)
        if requirement_text not in seen_requirements:
            seen_requirements.add(requirement_text)
            requirements.append(requirement_text)

    if not requirements:
        return (
            "Section conditional on an earlier answer",
            "This section has no active questions yet because it is conditional on an earlier response.",
        )

    if len(requirements) == 1:
        return (
            "Section conditional on an earlier answer",
            f'This section is shown only when {requirements[0]}.',
        )

    return (
        "Section conditional on earlier answers",
        "This section contains conditional questions. It is shown only when one of these conditions is met: "
        + "; ".join(requirements)
        + ".",
    )


def get_annotation_condition_notice(schema, annotation):
    condition = get_annotation_condition(annotation)
    if not condition:
        return None
    requirement_text = get_condition_requirement_text(schema, condition)
    return (
        "Question conditional on an earlier answer",
        f"This question is shown only when {requirement_text}.",
    )


def get_available_condition_sources(schema, current_section_key, current_annotation_key):
    sources = []
    for section_key, section_content, annotation_key, annotation in get_annotation_entries(schema):
        if section_key == current_section_key and annotation_key == current_annotation_key:
            break
        sources.append((section_key, section_content, annotation_key, annotation))
    return sources


def build_annotation_condition(schema, target_reference, raw_value):
    target_section_key, target_annotation_key = deserialize_condition_target(target_reference)
    if not target_section_key or not target_annotation_key:
        return None

    target_entry = get_annotation_lookup(schema).get((target_section_key, target_annotation_key))
    if not target_entry:
        return None

    _, target_annotation = target_entry
    normalized_value = normalize_annotation_response_value(target_annotation, raw_value)
    if normalized_value is None or (target_annotation.get("type") == "textbox" and normalized_value == ""):
        return None

    return {
        "section_key": target_section_key,
        "annotation_key": target_annotation_key,
        "value": normalized_value,
    }


def remove_conditions_referencing_target(schema, target_section_key, target_annotation_key=None):
    for _, section_content, _, annotation in get_annotation_entries(schema):
        condition = get_annotation_condition(annotation)
        if not condition:
            continue

        matches_section = condition["section_key"] == target_section_key
        matches_annotation = (
            target_annotation_key is None or condition["annotation_key"] == target_annotation_key
        )
        if matches_section and matches_annotation:
            annotation.pop("condition", None)


def is_annotation_active(schema, section_key, annotation_key, annotation_values, lookup=None, visited=None):
    lookup = lookup or get_annotation_lookup(schema)
    current_entry = lookup.get((section_key, annotation_key))
    if not current_entry:
        return True

    section_content, annotation = current_entry
    condition = get_annotation_condition(annotation)
    if not condition:
        return True

    target_key = (condition["section_key"], condition["annotation_key"])
    if target_key == (section_key, annotation_key):
        return True

    target_entry = lookup.get(target_key)
    if not target_entry:
        return True

    visited = visited or set()
    if (section_key, annotation_key) in visited:
        return True

    target_section_content, target_annotation = target_entry
    if not is_annotation_active(
        schema,
        condition["section_key"],
        condition["annotation_key"],
        annotation_values,
        lookup=lookup,
        visited=visited | {(section_key, annotation_key)},
    ):
        return False

    target_column_name = get_annotation_column_name(target_section_content, target_annotation)
    actual_value = normalize_annotation_response_value(target_annotation, annotation_values.get(target_column_name))
    expected_value = normalize_annotation_response_value(target_annotation, condition.get("value"))

    if actual_value is None:
        return False
    if target_annotation.get("type") == "textbox" and actual_value == "":
        return False

    return actual_value == expected_value


def get_active_annotations(schema, section_key, section_content, annotation_values):
    lookup = get_annotation_lookup(schema)
    active_annotations = []

    for annotation_key in get_sorted_annotation_keys(section_content):
        annotation = section_content.get("annotations", {}).get(annotation_key, {})
        if is_annotation_active(schema, section_key, annotation_key, annotation_values, lookup=lookup):
            active_annotations.append((annotation_key, annotation))

    return active_annotations


def sync_annotation_state_from_widgets(index, sections):
    annotations = st.session_state.get("annotations", {})

    for _, section_content in sections:
        for annotation in section_content.get("annotations", {}).values():
            full_column_name = get_annotation_column_name(section_content, annotation)
            widget_key = get_annotation_widget_key(index, full_column_name)
            if widget_key not in st.session_state:
                continue

            widget_value = st.session_state[widget_key]
            annotation_type = annotation.get("type", "checkbox")

            if annotation_type == "checkbox":
                annotations[full_column_name] = 1 if widget_value else 0
            elif annotation_type == "dropdown":
                annotations[full_column_name] = widget_value if widget_value else None
            else:
                annotations[full_column_name] = widget_value

    st.session_state.annotations = annotations


def clear_inactive_annotation_values(schema, sections, annotation_values, index):
    lookup = get_annotation_lookup(schema)
    changed = False

    for section_key, section_content in sections:
        for annotation_key, annotation in section_content.get("annotations", {}).items():
            if is_annotation_active(schema, section_key, annotation_key, annotation_values, lookup=lookup):
                continue

            full_column_name = get_annotation_column_name(section_content, annotation)
            if annotation_values.get(full_column_name) is not None:
                annotation_values[full_column_name] = None
                changed = True

            st.session_state.pop(get_annotation_widget_key(index, full_column_name), None)

    if changed:
        st.session_state.annotations = annotation_values


def get_section_completion(schema, section_key, section_content, annotation_values):
    annotations = get_active_annotations(schema, section_key, section_content, annotation_values)
    total = len(annotations)
    completed = 0

    for _, annotation in annotations:
        full_column_name = get_annotation_column_name(section_content, annotation)
        if is_answered_value(annotation_values.get(full_column_name)):
            completed += 1

    return completed, total


def get_completed_sections(schema, sections, annotation_values):
    completed_sections = 0
    for section_key, section_content in sections:
        completed, total = get_section_completion(schema, section_key, section_content, annotation_values)
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
        "annotation_progress",
        "_next_annotation_progress",
        "preview_progress",
        "_annotation_cache_key",
        "_pending_auto_save",
        "csv_uploader",
        "json_uploader",
        "codebook_versions",
        "_pending_compare_left",
        "_pending_compare_right",
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)

    st.session_state.page = "landing"


def load_demo_task(demo_key):
    demo = DEMO_TASKS.get(demo_key)
    if demo is None:
        st.error("That demo task is not available.")
        return

    demo_dir = DEMO_TASKS_DIR / demo["slug"]
    schema_path = demo_dir / "codebook.json"
    data_path = demo_dir / "data.csv"

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        csv_bytes = data_path.read_bytes()
        demo_df = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as exc:
        st.error(f"Could not load the demo task: {exc}")
        return

    uploaded_file = io.BytesIO(csv_bytes)
    uploaded_file.name = data_path.name

    reset_working_session()
    st.session_state.custom_schema = schema
    st.session_state.uploaded_file = uploaded_file
    st.session_state.column_names = demo_df.columns.tolist()
    st.session_state.data = demo_df
    st.session_state.index = 1

    st.session_state.data = process_data(st.session_state.uploaded_file, schema["text_column"])
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
    queue_auto_save()
    st.rerun()


def render_demo_task_section(saved_data):
    st.markdown("#### Try a demo task")
    st.markdown(
        '<div class="cb-demo-intro">Load a sample dataset and matching CodeBook drawn from familiar '
        "computational social science and political communication workflows. You can annotate a few texts, inspect "
        "or edit the CodeBook, and export results before preparing your own materials.</div>",
        unsafe_allow_html=True,
    )

    if saved_data:
        st.caption("Loading a demo starts a fresh in-browser working session and replaces the currently saved draft.")

    demo_columns = st.columns(len(DEMO_TASKS), gap="medium")
    for column, (demo_key, demo) in zip(demo_columns, DEMO_TASKS.items()):
        with column:
            with st.container(border=True):
                st.markdown(f'<div class="cb-demo-context">{demo["context"]}</div>', unsafe_allow_html=True)
                st.markdown(f"##### {demo['title']}")
                st.markdown(f'<div class="cb-demo-copy">{demo["description"]}</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="cb-demo-meta">{demo["summary"]}<br>{demo["rows"]} sample texts</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Try this demo", key=f"demo_{demo_key}", use_container_width=True):
                    load_demo_task(demo_key)


@st.dialog("Start Fresh")
def confirm_start_fresh(saved_data):
    st.markdown("Starting fresh will **permanently clear** your saved session.")

    schema = saved_data.get("custom_schema")
    csv_str = saved_data.get("data_csv")

    if schema or csv_str:
        st.markdown("Download your work before continuing:")
        if csv_str:
            st.download_button(
                label="Download Annotated Data",
                data=csv_str.encode("utf-8"),
                file_name="ground-truth.csv",
                mime="text/csv",
                use_container_width=True,
            )
        if schema:
            codebook_bundle = build_codebook_bundle(schema)
            st.download_button(
                label="Download CodeBook",
                data=codebook_bundle,
                file_name="codebook.zip",
                mime="application/zip",
                use_container_width=True,
            )

    if st.button("Confirm", use_container_width=True, type="primary"):
        clear_save()
        reset_working_session()
        st.rerun()


FEEDBACK_REPO = "LorcanMcLaren/codebook-studio"
FEEDBACK_LABELS = {"Bug report": "bug", "Feature request": "enhancement", "General feedback": "feedback"}


@st.dialog("Send Feedback")
def feedback_dialog():
    feedback_type = st.selectbox(
        "Type",
        options=list(FEEDBACK_LABELS.keys()),
    )
    description = st.text_area(
        "Description",
        placeholder="Tell us what happened or what you'd like to see...",
        height=150,
    )
    screenshot = st.file_uploader(
        "Screenshot (optional)",
        type=["png", "jpg", "jpeg", "gif", "webp"],
    )
    contact = st.text_input(
        "Contact (optional)",
        placeholder="Email or GitHub username in case we need to follow up",
    )

    if st.button("Submit", use_container_width=True, type="primary"):
        if not description.strip():
            st.warning("Please add a description.")
            return

        token = st.secrets.get("GITHUB_TOKEN", "")
        if not token:
            st.error("Feedback submission is not configured. Please contact the maintainer.")
            return

        title = f"[{feedback_type}] {description.strip()[:80]}"
        body_parts = [f"**Type:** {feedback_type}", f"**Description:**\n{description.strip()}"]
        if contact.strip():
            body_parts.append(f"**Contact:** {contact.strip()}")

        api_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }

        # Upload screenshot to repo if provided, and embed the URL in the issue body
        if screenshot is not None:
            img_bytes = screenshot.getvalue()
            b64 = base64.b64encode(img_bytes).decode()
            ext = screenshot.name.rsplit(".", 1)[-1].lower()
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = f".github/feedback-assets/{ts}.{ext}"
            upload_payload = json.dumps({
                "message": f"Feedback screenshot ({ts})",
                "content": b64,
            }).encode()
            upload_req = urllib.request.Request(
                f"https://api.github.com/repos/{FEEDBACK_REPO}/contents/{path}",
                data=upload_payload,
                headers=api_headers,
                method="PUT",
            )
            try:
                resp = urllib.request.urlopen(upload_req)
                upload_data = json.loads(resp.read().decode())
                img_url = upload_data["content"]["download_url"]
                body_parts.append(f"**Screenshot:**\n\n![screenshot]({img_url})")
            except urllib.error.HTTPError:
                body_parts.append("*Screenshot was attached but failed to upload.*")

        body = "\n\n".join(body_parts)
        label = FEEDBACK_LABELS.get(feedback_type, "feedback")
        payload = json.dumps({"title": title, "body": body, "labels": [label]}).encode()

        req = urllib.request.Request(
            f"https://api.github.com/repos/{FEEDBACK_REPO}/issues",
            data=payload,
            headers=api_headers,
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            st.success("Thanks for your feedback!")
        except urllib.error.HTTPError:
            st.error("Something went wrong. Please try again later.")


def _resolve_item_title(index, data):
    """Return the title string for the current item, or None when no header column is set."""
    title_column = st.session_state.custom_schema.get("header_column") or ""
    if not title_column or title_column not in data.columns:
        return None
    value = data.iloc[index][title_column]
    if pd.isna(value):
        return None
    return str(value)


def _resolve_metadata_pairs(index, data):
    """Return a list of (column, value) pairs for the current item's metadata columns."""
    columns = st.session_state.custom_schema.get("metadata_columns") or []
    if not columns:
        return []
    row = data.iloc[index]
    pairs = []
    for column in columns:
        if column not in data.columns:
            continue
        value = row[column]
        if pd.isna(value):
            continue
        pairs.append((column, str(value)))
    return pairs


def render_metadata_strip(pairs):
    """Render a chip strip of label : value metadata pairs."""
    if not pairs:
        return
    chips = "".join(
        '<span class="cb-metadata-chip">'
        f'<span class="cb-metadata-key">{html_module.escape(label)}</span>'
        f'<span class="cb-metadata-value">{html_module.escape(value)}</span>'
        '</span>'
        for label, value in pairs
    )
    st.markdown(
        f'<div class="cb-metadata-strip">{chips}</div>',
        unsafe_allow_html=True,
    )


def render_annotation_toolbar(index, data, sections):
    current_title = _resolve_item_title(index, data)
    completed_sections = get_completed_sections(
        st.session_state.custom_schema,
        sections,
        st.session_state.annotations,
    )
    current_item = index + 1

    if "_next_annotation_progress" in st.session_state:
        st.session_state.annotation_progress = st.session_state.pop("_next_annotation_progress")
    elif "annotation_progress" not in st.session_state:
        st.session_state.annotation_progress = current_item

    with st.container(border=True):
        title_col, progress_col, nav_col = st.columns([0.42, 0.3, 0.28], gap="medium")

        with title_col:
            if current_title is not None:
                safe_title = html_module.escape(current_title)
                st.markdown(
                    f'<p class="cb-toolbar-inline"><span class="cb-toolbar-inline-meta">Item</span> '
                    f'{safe_title}</p>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<p class="cb-toolbar-inline"><span class="cb-toolbar-inline-meta">Item</span> '
                    f'{current_item}</p>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<p class="cb-toolbar-progress">{completed_sections}/{len(sections)} sections touched</p>',
                unsafe_allow_html=True,
            )

        with progress_col:
            scrubbed_index = st.slider(
                "Item progress",
                min_value=1,
                max_value=len(data),
                step=1,
                help="Drag to move quickly between items.",
                key="annotation_progress",
                label_visibility="collapsed",
            )
            if scrubbed_index != current_item:
                update_data(index, data)
                update_index(int(scrubbed_index))

        with nav_col:
            button_col1, button_col2 = st.columns(2, gap="small")
            with button_col1:
                if st.button("Prev", key="annotation_prev", use_container_width=True, disabled=index == 0):
                    update_data(index, data)
                    update_index(index)
            with button_col2:
                if st.button("Next", key="annotation_next", use_container_width=True, disabled=index >= len(data) - 1):
                    update_data(index, data)
                    update_index(index + 2)


_URL_RE = re.compile(r'https?://[^\s<>"]+')
_URL_TRAILING_PUNCT = ".,;:!?)\"'"


def _linkify_and_escape(text):
    """Escape HTML in text and convert URLs to clickable anchors."""
    if text is None:
        return ""
    text = str(text)
    if not text:
        return ""
    parts = []
    cursor = 0
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(_URL_TRAILING_PUNCT)
        if not url:
            continue
        parts.append(html_module.escape(text[cursor:match.start()]))
        safe_url = html_module.escape(url, quote=True)
        parts.append(
            f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{html_module.escape(url)}</a>'
        )
        cursor = match.start() + len(url)
    parts.append(html_module.escape(text[cursor:]))
    return "".join(parts).replace("\n", "<br>")


def render_text_pane(index, data):
    text_column = st.session_state.custom_schema["text_column"]
    current_text = data.iloc[index][text_column]
    safe_text = _linkify_and_escape(current_text)

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


def get_editor_preview_sample(header_column, text_column, metadata_columns=None):
    sample_title = "Sample item"
    sample_text = "Upload data to preview how annotators will read and label a real text."
    sample_index = 1
    total_items = 1
    metadata_columns = metadata_columns or []

    def _resolve_title(row):
        if not header_column:
            return None
        value = row.get(header_column)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return str(value)

    def _resolve_metadata(row):
        pairs = []
        for column in metadata_columns:
            value = row.get(column)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue
            pairs.append((column, str(value)))
        return pairs

    data = st.session_state.get("data")
    if data is not None and len(data) > 0:
        sample_row = data.iloc[0]
        return (
            _resolve_title(sample_row) if header_column else None,
            str(sample_row.get(text_column, sample_text)),
            sample_index,
            len(data),
            _resolve_metadata(sample_row),
        )

    uploaded_file = st.session_state.get("uploaded_file")
    if uploaded_file is not None:
        uploaded_file.seek(0)
        sample_df = pd.read_csv(uploaded_file, nrows=1)
        uploaded_file.seek(0)
        if not sample_df.empty:
            sample_row = sample_df.iloc[0]
            return (
                _resolve_title(sample_row) if header_column else None,
                str(sample_row.get(text_column, sample_text)),
                sample_index,
                total_items,
                _resolve_metadata(sample_row),
            )

    return sample_title if header_column else None, sample_text, sample_index, total_items, []


def render_editor_preview_annotation(annotation, key, condition_summary=""):
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
        st.text_area(label, help=tooltip, key=key, height=120, disabled=True, placeholder="Free-text response")

    if condition_summary:
        st.caption(condition_summary)

    if annotation.get("example"):
        if annotation["type"] == "textbox":
            st.markdown('<div class="cb-field-spacer"></div>', unsafe_allow_html=True)
        render_persistent_disclosure(
            "Examples",
            f"preview_examples__{key}",
            lambda: render_example_blocks(annotation["example"], annotation.get("type")),
        )


def format_example_response_for_display(response_value, annotation_type):
    if annotation_type == "checkbox":
        lowered = str(response_value).strip().lower()
        if lowered in {"1", "true", "yes"}:
            return "Yes"
        if lowered in {"0", "false", "no"}:
            return "No"
    return "" if response_value is None else str(response_value)


def sync_persistent_disclosure_state(state_key):
    widget_key = f"_widget_{state_key}"
    if widget_key in st.session_state:
        st.session_state[state_key] = st.session_state[widget_key]


def render_persistent_disclosure(label, state_key, render_content, default_open=True):
    widget_key = f"_widget_{state_key}"

    if state_key not in st.session_state:
        st.session_state[state_key] = default_open
    if widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state[state_key]

    with st.expander(
        label,
        expanded=st.session_state[state_key],
        key=widget_key,
        on_change=sync_persistent_disclosure_state,
        args=(state_key,),
    ):
        render_content()


def render_disclosure_copy(text):
    safe_text = _linkify_and_escape(text)
    st.markdown(f'<div class="cb-disclosure-copy">{safe_text}</div>', unsafe_allow_html=True)


def render_example_blocks(example_text, annotation_type):
    example_blocks = parse_example_blocks(example_text, annotation_type)
    if not example_blocks:
        return

    rendered_cards = []
    for idx, block in enumerate(example_blocks):
        text_value = str(block.get("text", "")).strip()
        response_value = format_example_response_for_display(
            block.get("response", ""),
            annotation_type,
        ).strip()
        safe_text = _linkify_and_escape(text_value)
        safe_response = html_module.escape(response_value or "Example")

        rendered_cards.append(
            '<div class="cb-example-card">'
            f'<div class="cb-example-response">{safe_response}</div>'
            f'<div class="cb-example-text">{safe_text}</div>'
            '</div>'
        )

    st.markdown(
        f'<div class="cb-example-list">{"".join(rendered_cards)}</div>',
        unsafe_allow_html=True,
    )


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


def get_condition_enabled_widget_key(section_key, annotation_key):
    return f"{section_key}_{annotation_key}_condition_enabled"


def get_condition_target_widget_key(section_key, annotation_key):
    return f"{section_key}_{annotation_key}_condition_target"


def get_condition_value_widget_key(section_key, annotation_key):
    return f"{section_key}_{annotation_key}_condition_value"


def get_example_editor_count_key(section_key, annotation_key):
    return f"{section_key}_{annotation_key}_example_count"


def get_example_editor_signature_key(section_key, annotation_key):
    return f"{section_key}_{annotation_key}_example_signature"


def get_example_text_widget_key(section_key, annotation_key, idx):
    return f"{section_key}_{annotation_key}_example_text_{idx}"


def get_example_response_widget_key(section_key, annotation_key, idx):
    return f"{section_key}_{annotation_key}_example_response_{idx}"


def build_example_blocks_from_state(section_key, annotation_key):
    blocks = []
    count = st.session_state.get(get_example_editor_count_key(section_key, annotation_key), 0)

    for idx in range(count):
        blocks.append(
            {
                "text": st.session_state.get(get_example_text_widget_key(section_key, annotation_key, idx), ""),
                "response": st.session_state.get(get_example_response_widget_key(section_key, annotation_key, idx), ""),
            }
        )

    return blocks


def example_editor_state_is_complete(section_key, annotation_key):
    count = st.session_state.get(get_example_editor_count_key(section_key, annotation_key))
    if count is None:
        return False

    for idx in range(count):
        text_key = get_example_text_widget_key(section_key, annotation_key, idx)
        response_key = get_example_response_widget_key(section_key, annotation_key, idx)
        if text_key not in st.session_state or response_key not in st.session_state:
            return False

    return True


def set_example_editor_state(section_key, annotation_key, blocks, raw_signature=None):
    count_key = get_example_editor_count_key(section_key, annotation_key)
    previous_count = st.session_state.get(count_key, 0)
    st.session_state[count_key] = len(blocks)

    for idx, block in enumerate(blocks):
        st.session_state[get_example_text_widget_key(section_key, annotation_key, idx)] = block.get("text", "")
        st.session_state[get_example_response_widget_key(section_key, annotation_key, idx)] = block.get("response", "")

    for idx in range(len(blocks), previous_count):
        st.session_state.pop(get_example_text_widget_key(section_key, annotation_key, idx), None)
        st.session_state.pop(get_example_response_widget_key(section_key, annotation_key, idx), None)

    if raw_signature is not None:
        st.session_state[get_example_editor_signature_key(section_key, annotation_key)] = raw_signature


def initialize_example_editor_state(section_key, annotation_key, annotation):
    raw_example = annotation.get("example", "")
    annotation_type = annotation.get("type")
    signature = f"{annotation_type}::{raw_example}"
    signature_key = get_example_editor_signature_key(section_key, annotation_key)

    parsed_blocks = parse_example_blocks(raw_example, annotation_type)
    blocks = [
        {
            "text": block.get("text", ""),
            "response": format_example_response_for_display(block.get("response", ""), annotation_type),
        }
        for block in parsed_blocks
    ]

    count_key = get_example_editor_count_key(section_key, annotation_key)
    current_count = st.session_state.get(count_key)

    if current_count is not None and current_count > len(blocks):
        all_widgets_present = all(
            get_example_text_widget_key(section_key, annotation_key, idx) in st.session_state
            and get_example_response_widget_key(section_key, annotation_key, idx) in st.session_state
            for idx in range(current_count)
        )
        if all_widgets_present:
            return

    should_refresh = st.session_state.get(signature_key) != signature
    should_refresh = should_refresh or current_count != len(blocks)

    if not should_refresh:
        for idx in range(len(blocks)):
            text_key = get_example_text_widget_key(section_key, annotation_key, idx)
            response_key = get_example_response_widget_key(section_key, annotation_key, idx)
            if text_key not in st.session_state or response_key not in st.session_state:
                should_refresh = True
                break

    if not should_refresh:
        return

    set_example_editor_state(section_key, annotation_key, blocks, raw_signature=signature)


def get_valid_example_response_options(annotation):
    annotation_type = annotation.get("type", "checkbox")

    if annotation_type == "checkbox":
        return ["Yes", "No"]
    if annotation_type == "dropdown":
        return [str(option) for option in annotation.get("options", []) if str(option).strip()]
    if annotation_type == "likert":
        min_value = int(annotation.get("min_value", 0))
        max_value = int(annotation.get("max_value", 5))
        if min_value > max_value:
            min_value, max_value = max_value, min_value
        return [str(value) for value in range(min_value, max_value + 1)]

    return None


def sanitize_example_editor_responses(section_key, annotation_key, annotation):
    valid_options = get_valid_example_response_options(annotation)
    if valid_options is None:
        return

    valid_set = set(valid_options)
    count = st.session_state.get(get_example_editor_count_key(section_key, annotation_key), 0)
    for idx in range(count):
        response_key = get_example_response_widget_key(section_key, annotation_key, idx)
        current_response = st.session_state.get(response_key, "")
        if current_response and str(current_response) not in valid_set:
            st.session_state[response_key] = ""


def _pending_example_delete_key(section_key, annotation_key):
    return f"_pending_example_delete_{section_key}_{annotation_key}"


def _apply_pending_example_delete(section_key, annotation_key, annotation):
    """Run at the top of render_example_editor, before any widgets render.

    Works from ``annotation["example"]`` — which ``sync_schema_editor_state_from_widgets``
    just refreshed from the widget state — so we don't depend on the widget
    session_state surviving the cross-rerun handoff. Clears widget keys and
    resets editor metadata so ``initialize_example_editor_state`` rebuilds from
    the updated ``annotation["example"]``.
    """
    pending_key = _pending_example_delete_key(section_key, annotation_key)
    if pending_key not in st.session_state:
        return
    delete_idx = st.session_state.pop(pending_key)

    annotation_type = annotation.get("type")
    blocks = parse_example_blocks(annotation.get("example", ""), annotation_type)
    if not (0 <= delete_idx < len(blocks)):
        return

    del blocks[delete_idx]

    count_key = get_example_editor_count_key(section_key, annotation_key)
    previous_count = st.session_state.get(count_key, 0)
    for idx in range(max(previous_count, len(blocks) + 1)):
        st.session_state.pop(get_example_text_widget_key(section_key, annotation_key, idx), None)
        st.session_state.pop(get_example_response_widget_key(section_key, annotation_key, idx), None)

    annotation["example"] = serialize_example_blocks(blocks, annotation_type)
    st.session_state.pop(count_key, None)
    st.session_state.pop(get_example_editor_signature_key(section_key, annotation_key), None)


def render_example_editor(section_key, annotation_key, annotation):
    _apply_pending_example_delete(section_key, annotation_key, annotation)
    initialize_example_editor_state(section_key, annotation_key, annotation)
    sanitize_example_editor_responses(section_key, annotation_key, annotation)
    valid_response_options = get_valid_example_response_options(annotation)

    st.markdown("###### Examples")
    st.caption(
        "Add example text after defining the annotation. Expected responses follow the "
        "current annotation settings and save back into the LLM-ready CodeBook format automatically."
    )

    example_blocks = build_example_blocks_from_state(section_key, annotation_key)
    if not example_blocks:
        st.caption("No examples yet.")

    for idx, _ in enumerate(example_blocks):
        with st.container(border=True):
            text_key = get_example_text_widget_key(section_key, annotation_key, idx)
            response_key = get_example_response_widget_key(section_key, annotation_key, idx)

            st.text_area(
                f"Example text {idx + 1}",
                key=text_key,
                help="A sample text that illustrates this annotation.",
                height=100,
            )
            if valid_response_options is None:
                st.text_input(
                    f"Expected response {idx + 1}",
                    key=response_key,
                    help="Enter the response value you would expect for this example.",
                )
            else:
                st.selectbox(
                    f"Expected response {idx + 1}",
                    options=[""] + valid_response_options,
                    key=response_key,
                    format_func=lambda value: "Select response" if value == "" else value,
                    help="Choose one of the responses currently allowed for this annotation.",
                )

            if st.button("Delete Example", key=f"delete_example_{section_key}_{annotation_key}_{idx}"):
                st.session_state[_pending_example_delete_key(section_key, annotation_key)] = idx
                st.rerun()

    if st.button("Add Example", key=f"add_example_{section_key}_{annotation_key}"):
        count_key = get_example_editor_count_key(section_key, annotation_key)
        new_idx = st.session_state.get(count_key, 0)
        st.session_state[count_key] = new_idx + 1
        st.session_state[get_example_text_widget_key(section_key, annotation_key, new_idx)] = ""
        st.session_state[get_example_response_widget_key(section_key, annotation_key, new_idx)] = ""
        st.rerun()


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
            annotation_min_key = f"{section_key}_{annotation_key}_min_value"
            annotation_max_key = f"{section_key}_{annotation_key}_max_value"
            annotation_options_key = f"{section_key}_{annotation_key}_options"
            condition_enabled_key = get_condition_enabled_widget_key(section_key, annotation_key)
            condition_target_key = get_condition_target_widget_key(section_key, annotation_key)
            condition_value_key = get_condition_value_widget_key(section_key, annotation_key)

            if annotation_name_key in st.session_state:
                annotation["name"] = st.session_state[annotation_name_key]
            if annotation_type_key in st.session_state:
                annotation["type"] = st.session_state[annotation_type_key]
            if annotation_tooltip_key in st.session_state:
                annotation["tooltip"] = st.session_state[annotation_tooltip_key]
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

            if st.session_state.get(condition_enabled_key):
                condition = build_annotation_condition(
                    schema,
                    st.session_state.get(condition_target_key),
                    st.session_state.get(condition_value_key),
                )
                if condition:
                    annotation["condition"] = condition
                elif "condition" in annotation:
                    annotation.pop("condition", None)
            elif condition_enabled_key in st.session_state and "condition" in annotation:
                annotation.pop("condition", None)

            example_count_key = get_example_editor_count_key(section_key, annotation_key)
            if example_editor_state_is_complete(section_key, annotation_key):
                annotation["example"] = serialize_example_blocks(
                    build_example_blocks_from_state(section_key, annotation_key),
                    annotation.get("type"),
                )


def render_schema_workflow_preview(schema, header_column, text_column, metadata_columns=None):
    sections = get_schema_sections(schema)
    if not sections:
        return

    metadata_columns = metadata_columns or schema.get("metadata_columns") or []
    sample_title, sample_text, sample_index, total_items, metadata_pairs = get_editor_preview_sample(
        header_column, text_column, metadata_columns
    )
    section_keys = [section_key for section_key, _ in sections]
    option_labels = {
        section_key: section_content.get("section_name") or f"Section {idx + 1}"
        for idx, (section_key, section_content) in enumerate(sections)
    }

    active_section = st.session_state.get("editor_preview_section")
    if active_section not in section_keys:
        active_section = section_keys[0]
        st.session_state.editor_preview_section = active_section

    if total_items > 1 and "preview_progress" not in st.session_state:
        st.session_state.preview_progress = min(sample_index, total_items)

    st.markdown("#### Annotation Workflow Preview")
    st.caption("This preview mirrors the annotation workspace using a sample text from your uploaded data.")

    with st.container(border=True):
        st.markdown('<div class="cb-preview-surface-marker"></div>', unsafe_allow_html=True)
        st.markdown('<div class="cb-preview-kicker">Preview workspace</div>', unsafe_allow_html=True)
        title_col, progress_col, nav_col = st.columns([0.42, 0.3, 0.28], gap="medium")

        with title_col:
            title_text = html_module.escape(sample_title) if sample_title else str(sample_index)
            st.markdown(
                f'<p class="cb-toolbar-inline"><span class="cb-toolbar-inline-meta">Item</span> '
                f'{title_text}</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<p class="cb-toolbar-progress">0/{len(sections)} sections touched</p>',
                unsafe_allow_html=True,
            )

        with progress_col:
            if total_items > 1:
                st.slider(
                    "Preview item progress",
                    min_value=1,
                    max_value=total_items,
                    step=1,
                    disabled=True,
                    key="preview_progress",
                    label_visibility="collapsed",
                )
            else:
                st.progress(1.0, text="1")

        with nav_col:
            button_col1, button_col2 = st.columns(2, gap="small")
            with button_col1:
                st.button("Prev", key="preview_previous", use_container_width=True, disabled=True)
            with button_col2:
                st.button("Next", key="preview_next", use_container_width=True, disabled=True)

    render_metadata_strip(metadata_pairs)

    preview_left, preview_right = st.columns([1.02, 0.98], gap="medium")

    with preview_left:
        with st.container(border=True, height=EDITOR_PREVIEW_TEXT_HEIGHT):
            st.markdown('<div class="cb-preview-pane-marker"></div>', unsafe_allow_html=True)
            st.markdown('<div class="cb-pane-label">Document text</div>', unsafe_allow_html=True)
            safe_text = _linkify_and_escape(sample_text)
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
        preview_annotations = [
            (annotation_key, preview_content.get("annotations", {}).get(annotation_key, {}))
            for annotation_key in get_sorted_annotation_keys(preview_content)
        ]
        checkbox_only = preview_annotations and all(annotation["type"] == "checkbox" for _, annotation in preview_annotations)

        with st.container(border=True, height=EDITOR_PREVIEW_SECTION_HEIGHT):
            st.markdown('<div class="cb-preview-pane-marker"></div>', unsafe_allow_html=True)
            st.markdown('<div class="cb-pane-label">Annotation section</div>', unsafe_allow_html=True)
            st.markdown(
                f'<p class="cb-section-title">{html_module.escape(option_labels[preview_section])}</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<p class="cb-secondary-copy">0/{len(preview_annotations)} responses completed in this section</p>',
                unsafe_allow_html=True,
            )

            section_instruction = preview_content.get("section_instruction", "")
            if section_instruction:
                render_persistent_disclosure(
                    "Instructions",
                    f"preview_instructions__{preview_section}",
                    lambda: render_disclosure_copy(section_instruction),
                )

            if checkbox_only:
                checkbox_columns = st.columns(2, gap="medium")
                for idx, (_, annotation) in enumerate(preview_annotations):
                    with checkbox_columns[idx % 2]:
                        render_editor_preview_annotation(
                            annotation,
                            key=f"preview_{preview_section}_{idx}",
                            condition_summary=get_annotation_condition_summary(schema, annotation),
                        )
            else:
                for idx, (_, annotation) in enumerate(preview_annotations):
                    render_editor_preview_annotation(
                        annotation,
                        key=f"preview_{preview_section}_{idx}",
                        condition_summary=get_annotation_condition_summary(schema, annotation),
                    )


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
    widget_key = get_annotation_widget_key(index, full_column_name)

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
            placeholder="Enter free-text response...",
        )
        st.session_state.annotations[full_column_name] = annotated

    if config.get("example"):
        if config["type"] == "textbox":
            st.markdown('<div class="cb-field-spacer"></div>', unsafe_allow_html=True)
        render_persistent_disclosure(
            "Examples",
            f"annotation_examples__{full_column_name}",
            lambda: render_example_blocks(config["example"], config.get("type")),
        )


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
    lookup = get_annotation_lookup(st.session_state.custom_schema)
    annotation_status = []
    for annotation_key in get_sorted_annotation_keys(section_content):
        annotation = section_content.get("annotations", {}).get(annotation_key, {})
        is_active = is_annotation_active(
            st.session_state.custom_schema,
            selected_section,
            annotation_key,
            st.session_state.annotations,
            lookup=lookup,
        )
        annotation_status.append((annotation_key, annotation, is_active))

    annotations = [(key, annotation) for key, annotation, is_active in annotation_status if is_active]
    has_inactive = any(not is_active for _, _, is_active in annotation_status)
    checkbox_only = (
        annotations
        and not has_inactive
        and all(annotation["type"] == "checkbox" for _, annotation in annotations)
    )

    with st.container(border=True, height=ANNOTATION_PANE_HEIGHT):
        st.markdown('<div class="cb-pane-label">Annotation section</div>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="cb-section-title">{html_module.escape(option_labels[selected_section])}</p>',
            unsafe_allow_html=True,
        )
        completion_placeholder = st.empty()

        if not annotations:
            notice_title, notice_body = get_section_condition_notice(
                st.session_state.custom_schema,
                selected_section,
                section_content,
            )
            render_conditional_notice(notice_title, notice_body)
        else:
            section_instruction = section_content.get("section_instruction", "")
            if section_instruction:
                render_persistent_disclosure(
                    "Instructions",
                    f"annotation_instructions__{selected_section}",
                    lambda: render_disclosure_copy(section_instruction),
                )

            if checkbox_only:
                checkbox_columns = st.columns(2, gap="medium")
                for idx, (_, config) in enumerate(annotations):
                    full_column_name = get_annotation_column_name(section_content, config)
                    with checkbox_columns[idx % 2]:
                        render_annotation_input(section_content, config, full_column_name, index)
            else:
                for _, config, is_active in annotation_status:
                    if is_active:
                        full_column_name = get_annotation_column_name(section_content, config)
                        render_annotation_input(section_content, config, full_column_name, index)
                    else:
                        notice = get_annotation_condition_notice(st.session_state.custom_schema, config)
                        if notice:
                            render_conditional_notice(*notice)

        completed, total = get_section_completion(
            st.session_state.custom_schema,
            selected_section,
            section_content,
            st.session_state.annotations,
        )
        completion_placeholder.markdown(
            f'<p class="cb-secondary-copy">{completed}/{total} responses completed in this section</p>',
            unsafe_allow_html=True,
        )

def render_annotation_utilities(index, data):
    with st.expander("Utilities", expanded=True):
        utility_col1, utility_col2 = st.columns(2, gap="large")

        with utility_col1:
            st.markdown('<p class="cb-utility-subheading">Workflow</p>', unsafe_allow_html=True)
            if st.button("Edit CodeBook", key="utility_edit_codebook", use_container_width=True):
                update_data(index, data)
                st.session_state.data = data
                st.session_state.page = "create_schema"
                queue_auto_save()
                st.rerun()

            if st.button("Preview LLM Prompts", key="utility_prompt_preview", use_container_width=True):
                update_data(index, data)
                st.session_state.data = data
                st.session_state.previous_page = "annotate"
                st.session_state.page = "prompt_preview"
                queue_auto_save()
                st.rerun()

        with utility_col2:
            st.markdown('<p class="cb-utility-subheading">Export</p>', unsafe_allow_html=True)
            csv_data = st.session_state.data.copy()
            update_data(index, csv_data)
            csv = csv_data.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Annotated Data",
                key="utility_download_data",
                data=csv,
                file_name="ground-truth.csv",
                mime="text/csv",
                use_container_width=True,
            )

            codebook_bundle = build_codebook_bundle(st.session_state.custom_schema)
            st.download_button(
                label="Download CodeBook",
                key="utility_download_codebook",
                data=codebook_bundle,
                file_name="codebook.zip",
                mime="application/zip",
                use_container_width=True,
            )

def process_data(uploaded_file, text_column):
    if 'data' not in st.session_state or st.session_state.data is None:
        if uploaded_file is None:
            raise ValueError("No uploaded data is available in this session.")
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
                    df[full_column_name] = pd.Series([None] * len(df), dtype=object, index=df.index)
                elif df[full_column_name].dtype != object:
                    df[full_column_name] = df[full_column_name].astype(object).where(df[full_column_name].notna(), None)

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
    sync_annotation_state_from_widgets(index, sections)
    clear_inactive_annotation_values(st.session_state.custom_schema, sections, st.session_state.annotations, index)

    render_annotation_toolbar(index, data, sections)
    metadata_pairs = _resolve_metadata_pairs(index, data)
    if metadata_pairs:
        render_metadata_strip(metadata_pairs)
    else:
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
            '<div class="cb-hero-copy">CodeBook Studio is built for computational social science workflows '
            'that need a consistent annotation scheme across human coding, LLM prompt preview, and research '
            'reporting. Exported JSON CodeBooks can be used directly in '
            '<a href="https://github.com/LorcanMcLaren/codebook-lab" target="_blank">CodeBook Lab</a> '
            'to run and evaluate LLM annotation experiments from the same task definition.<br><br>'
            'If you use CodeBook Studio in research, please cite the software '
            'repository: <a href="https://github.com/LorcanMcLaren/codebook-studio" target="_blank">'
            'github.com/LorcanMcLaren/codebook-studio</a>.</div>',
            unsafe_allow_html=True,
        )

    with right_column:
        with st.container(border=True):
            st.markdown("### Get Started")

            if saved_data:
                display_time = format_saved_session_timestamp(saved_data.get("updated_at", ""))
                session_msg = (
                    f"Saved session available from {display_time}."
                    if display_time
                    else "Saved session available."
                )
                st.markdown(
                    f'<div class="cb-session-notice">{session_msg}</div>',
                    unsafe_allow_html=True,
                )
                resume_col, fresh_col = st.columns(2, gap="small")
                with resume_col:
                    if st.button("Resume Session", type="primary", use_container_width=True):
                        restore_session_state(saved_data)
                        st.rerun()
                with fresh_col:
                    if st.button("Start Fresh", use_container_width=True):
                        confirm_start_fresh(saved_data)
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
    render_demo_task_section(saved_data)

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

        header_column_default = st.session_state.custom_schema.get("header_column", "") or ""
        text_column_default = st.session_state.custom_schema.get("text_column", "")
        metadata_columns_default = list(
            st.session_state.custom_schema.get("metadata_columns", []) or []
        )

        HEADER_NONE_LABEL = "(no title — show item number only)"
        header_options = [HEADER_NONE_LABEL] + list(st.session_state.column_names)
        if header_column_default in st.session_state.column_names:
            header_index = header_options.index(header_column_default)
        else:
            header_index = 0

        header_choice = st.selectbox(
            "Header column",
            header_options,
            index=header_index,
            key="header_column_selector",
            help="Optional. The column used as a title or identifier for each text (displayed above the document during annotation). Choose the no-title option to show only the item number.",
        )
        header_column = "" if header_choice == HEADER_NONE_LABEL else header_choice

        text_column = st.selectbox(
            "Text column",
            st.session_state.column_names,
            index=st.session_state.column_names.index(text_column_default)
            if text_column_default in st.session_state.column_names
            else 0,
            key="text_column_selector",
            help="The column containing the main text content that annotators will read and annotate",
        )

        metadata_options = [
            col for col in st.session_state.column_names
            if col != header_column and col != text_column
        ]
        metadata_columns = st.multiselect(
            "Additional metadata columns",
            metadata_options,
            default=[col for col in metadata_columns_default if col in metadata_options],
            key="metadata_columns_selector",
            help="Optional. Extra CSV columns shown as label : value pairs above the document text during annotation (e.g. speaker, date, debate title).",
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
        st.session_state.custom_schema["metadata_columns"] = list(metadata_columns)
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
        remove_conditions_referencing_target(st.session_state.custom_schema, section_key)
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
            remove_conditions_referencing_target(
                st.session_state.custom_schema,
                section_key,
                annotation_key,
            )

        annotation_keys = get_sorted_annotation_keys(st.session_state.custom_schema[section_key])
        editor_state_key = get_annotation_editor_state_key(section_key)
        if st.session_state.get(editor_state_key) == annotation_key:
            st.session_state[editor_state_key] = annotation_keys[0] if annotation_keys else None

        st.session_state.annotations_count[section_key] = len(annotation_keys)
        st.rerun()

    render_schema_workflow_preview(
        st.session_state.custom_schema, header_column, text_column, metadata_columns
    )

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
                            condition_summary = get_annotation_condition_summary(
                                st.session_state.custom_schema,
                                annotation,
                            )
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
                                if condition_summary:
                                    st.caption(condition_summary)

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
                                        st.rerun()
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

                            st.markdown("###### Conditional display")
                            st.caption(
                                "Optional. Conditional annotations only appear when an earlier annotation has the chosen response."
                            )

                            saved_condition = get_annotation_condition(annotation)
                            available_sources = get_available_condition_sources(
                                st.session_state.custom_schema,
                                section_key,
                                selected_annotation_key,
                            )
                            source_labels = {
                                serialize_condition_target(source_section_key, source_annotation_key): get_annotation_display_name(
                                    source_section_key,
                                    source_section_content,
                                    source_annotation_key,
                                    source_annotation,
                                )
                                for source_section_key, source_section_content, source_annotation_key, source_annotation in available_sources
                            }
                            existing_reference = None
                            if saved_condition:
                                existing_reference = serialize_condition_target(
                                    saved_condition["section_key"],
                                    saved_condition["annotation_key"],
                                )
                                target_entry = get_annotation_lookup(st.session_state.custom_schema).get(
                                    (saved_condition["section_key"], saved_condition["annotation_key"])
                                )
                                if existing_reference not in source_labels and target_entry:
                                    target_section_content, target_annotation = target_entry
                                    source_labels[existing_reference] = (
                                        get_annotation_display_name(
                                            saved_condition["section_key"],
                                            target_section_content,
                                            saved_condition["annotation_key"],
                                            target_annotation,
                                        )
                                        + " (currently saved)"
                                    )

                            condition_enabled_key = get_condition_enabled_widget_key(section_key, selected_annotation_key)
                            condition_target_key = get_condition_target_widget_key(section_key, selected_annotation_key)
                            condition_value_key = get_condition_value_widget_key(section_key, selected_annotation_key)

                            condition_enabled = st.checkbox(
                                "Make this annotation conditional",
                                key=condition_enabled_key,
                                value=bool(saved_condition),
                                disabled=not source_labels,
                                help="Conditions can target annotations that appear earlier in the workflow.",
                            )

                            if not source_labels:
                                annotation.pop("condition", None)
                                st.caption("Add an earlier annotation first if you want to make this one conditional.")
                            elif condition_enabled:
                                source_options = list(source_labels.keys())
                                default_reference = (
                                    existing_reference if existing_reference in source_labels else source_options[0]
                                )
                                selected_reference = st.selectbox(
                                    "Depends on",
                                    options=source_options,
                                    index=source_options.index(default_reference),
                                    key=condition_target_key,
                                    format_func=lambda ref: source_labels[ref],
                                )

                                target_section_key, target_annotation_key = deserialize_condition_target(selected_reference)
                                target_section_content = st.session_state.custom_schema[target_section_key]
                                target_annotation = target_section_content["annotations"][target_annotation_key]
                                target_options = get_condition_response_options(
                                    target_annotation,
                                    include_current=saved_condition.get("value") if saved_condition else None,
                                )

                                if target_options is None:
                                    condition_value = st.text_input(
                                        "Show when response exactly matches",
                                        key=condition_value_key,
                                        value=(
                                            str(saved_condition.get("value", ""))
                                            if saved_condition
                                            and saved_condition["section_key"] == target_section_key
                                            and saved_condition["annotation_key"] == target_annotation_key
                                            else ""
                                        ),
                                        help="Textbox conditions match the response exactly after trimming whitespace.",
                                    )
                                else:
                                    default_value = (
                                        normalize_annotation_response_value(target_annotation, saved_condition.get("value"))
                                        if saved_condition
                                        and saved_condition["section_key"] == target_section_key
                                        and saved_condition["annotation_key"] == target_annotation_key
                                        else target_options[0]
                                    )
                                    condition_value = st.selectbox(
                                        "Show when response is",
                                        options=target_options,
                                        index=target_options.index(default_value)
                                        if default_value in target_options
                                        else 0,
                                        key=condition_value_key,
                                        format_func=lambda value: format_condition_value(target_annotation, value),
                                    )

                                condition = build_annotation_condition(
                                    st.session_state.custom_schema,
                                    selected_reference,
                                    condition_value,
                                )
                                if condition:
                                    annotation["condition"] = condition
                                    st.caption(get_annotation_condition_summary(st.session_state.custom_schema, annotation))
                                else:
                                    annotation.pop("condition", None)
                            else:
                                annotation.pop("condition", None)

                            render_example_editor(section_key, selected_annotation_key, annotation)

                            st.divider()
                            with st.container(border=True):
                                st.markdown('<div class="cb-preview-surface-marker"></div>', unsafe_allow_html=True)
                                st.markdown('<div class="cb-preview-kicker">Annotator view</div>', unsafe_allow_html=True)
                                st.markdown("###### Annotation preview")
                                st.caption(
                                    "This is how the annotation will appear to annotators during the workflow."
                                )
                                render_editor_preview_annotation(
                                    annotation,
                                    key=f"builder_preview_{section_key}_{selected_annotation_key}",
                                    condition_summary=get_annotation_condition_summary(
                                        st.session_state.custom_schema,
                                        annotation,
                                    ),
                                )

                st.divider()

        if st.button("Add New Section"):
            add_section()

        st.divider()
        version_count = len(st.session_state.get("codebook_versions", []))
        version_col_left, version_col_right = st.columns(2)
        with version_col_left:
            if st.button("Save Version", use_container_width=True, help="Snapshot the current codebook so you can compare or restore it later"):
                save_version_dialog()
        with version_col_right:
            history_label = (
                f"Version History ({version_count})" if version_count else "Version History"
            )
            if st.button(
                history_label,
                use_container_width=True,
                disabled=version_count == 0,
                help="View, compare, and restore saved versions" if version_count else "Save a version first to enable history",
            ):
                st.session_state.page = "version_history"
                queue_auto_save()
                st.rerun()

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
            uploaded_file = st.session_state.get("uploaded_file")
            st.session_state.data = process_data(uploaded_file, text_column)
            st.session_state.page = 'annotate'
            queue_auto_save()
            st.rerun()

    flush_queued_auto_save()


def update_data(index, data):
    for annotation_option in st.session_state.annotations:
        data.at[index, annotation_option] = st.session_state.annotations[annotation_option]

def update_index(new_index):
    st.session_state.index = new_index
    st.session_state._next_annotation_progress = new_index
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


@st.dialog("Save CodeBook Version")
def save_version_dialog():
    st.markdown(
        "Snapshot the current CodeBook so you can compare future edits against it or restore it later. "
        "Versions are stored locally in your browser alongside your saved session."
    )
    label = st.text_input(
        "Label (optional)",
        placeholder="e.g. baseline, after pilot round 1",
        key="_save_version_label",
    )
    if st.button("Save version", type="primary", use_container_width=True):
        snapshot = record_version(label)
        if snapshot is None:
            st.warning("There is no CodeBook to save yet.")
        else:
            st.session_state.pop("_save_version_label", None)
            queue_auto_save()
            st.toast("Version saved.")
            st.rerun()


def _clear_schema_editor_widget_state():
    """Drop cached editor widget values so a freshly-restored schema renders cleanly.

    The schema editor mirrors section/annotation widget values back into
    custom_schema on every render; if we restore a snapshot without clearing
    these, stale widget values clobber the restored fields.
    """
    keys_to_drop = [
        key for key in list(st.session_state.keys())
        if isinstance(key, str) and key.startswith("section_")
    ]
    for key in keys_to_drop:
        st.session_state.pop(key, None)
    st.session_state.pop("editor_preview_section", None)


@st.dialog("Restore Version")
def confirm_restore_version_dialog(version_id):
    version = get_version(version_id)
    if not version:
        st.warning("That version is no longer available.")
        return

    saved_at = _format_version_timestamp(version.get("saved_at"))
    label = version.get("label") or "(no label)"
    st.markdown(
        f"Restoring **{label}** ({saved_at}) will replace your current CodeBook draft. "
        "The saved versions list is unaffected — consider saving the current state first if you want to keep it."
    )

    if st.button("Restore", type="primary", use_container_width=True):
        _clear_schema_editor_widget_state()
        if restore_version(version_id):
            queue_auto_save()
            st.toast("Version restored.")
            st.session_state.page = "create_schema"
            st.rerun()


def _format_version_timestamp(value):
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return value


def _set_pending_compare(left_id, right_id):
    st.session_state._pending_compare_left = left_id
    st.session_state._pending_compare_right = right_id
    st.session_state.page = "version_compare"


def version_history_page():
    def go_to_editor():
        st.session_state.page = "create_schema"
        queue_auto_save()
        st.rerun()

    render_header(home_action=go_to_editor)

    _, body, _ = st.columns([0.08, 0.84, 0.08])
    with body:
        st.header("CodeBook Version History")
        st.markdown(
            "Each saved version is a complete snapshot of your CodeBook at the moment you clicked **Save Version**. "
            "Compare any two versions to see exactly what changed, or restore a version to roll back."
        )

        versions = list(st.session_state.get("codebook_versions", []))

        if not versions:
            st.info("No saved versions yet. Save a version from the CodeBook editor to get started.")
            if st.button("Back to CodeBook Editor"):
                go_to_editor()
            return

        sorted_versions = sorted(versions, key=lambda v: v.get("saved_at", ""), reverse=True)

        st.divider()
        st.markdown("**Compare two versions**")
        select_options = [
            (
                v["id"],
                f"{_format_version_timestamp(v.get('saved_at'))} — {v.get('label') or '(no label)'}",
            )
            for v in sorted_versions
        ]
        compare_col_left, compare_col_right, compare_col_button = st.columns([0.4, 0.4, 0.2])
        with compare_col_left:
            left = st.selectbox(
                "Older",
                options=[opt[0] for opt in select_options],
                format_func=lambda vid: dict(select_options)[vid],
                index=min(1, len(select_options) - 1),
                key="_compare_select_left",
            )
        with compare_col_right:
            right = st.selectbox(
                "Newer",
                options=[opt[0] for opt in select_options] + ["__current__"],
                format_func=lambda vid: "Current draft" if vid == "__current__" else dict(select_options)[vid],
                index=0,
                key="_compare_select_right",
            )
        with compare_col_button:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("Compare", use_container_width=True, type="primary"):
                if left == right:
                    st.warning("Pick two different versions.")
                else:
                    _set_pending_compare(left, right)
                    st.rerun()

        st.divider()
        st.markdown("**All versions**")

        for version in sorted_versions:
            with st.container(border=True):
                row_meta, row_actions = st.columns([0.65, 0.35])
                with row_meta:
                    label = version.get("label") or "(no label)"
                    st.markdown(f"**{label}**")
                    st.caption(_format_version_timestamp(version.get("saved_at")))
                with row_actions:
                    a, b, c = st.columns(3)
                    with a:
                        if st.button("Compare to current", key=f"cmp_cur_{version['id']}", use_container_width=True):
                            _set_pending_compare(version["id"], "__current__")
                            st.rerun()
                    with b:
                        if st.button("Restore", key=f"restore_{version['id']}", use_container_width=True):
                            confirm_restore_version_dialog(version["id"])
                    with c:
                        if st.button("Delete", key=f"del_{version['id']}", use_container_width=True):
                            delete_version(version["id"])
                            queue_auto_save()
                            st.toast("Version deleted.")
                            st.rerun()

        st.divider()
        if st.button("Back to CodeBook Editor"):
            go_to_editor()

    flush_queued_auto_save()


def _render_value(value):
    if value is None or value == "":
        return "_(empty)_"
    if isinstance(value, (list, dict)):
        return f"```\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```"
    text = str(value)
    if "\n" in text or len(text) > 80:
        return f"```\n{text}\n```"
    return text


DIFF_INSERT_STYLE = "background:#c6f6d5;color:#166534;padding:0 2px;border-radius:2px;"
DIFF_DELETE_STYLE = "background:#fecaca;color:#7f1d1d;padding:0 2px;border-radius:2px;text-decoration:line-through;"


def _tokenize_for_diff(text):
    """Split text into whitespace-preserving tokens for word-level diffing."""
    return re.findall(r"\S+|\s+", text)


def _format_diff_chunk(text, style):
    if not text:
        return ""
    escaped = html_module.escape(text).replace("\n", "<br>")
    return f'<span style="{style}">{escaped}</span>'


def _plain_chunk(text):
    if not text:
        return ""
    return html_module.escape(text).replace("\n", "<br>")


def _inline_text_diff(old, new):
    """Return ``(old_html, new_html)`` with word-level adds/removes highlighted."""
    old_tokens = _tokenize_for_diff(old or "")
    new_tokens = _tokenize_for_diff(new or "")
    matcher = SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)

    old_parts = []
    new_parts = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        old_chunk = "".join(old_tokens[i1:i2])
        new_chunk = "".join(new_tokens[j1:j2])
        if opcode == "equal":
            old_parts.append(_plain_chunk(old_chunk))
            new_parts.append(_plain_chunk(new_chunk))
        elif opcode == "delete":
            old_parts.append(_format_diff_chunk(old_chunk, DIFF_DELETE_STYLE))
        elif opcode == "insert":
            new_parts.append(_format_diff_chunk(new_chunk, DIFF_INSERT_STYLE))
        elif opcode == "replace":
            old_parts.append(_format_diff_chunk(old_chunk, DIFF_DELETE_STYLE))
            new_parts.append(_format_diff_chunk(new_chunk, DIFF_INSERT_STYLE))

    return "".join(old_parts), "".join(new_parts)


def _wrap_diff_block(inner_html, multiline=False):
    if not inner_html:
        return '<div style="color:#6b7280;font-style:italic;">(empty)</div>'
    if multiline:
        return (
            '<div style="background:#fafaf7;border:1px solid #e7e5e0;border-radius:4px;'
            'padding:8px 10px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;'
            f'font-size:0.85em;white-space:pre-wrap;">{inner_html}</div>'
        )
    return f'<div style="line-height:1.55;">{inner_html}</div>'


def _render_inline_text_diff(label, old, new):
    """Render a string field with inline word-level highlighting (Before/After)."""
    old_html, new_html = _inline_text_diff(old or "", new or "")
    multiline = ("\n" in (str(old or ""))) or ("\n" in (str(new or ""))) or len(str(old or "") + str(new or "")) > 120

    st.markdown(f"**{label}**")
    col_old, col_new = st.columns(2)
    with col_old:
        st.caption("Before")
        st.markdown(_wrap_diff_block(old_html, multiline=multiline), unsafe_allow_html=True)
    with col_new:
        st.caption("After")
        st.markdown(_wrap_diff_block(new_html, multiline=multiline), unsafe_allow_html=True)


def _render_structural_change(label, old, new):
    """Render non-text fields (lists, dicts, numbers) as JSON Before/After."""
    def fmt(value):
        if value is None or value == "":
            return '<div style="color:#6b7280;font-style:italic;">(empty)</div>'
        if isinstance(value, (list, dict)):
            text = json.dumps(value, indent=2, ensure_ascii=False)
        else:
            text = str(value)
        return _wrap_diff_block(_plain_chunk(text), multiline=True)

    st.markdown(f"**{label}**")
    col_old, col_new = st.columns(2)
    with col_old:
        st.caption("Before")
        st.markdown(fmt(old), unsafe_allow_html=True)
    with col_new:
        st.caption("After")
        st.markdown(fmt(new), unsafe_allow_html=True)


def _render_list_diff(label, old, new):
    """Render lists (e.g., dropdown options) with item-level add/remove highlights."""
    old_list = list(old or [])
    new_list = list(new or [])
    matcher = SequenceMatcher(a=old_list, b=new_list, autojunk=False)

    old_lines = []
    new_lines = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            for item in old_list[i1:i2]:
                rendered = _plain_chunk(str(item))
                old_lines.append(f"<div>• {rendered}</div>")
                new_lines.append(f"<div>• {rendered}</div>")
        elif opcode == "delete":
            for item in old_list[i1:i2]:
                old_lines.append(
                    f'<div>{_format_diff_chunk("• " + str(item), DIFF_DELETE_STYLE)}</div>'
                )
        elif opcode == "insert":
            for item in new_list[j1:j2]:
                new_lines.append(
                    f'<div>{_format_diff_chunk("• " + str(item), DIFF_INSERT_STYLE)}</div>'
                )
        elif opcode == "replace":
            for item in old_list[i1:i2]:
                old_lines.append(
                    f'<div>{_format_diff_chunk("• " + str(item), DIFF_DELETE_STYLE)}</div>'
                )
            for item in new_list[j1:j2]:
                new_lines.append(
                    f'<div>{_format_diff_chunk("• " + str(item), DIFF_INSERT_STYLE)}</div>'
                )

    st.markdown(f"**{label}**")
    col_old, col_new = st.columns(2)
    with col_old:
        st.caption("Before")
        st.markdown(
            _wrap_diff_block("".join(old_lines) or "", multiline=False),
            unsafe_allow_html=True,
        )
    with col_new:
        st.caption("After")
        st.markdown(
            _wrap_diff_block("".join(new_lines) or "", multiline=False),
            unsafe_allow_html=True,
        )


def _example_block_signature(block):
    """Stable string used to align old/new example blocks via SequenceMatcher."""
    return f"{(block.get('text') or '').strip()}{(block.get('response') or '')}"


def _render_example_block_card(block, kind):
    """kind in {'unchanged','added','removed','modified_before','modified_after'}."""
    text = block.get("text") or ""
    response = block.get("response")
    response_str = "" if response is None else str(response)

    if kind == "added":
        outer_style = "background:#dcfce7;border:1px solid #86efac;"
        badge = '<span style="color:#166534;font-weight:600;font-size:0.75em;">ADDED</span><br>'
    elif kind == "removed":
        outer_style = "background:#fee2e2;border:1px solid #fca5a5;"
        badge = '<span style="color:#7f1d1d;font-weight:600;font-size:0.75em;">REMOVED</span><br>'
    else:
        outer_style = "background:#fafaf7;border:1px solid #e7e5e0;"
        badge = ""

    body = (
        f"<div><strong>Text:</strong><br>{_plain_chunk(text) or '<em>(empty)</em>'}</div>"
        f'<div style="margin-top:6px;"><strong>Response:</strong> {_plain_chunk(response_str) or "<em>(empty)</em>"}</div>'
    )
    return (
        f'<div style="{outer_style}border-radius:4px;padding:8px 10px;margin-bottom:8px;'
        'font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:0.85em;'
        f'white-space:pre-wrap;">{badge}{body}</div>'
    )


def _render_example_block_diff(old_block, new_block):
    """Render a modified example block with inline word-level diff for Text and Response."""
    text_old, text_new = _inline_text_diff(old_block.get("text") or "", new_block.get("text") or "")
    resp_old_raw = "" if old_block.get("response") is None else str(old_block.get("response"))
    resp_new_raw = "" if new_block.get("response") is None else str(new_block.get("response"))
    resp_old, resp_new = _inline_text_diff(resp_old_raw, resp_new_raw)

    base_style = (
        "background:#fafaf7;border:1px solid #e7e5e0;border-radius:4px;padding:8px 10px;"
        "margin-bottom:8px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;"
        "font-size:0.85em;white-space:pre-wrap;"
    )

    def card(text_html, resp_html):
        return (
            f'<div style="{base_style}">'
            f"<div><strong>Text:</strong><br>{text_html or '<em>(empty)</em>'}</div>"
            f'<div style="margin-top:6px;"><strong>Response:</strong> {resp_html or "<em>(empty)</em>"}</div>'
            "</div>"
        )

    return card(text_old, resp_old), card(text_new, resp_new)


def _render_example_change(label, old, new, annotation_type=None):
    """Render an example field change block-by-block.

    Each example block is matched between old and new versions; modified blocks
    show inline word-level diff, added blocks get a green ADDED badge, removed
    blocks get a red REMOVED badge.
    """
    old_blocks = parse_example_blocks(old or "", annotation_type)
    new_blocks = parse_example_blocks(new or "", annotation_type)

    old_keys = [_example_block_signature(b) for b in old_blocks]
    new_keys = [_example_block_signature(b) for b in new_blocks]
    matcher = SequenceMatcher(a=old_keys, b=new_keys, autojunk=False)

    old_html_parts = []
    new_html_parts = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            for offset in range(i2 - i1):
                block = old_blocks[i1 + offset]
                card = _render_example_block_card(block, "unchanged")
                old_html_parts.append(card)
                new_html_parts.append(card)
        elif opcode == "delete":
            for block in old_blocks[i1:i2]:
                old_html_parts.append(_render_example_block_card(block, "removed"))
        elif opcode == "insert":
            for block in new_blocks[j1:j2]:
                new_html_parts.append(_render_example_block_card(block, "added"))
        elif opcode == "replace":
            # Pair up modified blocks; surplus on either side becomes add/remove.
            pair_count = min(i2 - i1, j2 - j1)
            for offset in range(pair_count):
                old_card, new_card = _render_example_block_diff(
                    old_blocks[i1 + offset], new_blocks[j1 + offset]
                )
                old_html_parts.append(old_card)
                new_html_parts.append(new_card)
            for block in old_blocks[i1 + pair_count : i2]:
                old_html_parts.append(_render_example_block_card(block, "removed"))
            for block in new_blocks[j1 + pair_count : j2]:
                new_html_parts.append(_render_example_block_card(block, "added"))

    st.markdown(f"**{label}**")
    col_old, col_new = st.columns(2)
    with col_old:
        st.caption("Before")
        st.markdown(
            "".join(old_html_parts) or _wrap_diff_block("", multiline=False),
            unsafe_allow_html=True,
        )
    with col_new:
        st.caption("After")
        st.markdown(
            "".join(new_html_parts) or _wrap_diff_block("", multiline=False),
            unsafe_allow_html=True,
        )


def _render_field_change(change, annotation=None):
    field = change["field"]
    label = field_label(field)
    old = change.get("old")
    new = change.get("new")

    if field == "example":
        annotation_type = None
        if isinstance(annotation, dict):
            annotation_type = annotation.get("type")
        _render_example_change(label, old, new, annotation_type=annotation_type)
    elif isinstance(old, list) or isinstance(new, list):
        _render_list_diff(label, old, new)
    elif isinstance(old, str) or isinstance(new, str) or old is None or new is None:
        _render_inline_text_diff(label, old, new)
    else:
        _render_structural_change(label, old, new)

    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)


def _annotation_summary(annotation):
    if not isinstance(annotation, dict):
        return ""
    name = annotation.get("name") or "(unnamed)"
    type_ = annotation.get("type") or ""
    return f"{name} ({type_})" if type_ else name


def _section_summary(section):
    if not isinstance(section, dict):
        return ""
    return section.get("section_name") or "(unnamed section)"


def version_compare_page():
    def go_back():
        st.session_state.page = "version_history"
        queue_auto_save()
        st.rerun()

    render_header(home_action=go_back)

    left_id = st.session_state.get("_pending_compare_left")
    right_id = st.session_state.get("_pending_compare_right")

    _, body, _ = st.columns([0.08, 0.84, 0.08])
    with body:
        st.header("Compare CodeBook Versions")

        if not left_id or not right_id:
            st.info("Choose two versions to compare from the Version History page.")
            if st.button("Back to Version History"):
                go_back()
            return

        def _resolve(version_id):
            if version_id == "__current__":
                return {
                    "label": "Current draft",
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                    "schema": st.session_state.get("custom_schema") or {},
                }
            return get_version(version_id)

        left = _resolve(left_id)
        right = _resolve(right_id)

        if not left or not right:
            st.warning("One of the selected versions is no longer available.")
            if st.button("Back to Version History"):
                go_back()
            return

        meta_left, meta_right = st.columns(2)
        with meta_left:
            st.markdown(f"**Before:** {left.get('label') or '(no label)'}")
            st.caption(_format_version_timestamp(left.get("saved_at")))
        with meta_right:
            st.markdown(f"**After:** {right.get('label') or '(no label)'}")
            st.caption(_format_version_timestamp(right.get("saved_at")))

        st.divider()

        changes = diff_schemas(left.get("schema"), right.get("schema"))
        if not changes:
            st.success("No differences between these versions.")
            if st.button("Back to Version History"):
                go_back()
            return

        top_changes, section_buckets = group_by_section(changes)

        if top_changes:
            with st.container(border=True):
                st.markdown("##### Header / Text columns")
                for change in top_changes:
                    _render_field_change(change)

        for bucket in section_buckets:
            section_key = bucket["section_key"]
            bucket_changes = bucket["changes"]

            section_added = next((c for c in bucket_changes if c["kind"] == "section_added"), None)
            section_removed = next((c for c in bucket_changes if c["kind"] == "section_removed"), None)

            if section_added:
                with st.container(border=True):
                    st.markdown(f"##### {section_key} — :green[Added]")
                    st.markdown(f"**Section:** {_section_summary(section_added['section'])}")
                    instruction = section_added["section"].get("section_instruction")
                    if instruction:
                        st.caption("Instruction")
                        st.markdown(_render_value(instruction))
                    annotations = section_added["section"].get("annotations") or {}
                    if annotations:
                        st.caption("Annotations")
                        for ann_key, ann in annotations.items():
                            st.markdown(f"- {ann_key}: {_annotation_summary(ann)}")
                    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
                continue

            if section_removed:
                with st.container(border=True):
                    st.markdown(f"##### {section_key} — :red[Removed]")
                    st.markdown(f"**Section:** {_section_summary(section_removed['section'])}")
                    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
                continue

            section_label = section_key
            for change in bucket_changes:
                if change["kind"] == "field_changed" and change["scope"] == "section" and change["field"] == "section_name":
                    section_label = f"{section_key} — {change['old']} → {change['new']}"
                    break

            with st.container(border=True):
                st.markdown(f"##### {section_label}")
                section_field_changes = [
                    c for c in bucket_changes if c["kind"] == "field_changed" and c["scope"] == "section"
                ]
                for change in section_field_changes:
                    _render_field_change(change)

                annotation_groups = {}
                for change in bucket_changes:
                    if change["kind"] in {"annotation_added", "annotation_removed"} or (
                        change["kind"] == "field_changed" and change["scope"] == "annotation"
                    ):
                        annotation_groups.setdefault(change["annotation_key"], []).append(change)

                for annotation_key, ann_changes in annotation_groups.items():
                    added = next((c for c in ann_changes if c["kind"] == "annotation_added"), None)
                    removed = next((c for c in ann_changes if c["kind"] == "annotation_removed"), None)

                    if added:
                        st.markdown(f"**{annotation_key} — :green[Added]:** {_annotation_summary(added['annotation'])}")
                        continue
                    if removed:
                        st.markdown(f"**{annotation_key} — :red[Removed]:** {_annotation_summary(removed['annotation'])}")
                        continue

                    st.markdown(f"**{annotation_key}**")
                    new_section = (right.get("schema") or {}).get(section_key) or {}
                    old_section = (left.get("schema") or {}).get(section_key) or {}
                    annotation_for_type = (
                        (new_section.get("annotations") or {}).get(annotation_key)
                        or (old_section.get("annotations") or {}).get(annotation_key)
                    )
                    for change in ann_changes:
                        _render_field_change(change, annotation=annotation_for_type)
                st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

        st.divider()
        if st.button("Back to Version History"):
            go_back()

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
elif st.session_state.page == 'version_history':
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide")
    version_history_page()
elif st.session_state.page == 'version_compare':
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide")
    version_compare_page()


# Add a footer
st.markdown('<div class="cb-footer-divider"></div>', unsafe_allow_html=True)
footer_left, footer_center, footer_right = st.columns(3)
with footer_left:
    st.markdown(
        '<p class="cb-footer-credit">Developed by '
        '<a href="https://www.lorcanmclaren.com" target="_blank">Lorcan McLaren</a></p>',
        unsafe_allow_html=True,
    )
with footer_center:
    if st.button("Send Feedback", key="footer_feedback", use_container_width=True):
        feedback_dialog()
