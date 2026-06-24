from __future__ import annotations

import pandas as pd

from utils.adjudication import (
    is_adjudication_filename,
    next_unresolved_index,
    unresolved_applicable_cells,
    unresolved_item_indices,
)


PARENT = "1. Parent_parent"
CHILD = "2. Child_child"


def codebook():
    return {
        "header_column": "sample_id",
        "text_column": "text",
        "section_1": {
            "section_name": "1. Parent",
            "section_instruction": "",
            "annotations": {
                "annotation_1": {
                    "name": "parent",
                    "type": "dropdown",
                    "tooltip": "",
                    "options": ["Yes", "No"],
                }
            },
        },
        "section_2": {
            "section_name": "2. Child",
            "section_instruction": "",
            "annotations": {
                "annotation_1": {
                    "name": "child",
                    "type": "dropdown",
                    "tooltip": "",
                    "options": ["A", "B"],
                    "condition": {
                        "section_key": "section_1",
                        "annotation_key": "annotation_1",
                        "value": "Yes",
                    },
                }
            },
        },
    }


def test_unresolved_cells_only_include_active_blank_annotations():
    data = pd.DataFrame(
        [
            {"sample_id": "S1", "text": "one", PARENT: "Yes", CHILD: ""},
            {"sample_id": "S2", "text": "two", PARENT: "No", CHILD: ""},
            {"sample_id": "S3", "text": "three", PARENT: "", CHILD: ""},
        ]
    )

    cells = unresolved_applicable_cells(codebook(), data)

    assert cells == [
        {
            "row_index": 0,
            "column": CHILD,
            "section_key": "section_2",
            "annotation_key": "annotation_1",
        },
        {
            "row_index": 2,
            "column": PARENT,
            "section_key": "section_1",
            "annotation_key": "annotation_1",
        },
    ]
    assert unresolved_item_indices(codebook(), data) == [0, 2]


def test_next_unresolved_index_wraps():
    data = pd.DataFrame(
        [
            {"sample_id": "S1", "text": "one", PARENT: "Yes", CHILD: "A"},
            {"sample_id": "S2", "text": "two", PARENT: "Yes", CHILD: ""},
            {"sample_id": "S3", "text": "three", PARENT: "Yes", CHILD: ""},
        ]
    )

    assert next_unresolved_index(codebook(), data, 0) == 1
    assert next_unresolved_index(codebook(), data, 1) == 2
    assert next_unresolved_index(codebook(), data, 2) == 1


def test_adjudication_filename_detection():
    assert is_adjudication_filename("outputs/adjudication_queue.csv")
    assert is_adjudication_filename("Adjudication_Queue_round_1.csv")
    assert not is_adjudication_filename("ground-truth.csv")
