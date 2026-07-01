# Requirements Document

## Introduction

This feature **concentrates three smeared, shallow duplications** in the portable
`network_models` package into single, honest homes. It is a **locality** refactor,
not new behavior: every observable output — `.cat` values, validator error
semantics, and consistency-check results — must be **byte-for-byte identical**
before and after. The three concentrations are:

1. **One severity→CAT home.** The rule "map DISA XCCDF `@severity` to a CAT label"
   is currently a byte-identical `.cat` property triplicated on three models
   (`StigRule`, `RuleResult`, `PoamItem`). It becomes a single free function
   `cat_for(severity)` in `network_models/stig/vocab.py`; the three properties
   delegate to it.
2. **One uniqueness helper.** The idiom `len(x) != len(set(x))` → raise
   `ValueError` is hand-inlined across the tree (21 occurrences in 6 modules). It
   becomes a single helper `require_unique(values, message)` in a new private
   module `network_models/_validators.py`; every site delegates to it.
3. **One honest home for the drift check.** `io/consistency.py::check_result_consistency`
   does **no I/O and touches no XML** — it is a pure model-vs-model drift check
   comparing a `StigCatalog` (stig domain) against a `Checklist` (system domain),
   yet it lives in the opt-in XML-ingestion `io/` seam, which is dishonest
   placement. It moves to `network_models/system/consistency.py` (its honest
   domain home), with a back-compat re-export kept in `io/` so existing imports
   still work.

**Strength: Speculative.** The deletion test for this change is weak: nothing is
*removed* from the interface and no new **depth** is created. Each duplication is
individually a one-liner, and the concentration mostly buys **locality** (one
place to read/change the rule) and honest **module** boundaries, not a smaller or
more powerful interface. This document is honest about that: the value is
maintainability and truthful placement, not a structural win. It is included
because the three duplications are real, the parity bar makes the change low-risk,
and the resulting seams (`cat_for`, `require_unique`, `system/consistency.py`) are
cheap for other specs to build on.

Everything stays inside the portable core (Pydantic v2 + standard library only).
Nothing new reaches into `io`'s optional dependencies (`defusedxml`). This
requirements document is derived from the approved design at
`.kiro/specs/concentrate-shared-rules/design.md`, which remains the source of
truth.

## Glossary

- **CAT (Category)**: The DISA severity label (CAT I / CAT II / CAT III) derived
  from XCCDF `@severity` (`high` / `medium` / `low`); `None` for `unknown` or an
  unset severity.
- **SEVERITY_TO_CAT**: The verbatim mapping `{"high": "CAT I", "medium": "CAT II",
  "low": "CAT III"}` in `network_models/stig/vocab.py` — the single source of truth
  for the severity→CAT rule.
- **cat_for**: The new free function `cat_for(severity) -> Optional[str]` in
  `stig/vocab.py` that wraps `SEVERITY_TO_CAT`; the single callable home for the
  severity→CAT rule.
- **cat property**: The `@property def cat` on `StigRule`, `RuleResult`, and
  `PoamItem` that returns the model's CAT label; after this feature each delegates
  to `cat_for`.
- **Uniqueness idiom**: The inlined pattern `if len(values) != len(set(values)):
  raise ValueError(<message>)` used to reject duplicates in a list.
- **require_unique**: The new helper `require_unique(values, message) -> None` in
  `network_models/_validators.py` that raises `ValueError(message)` on duplicates
  and returns `None` otherwise; the single home for the uniqueness idiom.
- **Drift check**: `check_result_consistency(checklist, catalog) -> list[str]`, a
  pure model-vs-model comparison that returns advisory warning strings and never
  raises.
- **StrictModel**: The strict Pydantic base (`extra="forbid"`,
  `str_strip_whitespace=True`, `validate_assignment=True`) every model inherits.
- **Portable core**: The `network_models/` package excluding `network_models/io/`
  — imports only Pydantic and the Python standard library.
- **io seam**: `network_models/io/`, the opt-in ingestion layer that may use the
  optional `defusedxml` dependency; deliberately not imported by the core.
- **Parity**: The acceptance bar for this feature — identical observable behavior
  (`.cat` values, validator `ValueError` messages, drift-check output) before and
  after.

