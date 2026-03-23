"""
Generate LaTeX and Markdown codebook documents from annotation schemas.

The exported codebook is suitable for pasting into academic paper appendices,
providing a formal description of the annotation scheme used in the study.
"""

import re
from utils.html_parser import parse_examples, truncate_text


# --------------------------------------------------------------------------
# LaTeX helpers
# --------------------------------------------------------------------------

_LATEX_SPECIAL = {
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\textasciicircum{}',
}

# Characters that need escaping but NOT inside our own LaTeX commands
_LATEX_ESCAPE_RE = re.compile(
    '([' + ''.join(re.escape(c) for c in _LATEX_SPECIAL.keys()) + '])'
)


def _escape_latex(text):
    """Escape LaTeX special characters in user-provided text."""
    if not text:
        return ""
    # First handle backslashes (must come before other replacements)
    text = text.replace('\\', r'\textbackslash{}')
    # Then handle all other special characters
    text = _LATEX_ESCAPE_RE.sub(lambda m: _LATEX_SPECIAL[m.group(1)], text)
    return text


def _latex_quote(text):
    """Wrap text in proper LaTeX double quotes: ``text''"""
    return f"``{text}''"


def _normalize_condition_value(annotation, value):
    ann_type = annotation.get('type', '')

    if value is None:
        return None
    if ann_type == 'checkbox':
        lowered = str(value).strip().lower()
        if lowered in {'1', 'true', 'yes'}:
            return 1
        if lowered in {'0', 'false', 'no'}:
            return 0
    if ann_type == 'likert':
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if ann_type == 'textbox':
        return str(value).strip()
    return str(value)


def _format_condition_value(annotation, value):
    normalized = _normalize_condition_value(annotation, value)
    if normalized is None:
        return "an answer"
    if annotation.get('type') == 'checkbox':
        return "Yes" if normalized == 1 else "No"
    return str(normalized)


def _get_condition_note(schema, annotation):
    condition = annotation.get('condition')
    if not isinstance(condition, dict):
        return ""

    target_section = schema.get(condition.get('section_key'))
    if not isinstance(target_section, dict):
        return ""

    target_annotation = target_section.get('annotations', {}).get(condition.get('annotation_key'))
    if not isinstance(target_annotation, dict):
        return ""

    section_name = target_section.get('section_name') or condition.get('section_key', 'Section')
    annotation_name = target_annotation.get('name') or condition.get('annotation_key', 'annotation')
    expected_value = _format_condition_value(target_annotation, condition.get('value'))
    return (
        f'Annotators answer this question only if the question "{annotation_name}" '
        f'in the section "{section_name}" is answered "{expected_value}".'
    )


def _response_type_line_latex(annotation):
    """Generate the response type line for a LaTeX codebook entry."""
    ann_type = annotation.get('type', '')

    if ann_type == 'dropdown':
        options = annotation.get('options', [])
        formatted = ', '.join(o.capitalize() for o in options)
        return f"    \\item \\textbf{{Options:}} {_escape_latex(formatted)}"
    elif ann_type == 'likert':
        min_val = annotation.get('min_value', 0)
        max_val = annotation.get('max_value', 5)
        return f"    \\item \\textbf{{Scale:}} {min_val}--{max_val}"
    elif ann_type == 'checkbox':
        return "    \\item \\textbf{Response:} Yes/No"
    elif ann_type == 'textbox':
        return "    \\item \\textbf{Response:} Free text"
    return ""


def _format_examples_latex(example_text, annotation_type):
    """Format parsed examples as a nested LaTeX itemize structure."""
    parsed = parse_examples(example_text, annotation_type)
    if not parsed:
        return ""

    lines = []
    lines.append("    \\item \\textbf{Examples:}")
    lines.append("    \\begin{itemize}")

    for label, texts in parsed.items():
        escaped_label = _escape_latex(label)
        lines.append(f"        \\item Code `{escaped_label}':")
        lines.append("        \\begin{itemize}")
        for text in texts:
            truncated = truncate_text(text, max_sentences=2)
            escaped = _escape_latex(truncated)
            # Add [\ldots] if text was truncated
            if len(truncated) < len(text):
                lines.append(f"            \\item {_latex_quote(escaped + ' [\\ldots]')}")
            else:
                lines.append(f"            \\item {_latex_quote(escaped)}")
        lines.append("        \\end{itemize}")

    lines.append("    \\end{itemize}")
    return '\n'.join(lines)


# --------------------------------------------------------------------------
# LaTeX codebook generator
# --------------------------------------------------------------------------

