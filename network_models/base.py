"""Shared strict base model for every domain.

Depends only on ``pydantic>=2.5`` so the package stays portable and can be
vendored here or extracted into its own shared repository without change.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base for every model: reject unknown keys, strip strings, validate writes."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
    )


__all__ = ["StrictModel"]
