"""Shared enum-construction helper used across all model domains.

Builds ``str``-valued enums from verbatim value lists so the value list stays the
single, auditable source of truth (matching upstream schemas byte-for-byte).
"""

from __future__ import annotations

import re
from enum import Enum


def _member_name(value: str) -> str:
    """Derive a valid, upper-snake Python identifier from an enum *value*."""
    name = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").upper()
    if not name:
        return "UNSET"
    if name[0].isdigit():
        name = f"N{name}"
    return name


def _str_enum(name: str, values: list[str]) -> type[Enum]:
    """Build a ``str``-valued :class:`Enum` from a verbatim list of values.

    Member *names* are derived automatically so the value list stays the single,
    auditable source of truth (matching the upstream schema byte-for-byte).
    """
    members: dict[str, str] = {}
    for value in values:
        member = _member_name(value)
        candidate, suffix = member, 2
        while candidate in members:
            candidate = f"{member}_{suffix}"
            suffix += 1
        members[candidate] = value
    cls = Enum(name, members, type=str)  # type: ignore[assignment]
    # A functional str-Enum member renders as its *repr* ("InterfaceType.N1000BASE_T")
    # under str()/format()/f-strings, not its value — which would corrupt generated
    # config text. Give the class value-returning dunders. (enum.StrEnum would do this
    # but is 3.11+; the supported floor is 3.10, so assign explicitly.)
    cls.__str__ = lambda self: str(self.value)  # type: ignore[assignment]
    cls.__format__ = lambda self, spec: format(self.value, spec)  # type: ignore[assignment]
    return cls  # type: ignore[return-value]


__all__ = ["_member_name", "_str_enum"]
