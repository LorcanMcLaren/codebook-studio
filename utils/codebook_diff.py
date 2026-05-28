"""Pure-Python diff between two codebook schemas.

A schema is the JSON object created by the editor: top-level
``header_column`` / ``text_column`` plus a series of ``section_<n>``
entries, each containing ``section_name``, ``section_instruction`` and
``annotation_<n>`` children.

``diff_schemas(old, new)`` walks both schemas in parallel by structural
key (``section_1``, ``annotation_1`` …) and returns a flat list of
change records that the UI layer formats. No rename detection — a
rename of ``section_2`` to a new name is reported as a ``section_name``
field change; reordering sections will surface as add+remove.
"""

from __future__ import annotations

TOP_LEVEL_FIELDS = ("header_column", "text_column", "metadata_columns")

SECTION_META_FIELDS = ("section_name", "section_instruction")

ANNOTATION_FIELDS = (
    "name",
    "type",
    "tooltip",
    "options",
    "min_value",
    "max_value",
    "condition",
    "example",
)

FIELD_LABELS = {
    "header_column": "Header column",
    "text_column": "Text column",
    "metadata_columns": "Metadata columns",
    "section_name": "Section name",
    "section_instruction": "Instruction",
    "name": "Name",
    "type": "Response type",
    "tooltip": "Tooltip",
    "example": "Example",
    "options": "Options",
    "min_value": "Minimum value",
    "max_value": "Maximum value",
    "condition": "Condition",
}


def _is_section_key(key):
    return isinstance(key, str) and key.startswith("section_")


def _is_annotation_key(key):
    return isinstance(key, str) and key.startswith("annotation_")


def _section_keys(schema):
    if not isinstance(schema, dict):
        return []
    return sorted(
        (k for k in schema.keys() if _is_section_key(k)),
        key=_natural_key,
    )


def _annotation_keys(section):
    annotations = section.get("annotations") if isinstance(section, dict) else None
    if not isinstance(annotations, dict):
        return []
    return sorted(
        (k for k in annotations.keys() if _is_annotation_key(k)),
        key=_natural_key,
    )


def _natural_key(key):
    parts = key.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return (parts[0], int(parts[1]))
    return (key, 0)


def field_label(field):
    return FIELD_LABELS.get(field, field)


def diff_schemas(old, new):
    """Return a list of change records describing how ``new`` differs from ``old``.

    Each record is a dict with a ``kind`` key. Kinds:

    - ``field_changed``: ``{field, old, new, scope, section_key?, annotation_key?}``
      where ``scope`` is one of ``"top"``, ``"section"``, ``"annotation"``.
    - ``section_added`` / ``section_removed``: ``{section_key, section}``
    - ``annotation_added`` / ``annotation_removed``: ``{section_key, annotation_key, annotation}``
    """
    old = old or {}
    new = new or {}
    changes = []

    for field in TOP_LEVEL_FIELDS:
        old_val = old.get(field)
        new_val = new.get(field)
        if old_val != new_val:
            changes.append({
                "kind": "field_changed",
                "scope": "top",
                "field": field,
                "old": old_val,
                "new": new_val,
            })

    old_sections = set(_section_keys(old))
    new_sections = set(_section_keys(new))
    all_sections = sorted(old_sections | new_sections, key=_natural_key)

    for section_key in all_sections:
        in_old = section_key in old_sections
        in_new = section_key in new_sections

        if in_old and not in_new:
            changes.append({
                "kind": "section_removed",
                "section_key": section_key,
                "section": old[section_key],
            })
            continue

        if in_new and not in_old:
            changes.append({
                "kind": "section_added",
                "section_key": section_key,
                "section": new[section_key],
            })
            continue

        old_section = old.get(section_key, {}) or {}
        new_section = new.get(section_key, {}) or {}

        for field in SECTION_META_FIELDS:
            old_val = old_section.get(field)
            new_val = new_section.get(field)
            if old_val != new_val:
                changes.append({
                    "kind": "field_changed",
                    "scope": "section",
                    "section_key": section_key,
                    "field": field,
                    "old": old_val,
                    "new": new_val,
                })

        old_anns = set(_annotation_keys(old_section))
        new_anns = set(_annotation_keys(new_section))
        all_anns = sorted(old_anns | new_anns, key=_natural_key)

        for annotation_key in all_anns:
            in_old_a = annotation_key in old_anns
            in_new_a = annotation_key in new_anns

            if in_old_a and not in_new_a:
                changes.append({
                    "kind": "annotation_removed",
                    "section_key": section_key,
                    "annotation_key": annotation_key,
                    "annotation": old_section["annotations"][annotation_key],
                })
                continue

            if in_new_a and not in_old_a:
                changes.append({
                    "kind": "annotation_added",
                    "section_key": section_key,
                    "annotation_key": annotation_key,
                    "annotation": new_section["annotations"][annotation_key],
                })
                continue

            old_ann = old_section["annotations"][annotation_key] or {}
            new_ann = new_section["annotations"][annotation_key] or {}

            known = list(ANNOTATION_FIELDS)
            extras = sorted(
                {k for k in (*old_ann.keys(), *new_ann.keys()) if isinstance(k, str)}
                - set(known)
            )
            ordered_fields = known + extras

            for field in ordered_fields:
                if field not in old_ann and field not in new_ann:
                    continue
                old_val = old_ann.get(field)
                new_val = new_ann.get(field)
                if old_val != new_val:
                    changes.append({
                        "kind": "field_changed",
                        "scope": "annotation",
                        "section_key": section_key,
                        "annotation_key": annotation_key,
                        "field": field,
                        "old": old_val,
                        "new": new_val,
                    })

    return changes


def has_changes(old, new):
    return bool(diff_schemas(old, new))


def group_by_section(changes):
    """Group change records into an ordered list of section buckets for UI rendering.

    Returns ``(top_level_changes, section_buckets)`` where ``section_buckets`` is
    a list of dicts ``{section_key, changes}`` ordered by natural key.
    """
    top = []
    by_section = {}
    for change in changes:
        if change.get("scope") == "top":
            top.append(change)
            continue
        section_key = change.get("section_key")
        if not section_key:
            continue
        by_section.setdefault(section_key, []).append(change)

    ordered = sorted(by_section.keys(), key=_natural_key)
    buckets = [{"section_key": k, "changes": by_section[k]} for k in ordered]
    return top, buckets
