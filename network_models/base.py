"""Shared strict base model for every domain.

Depends only on ``pydantic>=2.5`` so the package stays portable and can be
vendored here or extracted into its own shared repository without change.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class StrictModel(BaseModel):
    """Base for every model: reject unknown keys, strip strings, validate writes."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
    )


class ComputedFieldModel(StrictModel):
    """A :class:`StrictModel` that tolerates round-tripping its own computed fields.

    ``@computed_field`` values are emitted by ``model_dump()`` but are not model
    fields, so feeding a dump back through ``model_validate()`` would trip
    ``extra="forbid"``. This drops *only* the model's own computed-field keys on
    input (genuinely unknown keys are still rejected), so a dump round-trips.
    """

    @model_validator(mode="before")
    @classmethod
    def _drop_computed_fields(cls, data):
        computed = getattr(cls, "model_computed_fields", None)
        if computed and isinstance(data, dict):
            overlap = computed.keys() & data.keys()
            if overlap:
                return {k: v for k, v in data.items() if k not in overlap}
        return data


__all__ = ["StrictModel", "ComputedFieldModel"]
