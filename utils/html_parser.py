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


def parse_example_blocks(example_text, annotation_type=None):
    """
    Parse an example string from a schema annotation into ordered example blocks.

    Returns:
        list[dict]: [{"text": str, "response": Any, "label": str}]
    """
    if not example_text or not str(example_text).strip():
        return []

    example_text = _normalize_example_text(str(example_text))

    if "Text:" in example_text and "Response:" in example_text:
        return _parse_blocks_format_b(example_text, annotation_type)
    if "<br>" in example_text.lower():
        return _parse_blocks_format_a(example_text, annotation_type)

    return [
        {
            "text": example_text.strip(),
            "response": "",
            "label": "Example",
        }
    ]


def _normalize_example_text(example_text):
    """Normalize structured examples that were double-escaped in JSON."""
    if "Text:" not in example_text or "Response:" not in example_text:
        return example_text

    if "\\n" not in example_text and '\\"' not in example_text and "\\t" not in example_text:
        return example_text

    try:
        normalized = bytes(example_text, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return example_text

    if "Text:" in normalized and "Response:" in normalized:
        return normalized

    return example_text


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
    results = {}
    for block in parse_example_blocks(example_text, annotation_type):
        label = block.get("label") or "Example"
        results.setdefault(label, []).append(block.get("text", ""))
    return results


def serialize_example_blocks(example_blocks, annotation_type=None):
    """
    Serialize ordered example blocks into the prompt-ready schema format.

    Returns:
        str: Text/Response blocks joined by the standard --- separator.
    """
    serialized_blocks = []

    for block in example_blocks:
        text = str(block.get("text", "")).strip()
        response_value = _normalize_response_value(block.get("response", ""), annotation_type)

        if not text and response_value in ("", None):
            continue

        text_json = json.dumps(text, ensure_ascii=False)
        response_json = json.dumps({"response": response_value}, ensure_ascii=False)
        serialized_blocks.append(f"Text: \n{text_json}\n\nResponse: \n{response_json}")

    return "\n\n---\n\n".join(serialized_blocks)


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


def _parse_blocks_format_a(example_text, annotation_type=None):
    blocks = []
    parts = re.split(r'<br\s*/?>', example_text, flags=re.IGNORECASE)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        match = re.match(r"^(.+?):\s*['\"]?(.+?)['\"]?\s*$", part, re.DOTALL)
        if match:
            response_value = match.group(1).strip()
            text = match.group(2).strip().rstrip("'\"")
        else:
            response_value = ""
            text = part

        blocks.append(
            {
                "text": text,
                "response": response_value,
                "label": _humanize_response_label(response_value, annotation_type),
            }
        )

    return blocks


def _parse_blocks_format_b(example_text, annotation_type=None):
    blocks = []
    raw_blocks = re.split(r'\n---\n', example_text)

    for raw_block in raw_blocks:
        raw_block = raw_block.strip()
        if not raw_block:
            continue

        text_match = re.search(r'Text:\s*\n(.+?)(?:\n\nResponse:|\Z)', raw_block, re.DOTALL)
        response_match = re.search(r'Response:\s*\n(.+?)(?:\n\n|\Z)', raw_block, re.DOTALL)

        if not text_match:
            continue

        text = _decode_possible_json_string(text_match.group(1).strip())
        response_value = ""
        if response_match:
            response_value = _decode_response_value(response_match.group(1).strip())

        blocks.append(
            {
                "text": text,
                "response": response_value,
                "label": _humanize_response_label(response_value, annotation_type),
            }
        )

    return blocks


def _decode_possible_json_string(raw_value):
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, str):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    return raw_value.strip().strip('"')


def _decode_response_value(raw_value):
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, dict):
            return parsed.get("response", "")
        return parsed
    except (json.JSONDecodeError, TypeError):
        return raw_value.strip().strip('"')


def _normalize_response_value(response_value, annotation_type=None):
    if annotation_type == "checkbox":
        lowered = str(response_value).strip().lower()
        if lowered in {"1", "true", "yes"}:
            return 1
        if lowered in {"0", "false", "no"}:
            return 0
        return 1 if bool(response_value) else 0

    if annotation_type == "likert":
        try:
            return int(response_value)
        except (ValueError, TypeError):
            return response_value

    if response_value is None:
        return ""

    return str(response_value)


def _humanize_response_label(response_value, annotation_type=None):
    if annotation_type == "checkbox":
        lowered = str(response_value).strip().lower()
        if lowered in {"1", "true", "yes"}:
            return "Yes"
        if lowered in {"0", "false", "no"}:
            return "No"

    if response_value is None or str(response_value).strip() == "":
        return "Example"

    text = str(response_value).strip()
    return text[0].upper() + text[1:] if text else "Example"


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
