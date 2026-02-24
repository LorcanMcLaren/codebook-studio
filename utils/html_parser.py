"""
Parse HTML example strings from annotation schemas into structured data
for clean LaTeX and Markdown export.

Handles two formats:
  Format A (simple, <br>-separated):
    "Pro: 'It's outrageous...' <br> Anti: 'The anger towards...'"

  Format B (structured Text/Response pairs):
    "Text: \n\"STAGNANT WAGES...\"\n\nResponse: \n{\"response\": \"negative\"}\n\n---\n\n..."
"""

import re
import json


def parse_examples(example_text, annotation_type=None):
    """
    Parse an example string from a schema annotation into structured data.

    Args:
        example_text: Raw example string (may contain HTML or structured text)
        annotation_type: The annotation type (checkbox, dropdown, likert, textbox)

    Returns:
        dict: {code_label: [list_of_example_texts]}
              e.g. {"negative": ["STAGNANT WAGES...", "Trade Deficit..."],
                     "positive": ["Market Undergoes...", "Investors Regain..."]}
              or {"Pro": ["It's outrageous..."], "Anti": ["The anger towards..."]}
              Returns empty dict if no examples or unparseable.
    """
    if not example_text or not example_text.strip():
        return {}

    # Detect format based on presence of "Text:" and "Response:" patterns
    if "Text:" in example_text and "Response:" in example_text:
        return _parse_format_b(example_text)
    elif "<br>" in example_text.lower():
        return _parse_format_a(example_text)
    else:
        # Fallback: treat as a single unlabelled example
        return {"Example": [example_text.strip()]}


def _parse_format_a(example_text):
    """
    Parse Format A: simple <br>-separated examples with labels.
    e.g. "Pro: 'It's outrageous...' <br> Anti: 'The anger towards...'"
    Also handles multi-label formats like:
    "Care Pro: 'Adopting...' <br> Care Anti: '...' <br> Harm Pro: '...' <br> Harm Anti: '...'"
    """
    results = {}

    # Split on <br> tags (case-insensitive)
    parts = re.split(r'<br\s*/?>', example_text, flags=re.IGNORECASE)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Try to extract label and text: "Label: 'text'" or "Label: text"
        match = re.match(r"^(.+?):\s*['\"]?(.+?)['\"]?\s*$", part, re.DOTALL)
        if match:
            label = match.group(1).strip()
            text = match.group(2).strip()
            # Remove trailing quote if present
            text = text.rstrip("'\"")
            if label not in results:
                results[label] = []
            results[label].append(text)
        else:
            # No label found, use generic
            if "Example" not in results:
                results["Example"] = []
            results["Example"].append(part)

    return results


def _parse_format_b(example_text):
    """
    Parse Format B: structured Text/Response pairs separated by ---.
    e.g. 'Text: \n"STAGNANT..."\n\nResponse: \n{"response": "negative"}\n\n---\n\nText: ...'
    """
    results = {}

    # Split on --- separator
    blocks = re.split(r'\n---\n', example_text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Extract the text content
        text_match = re.search(r'Text:\s*\n"?(.+?)"?\s*(?:\n\nResponse:|\Z)', block, re.DOTALL)
        # Extract the response value
        response_match = re.search(r'Response:\s*\n(.+?)(?:\n\n|\Z)', block, re.DOTALL)

        if text_match:
            text = text_match.group(1).strip().strip('"')

            # Determine the label from the response
            label = "Example"
            if response_match:
                response_raw = response_match.group(1).strip()
                try:
                    parsed = json.loads(response_raw)
                    response_value = parsed.get("response", "")
                    label = str(response_value).capitalize()
                except (json.JSONDecodeError, AttributeError):
                    # Try to extract value directly
                    label = response_raw.strip('"').capitalize()

            if label not in results:
                results[label] = []
            results[label].append(text)

    return results


def truncate_text(text, max_sentences=2):
    """
    Truncate text to approximately max_sentences sentences.
    Returns the truncated text (without any ellipsis marker — caller adds that).
    """
    if not text:
        return text

    # Split on sentence-ending punctuation followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    if len(sentences) <= max_sentences:
        return text.strip()

    truncated = ' '.join(sentences[:max_sentences])
    return truncated
