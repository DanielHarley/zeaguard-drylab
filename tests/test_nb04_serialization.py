from __future__ import annotations

import ast
from itertools import permutations
from pathlib import Path

import pytest

import zeaguard.nb04_serialization as serialization
from zeaguard.nb04_serialization import (
    MULTIVALUE_SEPARATOR,
    NB04SerializationError,
    parse_multivalue,
    serialize_multivalue,
    validate_multivalue,
)


@pytest.mark.parametrize("cell", ["NONE", "A", "A|B", "A|a|é", "UNKNOWN"])
def test_canonical_round_trip(cell):
    vocabulary = {"A", "B", "a", "é", "UNKNOWN"}
    values = parse_multivalue(cell, vocabulary=vocabulary)
    assert serialize_multivalue(values, vocabulary=vocabulary) == cell
    assert validate_multivalue(cell, vocabulary=vocabulary) is None


def test_serialization_is_independent_of_input_order():
    assert MULTIVALUE_SEPARATOR == "|"
    for values in permutations(("C", "A", "B")):
        assert serialize_multivalue(values) == "A|B|C"


def test_literal_codepoint_order_and_utf8_byte_stability():
    values = ("é", "e\u0301", "😀", "Ω", "a", "A", "Z", "ä")
    expected = "A|Z|a|e\u0301|ä|é|Ω|😀"
    expected_bytes = (
        b"A|Z|a|e\xcc\x81|\xc3\xa4|\xc3\xa9|\xce\xa9|\xf0\x9f\x98\x80"
    )
    for ordered in (values, tuple(reversed(values)), tuple(sorted(values))):
        encoded = serialize_multivalue(ordered)
        assert encoded == expected
        assert encoded.encode("utf-8") == expected_bytes
    assert parse_multivalue(expected) == ("A", "Z", "a", "e\u0301", "ä", "é", "Ω", "😀")


def test_parse_canonicalizes_order_and_validate_rejects_noncanonical_cell():
    assert parse_multivalue("C|A|B") == ("A", "B", "C")
    assert serialize_multivalue(parse_multivalue("C|A|B")) == "A|B|C"
    with pytest.raises(NB04SerializationError, match="canonical"):
        validate_multivalue("C|A|B")


def test_empty_collection_and_none_cell():
    assert serialize_multivalue([]) == "NONE"
    assert serialize_multivalue(iter(()), vocabulary=[]) == "NONE"
    assert parse_multivalue("NONE") == ()
    assert validate_multivalue("NONE") is None


@pytest.mark.parametrize("values", [("A", "A"), ("B", "A", "B")])
def test_serializer_rejects_duplicates_before_set_conversion(values):
    with pytest.raises(NB04SerializationError, match="duplicate"):
        serialize_multivalue(iter(values))


@pytest.mark.parametrize("cell", ["A|A", "B|A|B", "UNKNOWN|UNKNOWN"])
def test_parser_rejects_duplicates(cell):
    with pytest.raises(NB04SerializationError, match="duplicate"):
        parse_multivalue(cell, vocabulary={"A", "B", "UNKNOWN"})


@pytest.mark.parametrize("token", ["A|B", "|", "A|", "|A"])
def test_serializer_rejects_literal_delimiter_in_item(token):
    with pytest.raises(NB04SerializationError, match="delimiter"):
        serialize_multivalue([token])


@pytest.mark.parametrize("cell", ["", "A||B", "|A", "A|", "|"])
def test_empty_cell_and_empty_tokens_are_invalid(cell):
    with pytest.raises(NB04SerializationError, match="empty"):
        parse_multivalue(cell)
    with pytest.raises(NB04SerializationError):
        validate_multivalue(cell)


@pytest.mark.parametrize("values", [("NONE",), ("A", "NONE")])
def test_none_cannot_be_a_collection_item(values):
    with pytest.raises(NB04SerializationError, match="NONE is reserved"):
        serialize_multivalue(values)


@pytest.mark.parametrize("cell", ["NONE|A", "A|NONE", "NONE|NONE"])
def test_none_cannot_coexist_with_tokens(cell):
    with pytest.raises(NB04SerializationError, match="NONE is reserved"):
        parse_multivalue(cell)


def test_none_is_forbidden_in_vocabulary_even_for_empty_values():
    vocabulary = {"NONE", "A"}
    for operation in (
        lambda: serialize_multivalue([], vocabulary=vocabulary),
        lambda: parse_multivalue("NONE", vocabulary=vocabulary),
        lambda: validate_multivalue("A", vocabulary=vocabulary),
    ):
        with pytest.raises(NB04SerializationError, match="NONE is reserved"):
            operation()


@pytest.mark.parametrize("vocabulary", [None, set(), {"A"}])
def test_unknown_requires_explicit_field_authorization(vocabulary):
    for operation in (
        lambda: serialize_multivalue(["UNKNOWN"], vocabulary=vocabulary),
        lambda: parse_multivalue("UNKNOWN", vocabulary=vocabulary),
        lambda: validate_multivalue("UNKNOWN", vocabulary=vocabulary),
    ):
        with pytest.raises(NB04SerializationError, match="explicit vocabulary"):
            operation()


@pytest.mark.parametrize("cell", ["UNKNOWN|A", "A|UNKNOWN"])
def test_authorized_unknown_must_stand_alone(cell):
    vocabulary = {"UNKNOWN", "A"}
    with pytest.raises(NB04SerializationError, match="alone"):
        parse_multivalue(cell, vocabulary=vocabulary)
    with pytest.raises(NB04SerializationError, match="alone"):
        serialize_multivalue(cell.split("|"), vocabulary=vocabulary)


def test_closed_vocabulary_rejects_undeclared_member():
    with pytest.raises(NB04SerializationError, match="outside the field vocabulary"):
        serialize_multivalue(["B"], vocabulary={"A"})
    with pytest.raises(NB04SerializationError, match="outside the field vocabulary"):
        parse_multivalue("A|B", vocabulary={"A"})


@pytest.mark.parametrize("token", [" A", "A ", "\tA", "A\n", "\rA", "\u00a0A"])
def test_external_whitespace_is_rejected_without_correction(token):
    with pytest.raises(NB04SerializationError, match="external whitespace"):
        serialize_multivalue([token])
    with pytest.raises(NB04SerializationError, match="external whitespace"):
        parse_multivalue(token)
    with pytest.raises(NB04SerializationError, match="external whitespace"):
        validate_multivalue("B|" + token)


def test_internal_whitespace_is_preserved():
    assert serialize_multivalue(["A B"]) == "A B"
    assert parse_multivalue("A B") == ("A B",)


@pytest.mark.parametrize("values", [[""], [1], "AB", None])
def test_serializer_rejects_invalid_collection_or_item_types(values):
    with pytest.raises(NB04SerializationError):
        serialize_multivalue(values)


@pytest.mark.parametrize("cell", [None, 1, b"A"])
def test_parser_rejects_nonstring_cell(cell):
    with pytest.raises(NB04SerializationError, match="non-empty string"):
        parse_multivalue(cell)


@pytest.mark.parametrize("vocabulary", [[""], [" A"], ["A|B"], ["A", "A"], "AB"])
def test_malformed_vocabulary_is_rejected(vocabulary):
    with pytest.raises(NB04SerializationError):
        serialize_multivalue(["A"], vocabulary=vocabulary)


def test_production_module_has_only_standard_library_imports():
    tree = ast.parse(Path(serialization.__file__).read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imports.add(node.module)
    assert imports == {"__future__", "collections.abc"}
