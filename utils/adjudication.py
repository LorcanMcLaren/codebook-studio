"""Helpers for adjudication queue navigation."""

from __future__ import annotations

from typing import Any

import pandas as pd


def get_sorted_annotation_keys(section_content: dict[str, Any]) -> list[str]:
    def sort_key(annotation_key: str) -> tuple[int, int | str]:
        suffix = annotation_key.split("_")[-1]
        return (0, int(suffix)) if suffix.isdigit() else (1, annotation_key)

    return sorted(section_content.get("annotations", {}).keys(), key=sort_key)


def get_schema_sections(schema: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(key, schema[key]) for key in schema if str(key).startswith("section")]


def get_annotation_column_name(section_content: dict[str, Any], annotation: dict[str, Any]) -> str:
    return f"{section_content['section_name']}_{annotation['name']}"


def get_annotation_entries(schema: dict[str, Any]) -> list[tuple[str, dict[str, Any], str, dict[str, Any]]]:
    entries = []
    for section_key, section_content in get_schema_sections(schema):
        for annotation_key in get_sorted_annotation_keys(section_content):
            annotation = section_content.get("annotations", {}).get(annotation_key, {})
            entries.append((section_key, section_content, annotation_key, annotation))
    return entries


def get_annotation_lookup(
    schema: dict[str, Any],
) -> dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]]:
    return {
        (section_key, annotation_key): (section_content, annotation)
        for section_key, section_content, annotation_key, annotation in get_annotation_entries(schema)
    }


def get_annotation_condition(annotation: dict[str, Any]) -> dict[str, Any] | None:
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


def normalize_annotation_response_value(annotation: dict[str, Any], value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass

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
    return str(value).strip()


def is_answered_value(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip() != ""
    return pd.notna(value)


def is_annotation_active(
    schema: dict[str, Any],
    section_key: str,
    annotation_key: str,
    annotation_values: dict[str, Any],
    lookup: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] | None = None,
    visited: set[tuple[str, str]] | None = None,
) -> bool:
    lookup = lookup or get_annotation_lookup(schema)
    current_entry = lookup.get((section_key, annotation_key))
    if not current_entry:
        return True

    _, annotation = current_entry
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


def unresolved_applicable_cells(schema: dict[str, Any], data: pd.DataFrame) -> list[dict[str, Any]]:
    cells = []
    lookup = get_annotation_lookup(schema)
    for index, row in data.iterrows():
        annotation_values = row.to_dict()
        for section_key, section_content, annotation_key, annotation in get_annotation_entries(schema):
            if not is_annotation_active(schema, section_key, annotation_key, annotation_values, lookup=lookup):
                continue
            column = get_annotation_column_name(section_content, annotation)
            if column not in data.columns:
                continue
            if is_answered_value(row.get(column)):
                continue
            cells.append(
                {
                    "row_index": int(index),
                    "column": column,
                    "section_key": section_key,
                    "annotation_key": annotation_key,
                }
            )
    return cells


def unresolved_item_indices(schema: dict[str, Any], data: pd.DataFrame) -> list[int]:
    return sorted({cell["row_index"] for cell in unresolved_applicable_cells(schema, data)})


def next_unresolved_index(schema: dict[str, Any], data: pd.DataFrame, current_index: int) -> int | None:
    indices = unresolved_item_indices(schema, data)
    for index in indices:
        if index > current_index:
            return index
    return indices[0] if indices else None


def is_adjudication_filename(filename: str | None) -> bool:
    return "adjudication_queue" in str(filename or "").lower()