def generate_latex_codebook(schema):
    """
    Generate a LaTeX codebook from an annotation schema.

    Args:
        schema: dict — the annotation schema (same format used by the app)

    Returns:
        str — LaTeX source text ready to paste into a paper appendix
    """
    output = []

    for key, section in schema.items():
        if not key.startswith('section'):
            continue

        section_name = section.get('section_name', '')
        section_instruction = section.get('section_instruction', '')

        output.append(f"\\subsection{{{_escape_latex(section_name)}}}")
        if section_instruction:
            output.append(_escape_latex(section_instruction))

        annotations = section.get('annotations', {})
        for ann_key in sorted(annotations.keys()):
            annotation = annotations[ann_key]
            name = annotation.get('name', '')
            tooltip = annotation.get('tooltip', '')
            example = annotation.get('example', '')
            ann_type = annotation.get('type', '')

            output.append(f"\\subsubsection{{{_escape_latex(name)}}}")
            output.append("\\begin{itemize}")

            # Question line
            if tooltip:
                output.append(f"    \\item \\textbf{{Question:}} {_escape_latex(tooltip)}")

            # Response type line
            type_line = _response_type_line_latex(annotation)
            if type_line:
                output.append(type_line)

            condition_note = _get_condition_note(schema, annotation)
            if condition_note:
                output.append(f"    \\item \\textbf{{When to answer:}} {_escape_latex(condition_note)}")

            # Examples
            if example:
                examples_block = _format_examples_latex(example, ann_type)
                if examples_block:
                    output.append(examples_block)

            output.append("\\end{itemize}")

    return '\n'.join(output)


# --------------------------------------------------------------------------
# Markdown helpers
# --------------------------------------------------------------------------

def _response_type_line_markdown(annotation):
    """Generate the response type line for a Markdown codebook entry."""
    ann_type = annotation.get('type', '')

    if ann_type == 'dropdown':
        options = annotation.get('options', [])
        formatted = ', '.join(o.capitalize() for o in options)
        return f"- **Options:** {formatted}"
    elif ann_type == 'likert':
        min_val = annotation.get('min_value', 0)
        max_val = annotation.get('max_value', 5)
        return f"- **Scale:** {min_val}–{max_val}"
    elif ann_type == 'checkbox':
        return "- **Response:** Yes/No"
    elif ann_type == 'textbox':
        return "- **Response:** Free text"
    return ""


def _format_examples_markdown(example_text, annotation_type):
    """Format parsed examples as a nested Markdown list."""
    parsed = parse_examples(example_text, annotation_type)
    if not parsed:
        return ""

    lines = []
    lines.append("- **Examples:**")

    for label, texts in parsed.items():
        lines.append(f'  - Code "{label}":')
        for text in texts:
            truncated = truncate_text(text, max_sentences=2)
            if len(truncated) < len(text):
                lines.append(f'    - "{truncated} [...]"')
            else:
                lines.append(f'    - "{truncated}"')

    return '\n'.join(lines)


# --------------------------------------------------------------------------
# Markdown codebook generator
# --------------------------------------------------------------------------

def generate_markdown_codebook(schema):
    """
    Generate a Markdown codebook from an annotation schema.

    Args:
        schema: dict — the annotation schema (same format used by the app)

    Returns:
        str — Markdown text ready to paste into a README or paper appendix
    """
    output = []

    for key, section in schema.items():
        if not key.startswith('section'):
            continue

        section_name = section.get('section_name', '')
        section_instruction = section.get('section_instruction', '')

        output.append(f"## {section_name}")
        if section_instruction:
            output.append(section_instruction)
        output.append("")  # blank line

        annotations = section.get('annotations', {})
        for ann_key in sorted(annotations.keys()):
            annotation = annotations[ann_key]
            name = annotation.get('name', '')
            tooltip = annotation.get('tooltip', '')
            example = annotation.get('example', '')
            ann_type = annotation.get('type', '')

            output.append(f"### {name}")

            # Question line
            if tooltip:
                output.append(f"- **Question:** {tooltip}")

            # Response type line
            type_line = _response_type_line_markdown(annotation)
            if type_line:
                output.append(type_line)

            condition_note = _get_condition_note(schema, annotation)
            if condition_note:
                output.append(f"- **When to answer:** {condition_note}")

            # Examples
            if example:
                examples_block = _format_examples_markdown(example, ann_type)
                if examples_block:
                    output.append(examples_block)

            output.append("")  # blank line between annotations

    return '\n'.join(output)
