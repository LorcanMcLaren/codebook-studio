"""
LLM prompt generation and preview for annotation schemas.

Ported from the standard prompt logic in annotate.py.
Generates prompts that show exactly what an LLM would receive
when annotating texts using a given schema.
"""


# --------------------------------------------------------------------------
# Prompt generation functions (ported from annotate.py, standard wrapper only)
# --------------------------------------------------------------------------

def _get_response_instructions(annotation_type, options=None, min_value=None, max_value=None):
    """Generate response format instructions based on annotation type."""
    if annotation_type == "dropdown" and options:
        options_str = ', or '.join(f'"{option}"' for option in options)
        return f"Respond only with one of the following options: {options_str}."
    elif annotation_type == "checkbox":
        return 'Respond with 1 if "Yes" or 0 if "No".'
    elif annotation_type == "likert" and min_value is not None and max_value is not None:
        return (f"Respond with a whole number from {min_value} to {max_value} "
                f"(inclusive), where {min_value} means lowest and {max_value} means highest.")
    elif annotation_type == "textbox":
        return "Respond with a brief text explanation."
    return ""


def _build_core_prompt(section_name, section_instruction, name, tooltip,
                       response_instructions, example, use_examples):
    """Build the core prompt with consistent field ordering."""
    core = f"{section_name}"

    if section_instruction:
        core += f"\n{section_instruction}"

    core += f"\n\n{name}"

    if tooltip:
        core += f"\n{tooltip}"

    if response_instructions:
        core += f"\n\n{response_instructions}"

    core += '\n\nReturn your response in JSON format, with the key "response".'

    if use_examples and example:
        core += f"\n\n{example}"
    elif not use_examples and example:
        # Include example only if it doesn't contain "Text:" (to avoid duplication)
        if "Text:" not in example:
            core += f"\n\n{example}"

    return core


def _add_standard_wrapper(core_prompt, text):
    """Add standard wrapper to the core prompt."""
    return f'{core_prompt}\n\n---\n\nText: \n"{text}"\n\nResponse: \n'


def format_prompt(section_name, section_instruction, name, tooltip, annotation_type,
                  options=None, min_value=None, max_value=None, example=None,
                  text=None, use_examples=False):
    """
    Format a complete prompt for a single annotation.

    Args:
        section_name: Name of the annotation section
        section_instruction: Instruction for the section from the schema
        name: Name of the annotation
        tooltip: Tooltip text explaining the annotation
        annotation_type: Type of annotation (dropdown, checkbox, textbox, likert)
        options: List of possible options (for dropdown)
        min_value: Minimum value for likert scale
        max_value: Maximum value for likert scale
        example: Example text from the schema
        text: The text to classify (use placeholder for preview)
        use_examples: Whether to include examples from the schema

    Returns:
        str: The complete formatted prompt
    """
    response_instructions = _get_response_instructions(
        annotation_type, options, min_value, max_value
    )

    core_prompt = _build_core_prompt(
        section_name, section_instruction, name, tooltip,
        response_instructions, example, use_examples
    )

    return _add_standard_wrapper(core_prompt, text or "<text to annotate>")


# --------------------------------------------------------------------------
# Streamlit UI
# --------------------------------------------------------------------------

def render_prompt_preview_page(schema):
    """
    Render the LLM prompt preview page in Streamlit.

    Shows a generated prompt for each annotation in the schema,
    with controls for toggling examples, and a download button.
    """
    import streamlit as st

    st.header("LLM Prompt Preview")
    st.write("Preview the prompts that would be sent to an LLM for each annotation "
             "in your codebook. These use the standard prompt format compatible with the LLM annotation pipeline.")

    use_examples = st.checkbox("Include examples in prompts", value=False)

    st.divider()

    if not schema:
        st.warning("No codebook loaded. Please create or upload a codebook first.")
        return

    # Generate and display a prompt for each annotation
    for key, section in schema.items():
        if not key.startswith('section'):
            continue

        section_name = section.get('section_name', '')
        section_instruction = section.get('section_instruction', '')
        annotations = section.get('annotations', {})

        for ann_key in sorted(annotations.keys()):
            annotation = annotations[ann_key]
            name = annotation.get('name', '')
            ann_type = annotation.get('type', '')
            tooltip = annotation.get('tooltip', '')
            example = annotation.get('example', '')
            options = annotation.get('options', None)
            min_value = annotation.get('min_value', None)
            max_value = annotation.get('max_value', None)

            prompt = format_prompt(
                section_name=section_name,
                section_instruction=section_instruction,
                name=name,
                tooltip=tooltip,
                annotation_type=ann_type,
                options=options,
                min_value=min_value,
                max_value=max_value,
                example=example,
                text="<text to annotate>",
                use_examples=use_examples,
            )

            st.subheader(f"{section_name} — {name} ({ann_type})")
            st.code(prompt, language=None)

    st.divider()

    # Download all prompts
    all_prompts = generate_all_prompts_text(schema, use_examples)
    st.download_button(
        label="Download All Prompts as Text",
        data=all_prompts,
        file_name="llm_prompts.txt",
        mime="text/plain",
    )


def generate_all_prompts_text(schema, use_examples=False):
    """
    Generate a single text file containing all prompts for the schema.

    Args:
        schema: The annotation schema dict
        use_examples: Whether to include examples in prompts

    Returns:
        str: All prompts concatenated with separator lines
    """
    blocks = []

    for key, section in schema.items():
        if not key.startswith('section'):
            continue

        section_name = section.get('section_name', '')
        section_instruction = section.get('section_instruction', '')
        annotations = section.get('annotations', {})

        for ann_key in sorted(annotations.keys()):
            annotation = annotations[ann_key]
            name = annotation.get('name', '')
            ann_type = annotation.get('type', '')
            tooltip = annotation.get('tooltip', '')
            example = annotation.get('example', '')
            options = annotation.get('options', None)
            min_value = annotation.get('min_value', None)
            max_value = annotation.get('max_value', None)

            prompt = format_prompt(
                section_name=section_name,
                section_instruction=section_instruction,
                name=name,
                tooltip=tooltip,
                annotation_type=ann_type,
                options=options,
                min_value=min_value,
                max_value=max_value,
                example=example,
                text="<text to annotate>",
                use_examples=use_examples,
            )

            header = f"{section_name} — {name} ({ann_type})"
            blocks.append(f"{'=' * 80}\n{header}\n{'=' * 80}\n{prompt}")

    return '\n\n'.join(blocks)
