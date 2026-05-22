"""Unit tests for commands/_common.py."""
import pytest

from commands._common import parse_kv, tags_to_dict, tags_match


def test_parse_kv_simple():
    assert parse_kv("Owner=alice") == ("Owner", "alice")


def test_parse_kv_empty_value():
    assert parse_kv("Owner=") == ("Owner", "")


def test_parse_kv_value_with_equals():
    assert parse_kv("Note=key=value") == ("Note", "key=value")


def test_parse_kv_no_key_raises():
    with pytest.raises(ValueError):
        parse_kv("=alice")


def test_tags_to_dict_empty():
    assert tags_to_dict(None) == {}
    assert tags_to_dict([]) == {}


def test_tags_to_dict_roundtrip():
    assert tags_to_dict([{"Key": "A", "Value": "1"}, {"Key": "B", "Value": "2"}]) == {"A": "1", "B": "2"}


def test_tags_match_all_match():
    assert tags_match({"A": "1", "B": "2"}, [("A", "1")], [])


def test_tags_match_missing_value_fails():
    assert not tags_match({"A": "1"}, [("A", "2")], [])


def test_tags_match_missing_key_filter():
    assert tags_match({"A": "1"}, [], ["B"])
    assert not tags_match({"A": "1", "B": "2"}, [], ["B"])


def test_tags_match_no_filter():
    # Empty filter matches anything.
    assert tags_match({}, [], [])
    assert tags_match({"A": "1"}, [], [])
