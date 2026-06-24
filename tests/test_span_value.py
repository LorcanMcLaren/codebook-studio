import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.span_value import parse_span_value, serialize_span_value


# --------------------------------------------------------------------------
# parse_span_value
# --------------------------------------------------------------------------

def test_parse_none_and_empty_return_empty_list():
    assert parse_span_value(None) == []
    assert parse_span_value("") == []
    assert parse_span_value("   ") == []


def test_parse_valid_json_string():
    raw = '[{"start": 0, "end": 4, "text": "fear", "label": "Emotion"}]'
    assert parse_span_value(raw) == [
        {"start": 0, "end": 4, "text": "fear", "label": "Emotion"}
    ]


def test_parse_malformed_json_returns_empty_list():
    assert parse_span_value("[not valid json") == []
    assert parse_span_value("{}") == []  # valid JSON, but not a list


def test_parse_list_passthrough_copies_dicts():
    original = [{"start": 1, "end": 2, "text": "x"}]
    parsed = parse_span_value(original)
    assert parsed == original
    # Must be a copy, not the same object, so later mutation can't leak back.
    assert parsed[0] is not original[0]


def test_parse_list_drops_non_dict_entries():
    assert parse_span_value([{"start": 0, "end": 1}, "junk", 5]) == [
        {"start": 0, "end": 1}
    ]


def test_parse_nan_returns_empty_list():
    pd = pytest.importorskip("pandas")
    assert parse_span_value(pd.NA) == []
    assert parse_span_value(float("nan")) == []


# --------------------------------------------------------------------------
# serialize_span_value
# --------------------------------------------------------------------------

def test_serialize_empty_returns_empty_string():
    assert serialize_span_value([]) == ""
    assert serialize_span_value(None) == ""


def test_serialize_coerces_offsets_and_keeps_optional_fields():
    out = serialize_span_value([{"start": "3", "end": "7", "text": "word", "label": "L"}])
    assert json.loads(out) == [{"start": 3, "end": 7, "text": "word", "label": "L"}]


def test_serialize_omits_empty_label_but_keeps_text():
    out = serialize_span_value([{"start": 0, "end": 1, "text": "a", "label": ""}])
    assert json.loads(out) == [{"start": 0, "end": 1, "text": "a"}]


def test_serialize_skips_non_dict_entries():
    assert serialize_span_value(["junk", 5]) == ""


def test_serialize_preserves_unicode():
    out = serialize_span_value([{"start": 0, "end": 2, "text": "café"}])
    assert "café" in out  # ensure_ascii=False keeps the literal character


# --------------------------------------------------------------------------
# round trip
# --------------------------------------------------------------------------

def test_round_trip_preserves_spans():
    spans = [
        {"start": 0, "end": 4, "text": "fear", "label": "Emotion"},
        {"start": 10, "end": 15, "text": "anger"},
    ]
    assert parse_span_value(serialize_span_value(spans)) == spans


def test_round_trip_empty():
    assert parse_span_value(serialize_span_value([])) == []
