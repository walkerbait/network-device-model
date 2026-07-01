# Structure

## Top-level layout

```
network_models/        # the package (portable: pydantic + stdlib only)
scripts/               # tooling (may use extra deps, e.g. PyYAML)
tests/                 # pytest suite (test_models.py)
converted/             # gitignored output from import script --out
pyproject.toml         # setuptools build + deps
README.md              # usage, model map, extraction notes
```

## Package organization (`network_models/`)

Shared building blocks live at the top; everything else is split into domains.

```
network_models/
  __init__.py          # re-exports everything; defines top-level __all__ + __version__
  base.py              # StrictModel — the strict base every model inherits
  _enum.py             # _str_enum helper: verbatim value lists -> str-valued enums
  device/              # reusable device *type* definitions
    vocab.py           #   value lists + enums (Nautobot + Cisco NaC vocab)
    components.py      #   Interface, ConsolePort, PowerPort, ...
    definition.py      #   DeviceDefinition, DeviceDefinitionLibrary, STIG, NaC
  stig/                # STIG catalog + vocab
    vocab.py           #   RuleSeverity, StigType, AssignmentStatus, TargetLayer
    catalog.py         #   StigRule, StigProfile, Stig, StigCatalog
  system/              # deployed *system* topology + L2 config
    vocab.py           #   classification/environment/ATO + L2 enums
    l2.py              #   Vlan, VlanRange, TrunkAllowedVlans, Switchport, SpanningTree
    topology.py        #   Enclave, Component, Endpoint, Connection, System, StigAssignment
```

## Conventions for placement

- **New model** → the domain subpackage it belongs to (`device`, `system`, or
  `stig`). It must inherit from `StrictModel`.
- **New constrained field** → add its value list as a module-level constant in
  that domain's `vocab.py`, then build the enum with `_str_enum`. Keep values
  byte-for-byte identical to the upstream source; adding a value is a one-line
  change. Keep an `"other"` escape hatch where appropriate.
- **Shared logic** → `base.py` (base model config) or `_enum.py` (enum helper).
  Do not duplicate these per domain.

## Import / export rules

- Each subpackage defines its own `__all__`.
- The top-level `network_models/__init__.py` re-exports every domain's `__all__`,
  so consumers can use `from network_models import System` or import a domain
  directly (`from network_models.system import System`).
- When adding a public model, add it to the subpackage's `__all__` so it flows
  through the top-level re-export.

## Portability boundary

- The `network_models/` package must import **only** `pydantic` and the standard
  library — no application imports, no third-party deps beyond Pydantic. This lets
  the package be vendored or extracted to its own repo unchanged.
- `scripts/` is exempt and may use extra tooling (e.g. `PyYAML`).
