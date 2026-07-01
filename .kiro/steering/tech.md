# Tech

## Stack

- **Language:** Python (`requires-python >= 3.10`; support floor is 3.10 — do not
  use 3.11+ only features such as `enum.StrEnum`).
- **Core dependency:** `pydantic >= 2.5` (Pydantic v2 only).
- **Standard library only** beyond Pydantic. The package must stay portable and
  free of application imports. `scripts/` may use extra tools (e.g. `PyYAML`) but
  the `network_models/` package itself must not.
- **Build backend:** setuptools (`setuptools >= 68`), configured in
  `pyproject.toml`.
- **Testing:** `pytest >= 7` (optional `test` extra).

## Conventions

- All models inherit from `StrictModel` (`network_models/base.py`): `extra="forbid"`,
  `str_strip_whitespace=True`, `validate_assignment=True`, `use_enum_values=False`.
- Constrained string fields are `str`-valued enums built via the `_str_enum`
  helper (`network_models/_enum.py`) from **verbatim** value lists. The value list
  is the single, auditable source of truth — keep values byte-for-byte identical
  to upstream schemas.
- Enum value lists live as module-level constants in each domain's `vocab.py`.
  Adding a value should be a one-line change. Keep an `"other"` escape hatch
  where appropriate.
- Use `from __future__ import annotations` at the top of modules.
- Each subpackage defines `__all__`; everything is re-exported from the top-level
  `network_models` package.
- Module docstrings explain intent and portability constraints — preserve this
  style.

## Common commands

```bash
# Install (editable) with test extras
python -m pip install -e ".[test]"

# Run the test suite
python -m pytest tests/test_models.py -q
# or run the test file directly
python tests/test_models.py

# Validate models against the real Nautobot devicetype-library (integration test)
python scripts/import_devicetype_library.py /path/to/devicetype-library

# Same, but also persist validated devices as JSON under converted/ (gitignored)
python scripts/import_devicetype_library.py /path/to/devicetype-library --out
```