## Requirements

### Requirement 1: Single severity→CAT home (`cat_for`)

**User Story:** As a model author, I want the severity→CAT rule expressed once as a
free function, so that the mapping has a single source of truth and the three model
properties stop repeating it.

#### Acceptance Criteria

1. THE stig vocab module SHALL define a free function
   `cat_for(severity) -> Optional[str]` in `network_models/stig/vocab.py` that
   returns `SEVERITY_TO_CAT.get(str(severity))`.
2. WHEN `cat_for` is called with a severity whose string form is `high`, `medium`,
   or `low`, THE function SHALL return `CAT I`, `CAT II`, or `CAT III` respectively.
3. WHEN `cat_for` is called with a severity whose string form is `unknown` or any
   value absent from `SEVERITY_TO_CAT`, THE function SHALL return `None`.
4. WHEN `cat_for` is called with `None`, THE function SHALL return `None` and SHALL
   NOT raise.
5. THE `StigRule.cat`, `RuleResult.cat`, and `PoamItem.cat` properties SHALL each
   delegate to `cat_for`, preserving their existing `None`-guarding behavior where
   present (`PoamItem.severity` is optional).
6. THE severity→CAT rule SHALL exist in exactly one executable location
   (`cat_for` over `SEVERITY_TO_CAT`); no `.cat` property SHALL re-inline
   `SEVERITY_TO_CAT.get(...)` after this feature.
7. THE `cat_for` function SHALL be delivered as a free function rather than a shared
   mixin or base-class property, to keep coupling minimal across the `stig` and
   `system` domains.

### Requirement 2: Single uniqueness helper (`require_unique`)

**User Story:** As a model author, I want one uniqueness helper, so that every
"reject duplicates" check reads and behaves identically and lives in one place.

#### Acceptance Criteria

1. THE portable core SHALL define `require_unique(values, message) -> None` in a new
   module `network_models/_validators.py` that raises `ValueError(message)` when
   `values` contains a duplicate and returns `None` otherwise.
2. THE `require_unique` helper SHALL preserve the semantics of `len(values) !=
   len(set(values))` — it detects duplicates by hashable-set comparison and does not
   reorder, deduplicate, or return `values`.
3. WHEN `values` is empty, THE `require_unique` helper SHALL return `None` without
   raising.
4. THE `require_unique` module SHALL import only the Python standard library and
   SHALL NOT import Pydantic or any third-party package.
5. THE feature SHALL replace every inlined `!= len(set(` uniqueness site in the
   portable core with a call to `require_unique`, enumerated exhaustively in design
   Part 2 (§2.2) across `stig/catalog.py`, `device/definition.py`,
   `system/topology.py`, `system/l2.py`, `system/authorization.py`, and
   `system/assessment.py`.
6. WHERE a migrated site is guarded (e.g. an optional field that may be `None`, as in
   `system/l2.py` `TrunkAllowedVlans`), THE feature SHALL preserve the guard so the
   helper is only called with a real sequence.
7. AFTER migration, EACH migrated site SHALL raise `ValueError` with the **same
   message string** it raised before, so field/model validator error semantics are
   unchanged.

### Requirement 3: Relocate the drift check to its honest domain home

**User Story:** As a package maintainer, I want the pure model-vs-model drift check
to live in the domain it belongs to rather than in the XML-ingestion seam, so that
module placement is honest and the core does not pretend the check needs `io`.

#### Acceptance Criteria

1. THE feature SHALL move `check_result_consistency` to a new module
   `network_models/system/consistency.py` with byte-identical behavior.
2. THE relocated `check_result_consistency` SHALL import `StigCatalog` from
   `network_models.stig.catalog` and `Checklist` from
   `network_models.system.assessment`, both inside the portable core, forming an
   acyclic import (the `system` domain already depends on `stig`).
3. THE relocated module SHALL import only Pydantic and the Python standard library
   and SHALL NOT import anything from `network_models.io`.
4. THE feature SHALL keep a back-compat re-export so
   `from network_models.io import check_result_consistency` and
   `from network_models.io.consistency import check_result_consistency` continue to
   resolve to the relocated function.
