"""Serialization invariants for explicitly declared NB04 multivalue fields.

Callers supply the field vocabulary where applicable. These pure functions
perform no file I/O and assign no scientific states or decisions.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable


MULTIVALUE_SEPARATOR = "|"


class NB04SerializationError(ValueError):
    """A multivalue cell or collection violates the serialization contract."""


def _checked_tokens(values: Iterable[str], label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise NB04SerializationError(f"{label} must be a collection of strings")
    try:
        tokens = tuple(values)
    except TypeError as exc:
        raise NB04SerializationError(f"{label} must be a collection of strings") from exc
    seen: set[str] = set()
    for token in tokens:
        if not isinstance(token, str) or not token:
            raise NB04SerializationError(f"{label} contains an empty or non-string token")
        if token != token.strip():
            raise NB04SerializationError(f"{label} token has external whitespace: {token!r}")
        if MULTIVALUE_SEPARATOR in token:
            raise NB04SerializationError(f"{label} token contains the delimiter: {token!r}")
        if token == "NONE":
            raise NB04SerializationError(f"NONE is reserved and cannot be a {label} item")
        if token in seen:
            raise NB04SerializationError(f"duplicate {label} token: {token!r}")
        seen.add(token)
    return tokens


def _canonical_values(
    values: Iterable[str], vocabulary: Collection[str] | None,
) -> tuple[str, ...]:
    allowed = (
        None if vocabulary is None
        else frozenset(_checked_tokens(vocabulary, "vocabulary"))
    )
    tokens = _checked_tokens(values, "values")
    if "UNKNOWN" in tokens:
        if allowed is None or "UNKNOWN" not in allowed:
            raise NB04SerializationError("UNKNOWN requires explicit vocabulary authorization")
        if len(tokens) != 1:
            raise NB04SerializationError("UNKNOWN must appear alone")
    if allowed is not None:
        for token in tokens:
            if token not in allowed:
                raise NB04SerializationError(f"token outside the field vocabulary: {token!r}")
    return tuple(sorted(tokens))


def serialize_multivalue(
    values: Iterable[str], *, vocabulary: Collection[str] | None = None,
) -> str:
    """Serialize distinct literal tokens in Unicode codepoint order.

    The empty collection produces ``NONE``. ``NONE`` cannot be a normal item or
    vocabulary member. ``UNKNOWN`` requires explicit vocabulary membership and
    must stand alone. No whitespace or Unicode normalization is performed.
    """
    tokens = _canonical_values(values, vocabulary)
    return MULTIVALUE_SEPARATOR.join(tokens) if tokens else "NONE"


def parse_multivalue(
    cell: str, *, vocabulary: Collection[str] | None = None,
) -> tuple[str, ...]:
    """Parse a cell into a sorted tuple, accepting valid noncanonical order.

    Only the literal cell ``NONE`` denotes the empty collection. An empty cell,
    empty token, duplicate, or token with external whitespace is invalid.
    """
    if not isinstance(cell, str) or not cell:
        raise NB04SerializationError("cell must be a non-empty string")
    values = () if cell == "NONE" else cell.split(MULTIVALUE_SEPARATOR)
    return _canonical_values(values, vocabulary)


def validate_multivalue(
    cell: str, *, vocabulary: Collection[str] | None = None,
) -> None:
    """Require a valid cell already in its canonical serialized form."""
    values = parse_multivalue(cell, vocabulary=vocabulary)
    if serialize_multivalue(values, vocabulary=vocabulary) != cell:
        raise NB04SerializationError("cell is not in canonical codepoint order")
