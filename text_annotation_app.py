import streamlit as st
import pandas as pd
import json
import html as html_module

from utils.export import generate_latex_codebook, generate_markdown_codebook
from utils.prompt_preview import render_prompt_preview_page, generate_all_prompts_text

def render_header():
    # Global CSS — injected once per page render
    global_css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Libre+Franklin:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

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
            color: #333333;
        }

        /* Subtle dividers */
        hr {
            border-color: #ccc !important;
        }

        /* Code blocks on prompt preview page */
        .stCodeBlock {
            border: 1px solid #e0dbd4;
            border-radius: 4px;
        }

        /* Remove excess top padding from Streamlit's main content area */
        [data-testid="stAppViewBlockContainer"] {
            padding-top: 1rem !important;
        }
        </style>
    """
    st.markdown(global_css, unsafe_allow_html=True)

    # Inline title — flows with page, no fixed positioning
    st.markdown(
        '<h1 style="font-family: Lora, serif; font-weight: 700; '
        'color: #333333; margin-bottom: 0; padding-bottom: 0.3em; '
        'border-bottom: 1px solid #ccc;">CodeBook Studio</h1>',
        unsafe_allow_html=True,
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
    render_header()

    if 'index' not in st.session_state or 'data' not in st.session_state or st.session_state.data is None:
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
        st.warning("Please upload a CSV file to start annotating.")
        return

    left_column, right_column = st.columns([0.7, 0.3], gap='large')

    with left_column:
        title_column = st.session_state.custom_schema["header_column"]
        text_column = st.session_state.custom_schema["text_column"]
        current_title = data.iloc[index][title_column]
        st.markdown(f"### {current_title}")

        current_text = data.iloc[index][text_column]
        safe_text = html_module.escape(str(current_text))
        st.markdown(
            f'<div style="height: 300px; overflow-y: scroll; border: 1px solid #ccc; '
            f'border-radius: 4px; padding: 1em; line-height: 1.6; '
            f'background-color: rgba(0, 0, 0, 0.03);">{safe_text}</div>',
            unsafe_allow_html=True,
        )

        if 'annotations' not in st.session_state:
            st.session_state.annotations = {}

        for key, content in st.session_state.custom_schema.items():
            if "section" in key:
                st.subheader(content['section_name'])
                st.write(content["section_instruction"])
                for _, config in content["annotations"].items():
                    full_column_name = f"{content['section_name']}_{config['name']}"
                    if config['type'] == 'checkbox':
                        annotated = st.checkbox(config['name'], value=bool(data.at[index, full_column_name]) if pd.notna(data.at[index, full_column_name]) else False, key=f'{index}_{full_column_name}', help=config['tooltip'])
                        st.session_state.annotations[full_column_name] = 1 if annotated else 0
                    elif config['type'] == 'likert':
                        default_value = 0
                        min_value = config.get('min_value', 0)
                        max_value = config.get('max_value', 5)  # Default to 5 instead of using scale
                        annotated = st.slider(config['name'], min_value, max_value, value=int(data.at[index, full_column_name]) if pd.notna(data.at[index, full_column_name]) else default_value, key=f'{index}_{full_column_name}', help=config['tooltip'], format="%d")
                        st.session_state.annotations[full_column_name] = annotated
                    elif config['type'] == 'dropdown':
                        options = [""] + config['options']
                        current_value = data.at[index, full_column_name]
                        if pd.isna(current_value) or current_value not in options:
                            selected_index = 0
                        else:
                            selected_index = options.index(current_value)
                        annotated = st.selectbox(config['name'], options, index=selected_index, key=f'{index}_{full_column_name}', help=config['tooltip'])
                        st.session_state.annotations[full_column_name] = annotated if annotated else None
                    elif config['type'] == 'textbox':
                        default_text = '' if pd.isna(data.at[index, full_column_name]) else data.at[index, full_column_name]
                        annotated = st.text_area(config['name'], value=default_text, key=f'{index}_{full_column_name}', help=config['tooltip'])
                        st.session_state.annotations[full_column_name] = annotated
                    if config['example']:
                        with st.expander(f"See examples for {config['name']}"):
                            st.write(config['example'], unsafe_allow_html=True)

    with right_column:
        st.markdown("### Navigation Controls")

        if st.button("Next") and index < len(data) - 1:
            update_data(index, data)
            update_index(index + 2)

        if st.button("Previous") and index > 0:
            update_data(index, data)
            update_index(index)

        new_index = st.slider("Go to Item", 1, len(data), index + 1, format="%d")
        if new_index != index + 1:
            update_data(index, data)
            update_index(new_index)

        if st.session_state.data is not None:
            csv_data = st.session_state.data.copy()  # Create a copy to update only when needed
            update_data(index, csv_data)  # Update the data copy
            csv = csv_data.to_csv(index=False).encode('utf-8')
            st.download_button(label="Download Annotated CSV", data=csv, file_name='annotated_data.csv', mime='text/csv')

        st.divider()
        st.markdown("##### Options")

        if st.button("Annotate New Data"):
            st.session_state.prepare_return = True
        
        if st.button("Edit Codebook"):
            update_data(index, data)
            st.session_state.data = data
            st.session_state.page = 'create_schema'
            st.rerun()

        schema_str = json.dumps(st.session_state.custom_schema, indent=4)
        st.download_button(label="Download Codebook as JSON", data=schema_str, file_name='custom_annotation_schema.json', mime='application/json')

        st.divider()
        st.markdown("##### Codebook & Prompts")

        latex_codebook = generate_latex_codebook(st.session_state.custom_schema)
        st.download_button(label="Download Codebook as LaTeX", data=latex_codebook, file_name='codebook.tex', mime='text/x-tex')

        md_codebook = generate_markdown_codebook(st.session_state.custom_schema)
        st.download_button(label="Download Codebook as Markdown", data=md_codebook, file_name='codebook.md', mime='text/markdown')

        if st.button("Preview LLM Prompts"):
            update_data(index, data)
            st.session_state.data = data
            st.session_state.previous_page = 'annotate'
            st.session_state.page = 'prompt_preview'
            st.rerun()

        if st.session_state.get('prepare_return', False):
            st.warning("Warning: Annotations that have not been downloaded will not be saved.")
            confirmed = st.checkbox("I understand and wish to proceed.")

            if confirmed:
                st.session_state.data = None
                st.session_state.custom_schema = {}
                st.session_state.page = 'landing'
                st.session_state.prepare_return = False
                st.rerun()

def landing_page():
    render_header()

    st.markdown(
        '<p style="font-size: 1.05em; color: #555; line-height: 1.6; margin-top: 0.5em;">'
        'A codebook-driven text annotation tool for computational social science. '
        'Define your annotation codebook once &mdash; use it for human annotation, '
        'LLM pipelines, and paper appendices.</p>',
        unsafe_allow_html=True,
    )
    st.info(
        "Exported JSON codebooks can be used directly in "
        "[CodeBook Lab](https://github.com/LorcanMcLaren/codebook-lab) "
        "to run and evaluate LLM annotation experiments."
    )
    st.caption(
        "If you use CodeBook Studio in research, please cite the software repository: "
        "[github.com/LorcanMcLaren/codebook-studio](https://github.com/LorcanMcLaren/codebook-studio)."
    )

    st.write("")
    st.markdown("#### Get Started")

    # File uploader for the CSV file
    st.markdown("**Upload your data**")
    uploaded_file = st.file_uploader("Choose a text CSV file", type=['csv'], key="csv_uploader")

    # Check if a CSV file has been uploaded and if an annotation codebook is present
    if uploaded_file is not None:
        temp_df = pd.read_csv(uploaded_file)
        st.session_state.column_names = temp_df.columns.tolist()

        st.session_state.uploaded_file = uploaded_file
        st.session_state.index = 1

        st.write("")

        # File uploader for the annotation codebook JSON file
        st.markdown("**Upload an existing codebook** *(optional)*")
        schema_file = st.file_uploader("Upload a codebook JSON file, or create a new codebook in the next step", type=['json'], key="json_uploader")

        # Load the uploaded annotation codebook
        if schema_file is not None:
            st.session_state.custom_schema = json.load(schema_file)

        # Load default codebook if available and no custom schema has been uploaded yet
        if 'custom_schema' not in st.session_state:
            st.session_state.custom_schema = {}  # Use an empty schema if default is not found

        st.write("")

        if st.button("Start Annotating"):
            # Check if the codebook is empty before proceeding to annotation
            if st.session_state.custom_schema:
                st.session_state.data = process_data(st.session_state.uploaded_file, st.session_state.custom_schema["text_column"])
                last_annotated_row = find_last_annotated_row(st.session_state.data, st.session_state.custom_schema)
                st.session_state.index = last_annotated_row + 1 if last_annotated_row < len(st.session_state.data) else len(st.session_state.data)
                st.session_state.page = 'annotate'
            else:
                # Redirect to codebook creation page if no codebook is present
                st.session_state.page = 'create_schema'
            st.rerun()


def schema_creation_page():
    render_header()
    st.header("Create Your Codebook")
    st.markdown(
        "Your codebook defines the annotation task: what questions annotators should answer "
        "for each text, and what response formats are available. The same codebook file can "
        "be used for human annotation in this app, passed directly to an LLM annotation "
        "pipeline, or exported as a LaTeX/Markdown appendix for your paper."
    )
    st.caption(
        "Tip: download the JSON codebook here and use it in "
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
    header_column = st.selectbox("Header column", st.session_state.column_names, index=st.session_state.column_names.index(header_column_default) if header_column_default in st.session_state.column_names else 0, key="header_column_selector", help="The column used as a title or identifier for each text (displayed above the text during annotation)")
    text_column = st.selectbox("Text column", st.session_state.column_names, index=st.session_state.column_names.index(text_column_default) if text_column_default in st.session_state.column_names else 0, key="text_column_selector", help="The column containing the main text content that annotators will read and annotate")
        
    # Initialize or update the session state for codebook creation
    if not st.session_state.custom_schema:
        # Add these lines at an appropriate place in schema_creation_page()
        st.session_state.custom_schema = {
            "header_column": header_column,
            "text_column": text_column,
            "section_1": {"section_name": "", "section_instruction": "", "annotations": {}}}
    
    if 'annotations_count' not in st.session_state:
        st.session_state.annotations_count = {}
        for section_key, section_value in st.session_state.custom_schema.items():
            if "section" in section_key:
                st.session_state.annotations_count[section_key] = len(section_value["annotations"])

    # Store the selected columns in custom_schema
    if st.session_state.custom_schema:
        st.session_state.custom_schema["header_column"] = header_column
        st.session_state.custom_schema["text_column"] = text_column

    # Function to add a new section
    def add_section():
        new_section_key = f"section_{len(st.session_state.custom_schema) - 1}"
        st.session_state.custom_schema[new_section_key] = {"section_name": "", "section_instruction": "", "annotations": {}}
        st.session_state.annotations_count[new_section_key] = 0  # Initialize with 0 annotations
        st.rerun()

    def delete_section(section_key):
        del st.session_state.custom_schema[section_key]
        st.session_state.annotations_count.pop(section_key, None)
        st.rerun()

    def add_annotation(section_key):
        st.session_state.annotations_count[section_key] += 1
        st.rerun()

    def delete_annotation(section_key, annotation_key):
        del st.session_state.custom_schema[section_key]['annotations'][annotation_key]
        st.session_state.annotations_count[section_key] -= 1
        st.rerun()

    def render_annotation(annotation, key):
        label = annotation['name'] if annotation['name'] else ""
        if annotation['type'] == 'checkbox':
            st.checkbox(label, help=annotation['tooltip'], key=key)
        elif annotation['type'] == 'likert':
            default_value = 0
            min_value = annotation.get('min_value', 0)
            max_value = annotation.get('max_value', 5)  # Default to 5 instead of using scale
            st.slider(label, min_value, max_value, value=default_value, help=annotation['tooltip'], format="%d", key=key)
        elif annotation['type'] == 'dropdown':
            options = [""] + annotation.get('options', [])
            st.selectbox(label, options, index=0, help=annotation['tooltip'], key=key)
        elif annotation['type'] == 'textbox':
            st.text_area(label, help=annotation['tooltip'], key=key)
        if annotation['example']:
            with st.expander(f"See examples for {annotation['name']}"):
                st.write(annotation['example'], unsafe_allow_html=True)

    for section_key in st.session_state.custom_schema.keys():
        if "section" in section_key:
            section = st.session_state.custom_schema[section_key]
            section_title = "Section " + section_key.split('section_')[1]
            with st.container():
                left_column, right_column = st.columns([0.8, 0.2])
                with left_column:
                    st.subheader(section_title)
                with right_column:
                    if st.button("Delete Section", key=f"delete_section_{section_key}"):
                        delete_section(section_key)
                section["section_name"] = st.text_input("Section name", key=f"{section_key}_name", value=section.get("section_name", ""), help="A descriptive name for this group of annotations (e.g. 'Discrete Emotions', 'Economic Sentiment')")
                section["section_instruction"] = st.text_area("Section instructions", key=f"{section_key}_instructions", value=section.get("section_instruction", ""), help="Instructions shown to annotators before this section's annotations. Explain the task and any guidelines.")


                for ann_idx in range(st.session_state.annotations_count.get(section_key, 0)):
                    ann_key = f"annotation_{ann_idx + 1}"
                    left_column, right_column = st.columns([0.8, 0.25])
                    with left_column:
                        with st.expander(f"Annotation {ann_idx + 1}"):
                            if ann_key not in section["annotations"]:
                                section["annotations"][ann_key] = {"name": "", "type": "checkbox", "tooltip": "", "example": ""}

                            annotation = section["annotations"][ann_key]
                            name = st.text_input("Name", key=f"{section_key}_{ann_key}_name", value=annotation.get("name", ""), help="The label for this annotation, shown to both human annotators and in LLM prompts (e.g. 'Anger', 'Spatial Distance', 'Positivity')")
                            annotation["type"] = st.selectbox("Type", ["checkbox", "likert", "dropdown", "textbox"], key=f"{section_key}_{ann_key}_type", index=["checkbox", "likert", "dropdown", "textbox"].index(annotation.get("type", "checkbox")))
                            tooltip = st.text_area("Description", key=f"{section_key}_{ann_key}_tooltip", value=annotation.get("tooltip", ""), help="A detailed description of what this annotation measures. This is shown as help text during annotation and used as the main instruction in LLM prompts.")
                            example = st.text_area("Examples", key=f"{section_key}_{ann_key}_example", value=annotation.get("example", ""), help="Provide examples to guide annotators. For LLM prompts, use the format: Text: \\n\"example text\"\\n\\nResponse: \\n{\"response\": \"value\"}")

                            if annotation["type"] == "likert":
                                min_value = st.number_input("Minimum Value", value=annotation.get("min_value", 0), key=f"{section_key}_{ann_key}_min_value")
                                max_value = st.number_input("Maximum Value", value=annotation.get("max_value", 5), key=f"{section_key}_{ann_key}_max_value")
                            elif annotation["type"] == "dropdown":
                                options_str = st.text_area("Options (comma-separated)", key=f"{section_key}_{ann_key}_options", value=','.join(annotation.get("options", [])), help="List the available choices, separated by commas (e.g. 'negative, positive' or 'Low, Medium, High')")
                                options = [option.strip() for option in options_str.split(',') if option.strip()]
                            if st.button("Save Changes",  key=f"update_annotation_{section_key}_{ann_key}"):
                                annotation["name"] = name
                                annotation["tooltip"] = tooltip
                                annotation["example"] = example
                                if annotation["type"] == "likert":
                                    annotation["min_value"] = min_value
                                    annotation["max_value"] = max_value
                                elif annotation["type"] == "dropdown":
                                    annotation["options"] = options
                    with right_column:
                        if st.button("Delete Annotation", key=f"delete_annotation_{section_key}_{ann_key}"):
                            delete_annotation(section_key, ann_key)

                    st.caption(f"Preview of annotation {ann_idx + 1}")
                    render_annotation(annotation, key=f"{section_key}_{ann_key}_render")

                if st.button("Add Annotation", key=f"add_annotation_{section_key}"):
                    add_annotation(section_key)
                st.divider()

    if st.button("Add New Section"):
        add_section()

    st.divider()
    st.write("Current codebook (JSON):")
    st.json(st.session_state.custom_schema)

    schema_str = json.dumps(st.session_state.custom_schema, indent=4)
    st.download_button(label="Download Codebook as JSON", data=schema_str, file_name='custom_annotation_schema.json', mime='application/json')

    latex_codebook = generate_latex_codebook(st.session_state.custom_schema)
    st.download_button(label="Download Codebook as LaTeX", data=latex_codebook, file_name='codebook.tex', mime='text/x-tex')

    md_codebook = generate_markdown_codebook(st.session_state.custom_schema)
    st.download_button(label="Download Codebook as Markdown", data=md_codebook, file_name='codebook.md', mime='text/markdown')

    if st.button("Preview LLM Prompts"):
        st.session_state.previous_page = 'create_schema'
        st.session_state.page = 'prompt_preview'
        st.rerun()

    if st.button("Start Annotating"):
        st.session_state.data = process_data(st.session_state.uploaded_file, text_column)
        st.session_state.page = 'annotate'
        st.rerun()


def update_data(index, data):
    for annotation_option in st.session_state.annotations:
        data.at[index, annotation_option] = st.session_state.annotations[annotation_option]

def update_index(new_index):
    st.session_state.index = new_index
    st.rerun()

def prompt_preview_page():
    render_header()
    render_prompt_preview_page(st.session_state.custom_schema)

    previous = st.session_state.get('previous_page', 'annotate')
    label = "Back to Annotation" if previous == 'annotate' else "Back to Codebook Editor"
    if st.button(label):
        st.session_state.page = previous
        st.rerun()


if 'page' not in st.session_state:
    st.session_state.page = 'landing'

page_title = "CodeBook Studio"
page_icon = "📓"

if st.session_state.page == 'landing':
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="centered")
    landing_page()
elif st.session_state.page == 'annotate':
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide")
    annotation_page()
elif st.session_state.page == 'create_schema':
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="centered")
    schema_creation_page()
elif st.session_state.page == 'prompt_preview':
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide")
    prompt_preview_page()


# Add a footer
footer = """<style>
.footer a:link, .footer a:visited {
    color: #555555;
    background-color: transparent;
    text-decoration: underline;
}

.footer a:hover, .footer a:active {
    color: #7a4a5d;
    background-color: transparent;
    text-decoration: underline;
}

.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    color: #999;
    text-align: center;
    font-size: 0.85em;
    padding: 0.4em 0;
    border-top: 1px solid #e0dbd4;
    background-color: #f9f6f1;
}
</style>
<div class="footer">
<p>Developed by <a href="https://www.lorcanmclaren.com" target="_blank">Lorcan McLaren</a></p>
</div>
"""
st.markdown(footer, unsafe_allow_html=True)