5. THE back-compat re-export SHALL be a soft-deprecation: `io/consistency.py`
   becomes a thin shim that imports the function from
   `network_models.system.consistency` and re-exports it via `__all__`, and its
   docstring SHALL note the canonical home.
6. WHEN `check_result_consistency` is called with the same `checklist` and `catalog`
   before and after the move, THE function SHALL return an identical list of warning
   strings, in identical order.

### Requirement 4: Behavior parity (no behavior change anywhere)

**User Story:** As a consumer of these models, I want a pure relocation with zero
behavior change, so that upgrading is risk-free and needs no code changes on my side.

#### Acceptance Criteria

1. THE `.cat` value returned by `StigRule`, `RuleResult`, and `PoamItem` SHALL be
   identical for every severity input before and after this feature.
2. THE `ValueError` raised at every migrated uniqueness site SHALL carry the same
   message string as before, so tests asserting on validator messages continue to
   pass unchanged.
3. THE `check_result_consistency` output SHALL be identical for every input before
   and after the move.
4. THE feature SHALL NOT add, remove, or reorder any model field, enum value, or
   vocabulary entry, and SHALL NOT change any validator's trigger conditions.
5. THE feature SHALL NOT change the drift-check algorithm (rule-id matching,
   severity comparison, CCI-set comparison, advisory-list return, never raises).

### Requirement 5: Public surface and re-export updates

**User Story:** As a package consumer, I want the public names and re-exports kept
coherent, so that the new homes are importable and the moved function stays reachable
from its old path.

#### Acceptance Criteria

1. THE `stig/vocab.py` `__all__` SHALL add `cat_for` so it re-exports through the
   `stig` subpackage and the top-level `network_models` package.
2. THE `network_models/_validators.py` module SHALL declare `__all__ =
   ["require_unique"]`; being a private (underscore) module, it SHALL NOT be
   re-exported by the top-level package.
3. THE `network_models/system/consistency.py` module SHALL declare `__all__ =
   ["check_result_consistency"]`, and `system/__init__.py` SHALL re-export it so it
   flows through to the top-level `network_models` package.
4. THE `network_models/io/__init__.py` SHALL continue to expose
   `check_result_consistency` in its `__all__` via the `io/consistency.py` shim, so
   the opt-in `io` import path is unbroken.
5. THE steering `structure.md` SHALL be updated to record the new
   `network_models/_validators.py` helper module, the `cat_for` home in
   `stig/vocab.py`, and the `system/consistency.py` relocation (with the `io` shim
   noted as soft-deprecated).

### Requirement 6: Portability preserved

**User Story:** As a maintainer of the portability boundary, I want the whole change
to stay in the pydantic+stdlib core, so that nothing new couples the core to `io`'s
optional dependencies.

#### Acceptance Criteria

1. THE `cat_for` function, the `require_unique` helper, and the relocated
   `check_result_consistency` SHALL each import only Pydantic and the Python standard
   library.
2. THE portable core (`network_models/` excluding `network_models/io/`) SHALL NOT
   gain any import of `network_models.io` or of any `io` optional dependency
   (`defusedxml`).
3. WHEN `import network_models` is executed in an environment without the `io` extra
   installed, THE package SHALL import successfully and `check_result_consistency`
   SHALL be reachable via `network_models.system.consistency` and the top-level
   package without importing `io`.

## Non-Goals / Out of Scope

1. **No new validation behavior.** `require_unique` reproduces the existing idiom
   exactly; no new uniqueness checks are added and no existing one is tightened or
   relaxed.
2. **No severity/CAT vocabulary changes.** `SEVERITY_TO_CAT`, `RULE_SEVERITIES`, and
   the CAT labels are untouched; `cat_for` is a wrapper, not a redefinition.
3. **No change to the drift-check algorithm.** The relocation preserves rule-id
   matching, the severity and CCI-set comparisons, the advisory-list return type,
   and the never-raises contract.
4. **No new dependencies.** Everything stays Pydantic + standard library; no
   third-party package is added, and the `io` optional deps are not pulled into the
   core.
5. **No interface deepening.** This is deliberately a locality/placement refactor
   (see the Speculative framing in the Introduction); it does not attempt to shrink
   or generalize any public interface beyond concentrating the three duplications.
</content>
</invoke>
