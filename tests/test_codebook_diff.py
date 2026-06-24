import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.codebook_diff import diff_schemas, group_by_section, has_changes


@pytest.fixture
def base_schema():
    return {
        "header_column": "title",
        "text_column": "text",
        "section_1": {
            "section_name": "Sentiment",
            "section_instruction": "Identify the sentiment.",
            "annotations": {
                "annotation_1": {
                    "name": "Polarity",
                    "type": "dropdown",
                    "tooltip": "Pick one",
                    "example": "Text:\n...\n",
                    "options": ["positive", "negative", "neutral"],
                },
            },
        },
        "section_2": {
            "section_name": "Intensity",
            "section_instruction": "Rate intensity.",
            "annotations": {
                "annotation_1": {
                    "name": "Intensity",
                    "type": "likert",
                    "tooltip": "Use 1-5",
                    "example": "",
                    "min_value": 1,
                    "max_value": 5,
                },
            },
        },
    }


def test_identical_schemas_have_no_changes(base_schema):
    assert diff_schemas(base_schema, copy.deepcopy(base_schema)) == []
    assert has_changes(base_schema, copy.deepcopy(base_schema)) is False


def test_field_change_in_annotation_tooltip(base_schema):
    new = copy.deepcopy(base_schema)
    new["section_1"]["annotations"]["annotation_1"]["tooltip"] = "Pick exactly one"

    changes = diff_schemas(base_schema, new)
    assert len(changes) == 1
    change = changes[0]
    assert change["kind"] == "field_changed"
    assert change["scope"] == "annotation"
    assert change["section_key"] == "section_1"
    assert change["annotation_key"] == "annotation_1"
    assert change["field"] == "tooltip"
    assert change["old"] == "Pick one"
    assert change["new"] == "Pick exactly one"


def test_section_added(base_schema):
    new = copy.deepcopy(base_schema)
    new["section_3"] = {
        "section_name": "Evidence",
        "section_instruction": "Quote it",
        "annotations": {
            "annotation_1": {"name": "Evidence", "type": "textbox", "tooltip": "", "example": ""},
        },
    }

    changes = diff_schemas(base_schema, new)
    assert len(changes) == 1
    assert changes[0]["kind"] == "section_added"
    assert changes[0]["section_key"] == "section_3"


def test_annotation_removed(base_schema):
    new = copy.deepcopy(base_schema)
    del new["section_2"]["annotations"]["annotation_1"]

    changes = diff_schemas(base_schema, new)
    assert len(changes) == 1
    assert changes[0]["kind"] == "annotation_removed"
    assert changes[0]["section_key"] == "section_2"
    assert changes[0]["annotation_key"] == "annotation_1"


def test_dropdown_options_change(base_schema):
    new = copy.deepcopy(base_schema)
    new["section_1"]["annotations"]["annotation_1"]["options"] = [
        "positive", "negative", "neutral", "mixed",
    ]

    changes = diff_schemas(base_schema, new)
    assert len(changes) == 1
    change = changes[0]
    assert change["field"] == "options"
    assert change["old"] == ["positive", "negative", "neutral"]
    assert change["new"] == ["positive", "negative", "neutral", "mixed"]


def test_header_column_change(base_schema):
    new = copy.deepcopy(base_schema)
    new["header_column"] = "doc_id"

    changes = diff_schemas(base_schema, new)
    assert len(changes) == 1
    change = changes[0]
    assert change["scope"] == "top"
    assert change["field"] == "header_column"
    assert change["old"] == "title"
    assert change["new"] == "doc_id"


def test_section_name_change_emits_field_change(base_schema):
    new = copy.deepcopy(base_schema)
    new["section_1"]["section_name"] = "Polarity"

    changes = diff_schemas(base_schema, new)
    assert len(changes) == 1
    change = changes[0]
    assert change["scope"] == "section"
    assert change["section_key"] == "section_1"
    assert change["field"] == "section_name"


def test_likert_range_change(base_schema):
    new = copy.deepcopy(base_schema)
    new["section_2"]["annotations"]["annotation_1"]["max_value"] = 7

    changes = diff_schemas(base_schema, new)
    assert len(changes) == 1
    assert changes[0]["field"] == "max_value"
    assert changes[0]["old"] == 5
    assert changes[0]["new"] == 7


def test_group_by_section_separates_top_and_buckets(base_schema):
    new = copy.deepcopy(base_schema)
    new["header_column"] = "doc_id"
    new["section_1"]["annotations"]["annotation_1"]["tooltip"] = "changed"

    changes = diff_schemas(base_schema, new)
    top, buckets = group_by_section(changes)
    assert len(top) == 1 and top[0]["field"] == "header_column"
    assert len(buckets) == 1
    assert buckets[0]["section_key"] == "section_1"
    assert len(buckets[0]["changes"]) == 1


def test_empty_schemas():
    assert diff_schemas({}, {}) == []
    assert diff_schemas(None, None) == []
