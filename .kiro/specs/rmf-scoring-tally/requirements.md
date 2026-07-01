# Requirements Document

## Introduction

This feature **deepens** the RMF (Risk Management Framework) compliance-scoring
math in the portable `network_models` package by extracting it behind one small,
deep value object. Today the same four CKL scoring metrics are **duplicated**:
`Checklist` (in `network_models/system/assessment.py`) exposes `status_counts`,
`cat_open_counts`, `compliance_score`, and `coverage` as `@computed_field`
properties; `AuthorizationPackage` (in `network_models/system/authorization.py`)
re-implements the *same four* system-wide and adds `component_scores`. The RMF
conventions — `assessable = total − Not_Applicable`, empty population → `100.0`,
`Not_Reviewed` stays in the denominator, and `round(..., 1)` — are restated in
both files and are **drift-prone**. The seed `{s: 0 for s in CHECKLIST_STATUSES}`
appears three times.

This spec introduces a single **module** — `network_models/system/scoring.py` —
holding a small **interface**, the `StatusTally` value object. A tally takes a
sequence of evaluated results (each exposing a CKL `status` and a derived `cat`)
and exposes the four metrics behind one seam. `Checklist` and
`AuthorizationPackage` both derive **through** it, giving the design **locality**
(one place the RMF stance lives) and **leverage** (reused at both the checklist
and the system altitude). The refactor is behavior-preserving: the public
`@computed_field` names and their emitted values in `model_dump()` stay
**byte-identical**. `StatusTally` is a pure internal helper (a frozen dataclass,
not a Pydantic model, never serialized), so the model **schema is unchanged**.

The tally is an internal implementation **seam**, not a schema change. All work
stays inside the portable package (Pydantic v2 + standard library only) with no
new dependencies. This requirements document is derived from the design at
`.kiro/specs/rmf-scoring-tally/design.md`, which remains the source of truth.

## Glossary

- **RMF**: Risk Management Framework — the NIST 800-37 process whose STIG/CKL
  assessment scoring this feature concentrates.
- **CKL status**: One of the four verbatim STIG-Viewer rule-result strings —
  `Open`, `NotAFinding`, `Not_Reviewed`, `Not_Applicable` — held in
  `CHECKLIST_STATUSES` (`network_models/system/vocab.py`).
- **CAT (Category)**: The DISA severity label (`CAT I` / `CAT II` / `CAT III`)
  derived from XCCDF severity via `SEVERITY_TO_CAT`; `None`/`"unknown"` otherwise.
- **The four metrics**: `status_counts`, `cat_open_counts`, `compliance_score`,
  and `coverage` — the scoring surface duplicated across `Checklist` and
  `AuthorizationPackage`.
- **Assessable**: `total − Not_Applicable` — the compliance-score denominator;
  `Not_Reviewed` deliberately remains inside it (conservative RMF stance).
- **Scoring_Module**: The new `network_models/system/scoring.py` module.
- **StatusTally**: The deep value object (a frozen `dataclass`) defined in the
  Scoring_Module; the single source of truth for the four metrics.
- **Tally_Interface**: The public surface of `StatusTally` — its constructors
  (`from_results`, `from_status_pairs`), aggregation (`__add__`), and the four
  metrics.
- **Evaluated result**: Any object exposing a `.status` (str-able CKL status) and
  a `.cat` (`Optional[str]`); `RuleResult` is the concrete case.
- **Checklist**: `network_models.system.assessment.Checklist` — one benchmark
  evaluated against one target (a CKL), holding `RuleResult` lines.
- **AuthorizationPackage**: `network_models.system.authorization.AuthorizationPackage`
  — the system-wide RMF package aggregating many checklists.
- **ComputedFieldModel**: The `network_models.base` base that lets a model
  round-trip its own `@computed_field` outputs through `model_validate`.
- **StrictModel**: The strict Pydantic base (`extra="forbid"`,
  `str_strip_whitespace=True`, `validate_assignment=True`).
- **Serialization parity**: The property that `model_dump(mode="json")` output
  for `Checklist` and `AuthorizationPackage` is byte-identical before and after
  the refactor.

## Requirements

### Requirement 1: StatusTally is the single source of truth for RMF scoring

**User Story:** As a model author, I want one deep value object that computes the
four RMF metrics from a sequence of evaluated results, so that the scoring math
lives in exactly one place instead of being duplicated across two models.

#### Acceptance Criteria

1. THE Scoring_Module SHALL be `network_models/system/scoring.py` and SHALL
   define `StatusTally`.
2. THE StatusTally SHALL expose the four metrics `status_counts`,
   `cat_open_counts`, `compliance_score`, and `coverage`.
3. THE StatusTally SHALL provide a constructor `from_results(results)` that
   consumes any iterable of evaluated results, each exposing `.status` and `.cat`.
4. THE StatusTally SHALL provide a constructor `from_status_pairs(pairs)` that
   consumes an iterable of `(status, cat)` tuples so scoring can be exercised
   without constructing `RuleResult` instances.
5. THE StatusTally SHALL support system-wide aggregation across many checklists,
   exposed as an `__add__` that combines two tallies into one.
6. THE StatusTally SHALL import only the Python standard library (`dataclasses`,
   `typing`) plus `CHECKLIST_STATUSES` from `network_models.system.vocab`, and
   SHALL NOT import Pydantic.

### Requirement 2: One definition of the RMF conventions

**User Story:** As a maintainer, I want the RMF scoring conventions stated once,
so that the assessable rule, the empty-population rule, the Not_Reviewed stance,
and the rounding cannot drift between the checklist and the system altitude.

#### Acceptance Criteria

1. THE StatusTally SHALL define `assessable` as `total − Not_Applicable`, where
   `total` is the sum of `status_counts` values.
2. THE StatusTally SHALL keep `Not_Reviewed` inside the compliance-score
   denominator (i.e. it is NOT subtracted from `assessable`).
3. WHEN `assessable` is less than or equal to zero, THE StatusTally SHALL return
   `compliance_score` equal to `100.0`.
4. WHEN `total` is less than or equal to zero, THE StatusTally SHALL return
   `coverage` equal to `100.0`.
5. THE StatusTally SHALL compute `compliance_score` as
   `round(100.0 * NotAFinding / assessable, 1)`.
6. THE StatusTally SHALL compute `coverage` as
   `round(100.0 * (total − Not_Reviewed) / total, 1)`.
7. THE StatusTally SHALL seed `status_counts` with every value in
   `CHECKLIST_STATUSES` set to zero, in `CHECKLIST_STATUSES` order, from a single
   seed helper (replacing the three restated `{s: 0 for s in CHECKLIST_STATUSES}`
   literals).
8. THE StatusTally SHALL populate `cat_open_counts` only with CAT labels that have
   at least one `Open` finding (no zero-seeded labels), keyed by `cat or "unknown"`.

### Requirement 3: Checklist delegates its four computed fields to the tally

**User Story:** As a model author, I want `Checklist`'s four `@computed_field`
properties to derive through a `StatusTally`, so that the checklist no longer
restates the scoring math.

#### Acceptance Criteria

1. THE Checklist `status_counts`, `cat_open_counts`, `compliance_score`, and
   `coverage` computed fields SHALL each derive from a `StatusTally` built from
   `self.results`.
2. THE Checklist SHALL retain all four properties as `@computed_field`s with
   unchanged names, so `model_dump()` continues to emit them.
3. THE Checklist SHALL NOT restate the `assessable`, empty→`100.0`,
   `Not_Reviewed`, or rounding conventions inline; those live only in the tally.
4. WHEN a Checklist has no results, THE Checklist SHALL report `compliance_score`
   equal to `100.0` and `coverage` equal to `100.0`.

### Requirement 4: AuthorizationPackage delegates all scoring to the tally

**User Story:** As a model author, I want `AuthorizationPackage`'s four
system-wide computed fields AND `component_scores` to derive through the tally, so
that the system altitude reuses the exact same RMF math.

#### Acceptance Criteria

1. THE AuthorizationPackage `status_counts`, `cat_open_counts`,
   `compliance_score`, and `coverage` computed fields SHALL each derive from a
   `StatusTally` aggregated across every checklist's results.
2. THE AuthorizationPackage `component_scores` method SHALL derive each
   per-component `status_counts` from a `StatusTally` and SHALL remain a plain
   method (NOT a `@computed_field`).
3. WHERE a checklist has no `component`, THE AuthorizationPackage
   `component_scores` SHALL key that checklist's contribution under `__system__`.
4. THE AuthorizationPackage SHALL NOT restate the RMF conventions or the
   `{s: 0 for s in CHECKLIST_STATUSES}` seed inline.
5. THE AuthorizationPackage `rolled_up_control_status` and
   `draft_poam_from_findings` methods SHALL be unchanged by this feature.

### Requirement 5: System-wide aggregation preserves the checklist math

**User Story:** As a compliance consumer, I want system-wide scores to equal the
scores obtained by concatenating every checklist's results, so that the aggregate
and per-checklist numbers stay consistent.

#### Acceptance Criteria

1. WHEN an AuthorizationPackage aggregates checklists, THE StatusTally result
   SHALL equal the tally of the flattened sequence of all checklist results.
2. THE StatusTally aggregation SHALL be associative and commutative on
   `status_counts`, so grouping order does not change the counts.
3. WHEN an AuthorizationPackage has no checklists, THE AuthorizationPackage SHALL
   report `status_counts` fully seeded to zero, `compliance_score` equal to
   `100.0`, and `coverage` equal to `100.0`.

### Requirement 6: Serialization parity (golden)

**User Story:** As a downstream consumer of exports, I want the serialized output
of `Checklist` and `AuthorizationPackage` to be identical before and after the
refactor, so that the System Viewer and JSON exports are unaffected.

#### Acceptance Criteria

1. THE `Checklist.model_dump(mode="json")` output SHALL be byte-identical before
   and after the refactor for a representative fixture, including the emitted
   `@computed_field` key set and every metric value.
2. THE `AuthorizationPackage.model_dump(mode="json")` output SHALL be
   byte-identical before and after the refactor for a representative fixture.
3. THE emitted `status_counts` mapping SHALL preserve `CHECKLIST_STATUSES` key
   order.
4. THE emitted `cat_open_counts` mapping SHALL preserve first-seen CAT-label
   order across the result sequence.
5. WHEN a serialized `Checklist` or `AuthorizationPackage` dump is fed back
   through `model_validate`, THE ComputedFieldModel SHALL still drop the computed
   keys so the round-trip succeeds.

### Requirement 7: StatusTally is an internal seam, not a schema change

**User Story:** As a schema consumer, I want the tally to be a pure internal
helper, so that no public model field, computed field, or JSON schema changes.

#### Acceptance Criteria

1. THE StatusTally SHALL be a frozen `dataclass` (or equivalent non-serialized
   class) and SHALL NOT be a Pydantic model.
2. THE StatusTally SHALL NOT appear as a field on `Checklist`,
   `AuthorizationPackage`, `RuleResult`, or any other model.
3. THE public field set of `RuleResult`, `Checklist`, and `AuthorizationPackage`
   SHALL be unchanged by this feature.
4. THE severity-to-CAT mapping and `RuleResult.cat` derivation SHALL be unchanged
   by this feature.

### Requirement 8: Direct scoring tests (`tests/test_scoring.py`)

**User Story:** As a maintainer, I want the scoring math tested directly, so that
the single source of truth is verified independently of the models.

#### Acceptance Criteria

1. THE test suite SHALL include `tests/test_scoring.py` exercising `StatusTally`
   directly via `from_status_pairs` and/or `from_results`.
2. THE test suite SHALL verify an empty population yields `compliance_score`
   equal to `100.0` and `coverage` equal to `100.0`.
3. THE test suite SHALL verify an all-`Not_Applicable` population yields
   `compliance_score` equal to `100.0` (assessable is zero) and `coverage` equal
   to `100.0`.
4. THE test suite SHALL verify a mixed population reproduces the documented
   `assessable = total − Not_Applicable`, `Not_Reviewed`-in-denominator, and
   one-decimal rounding conventions.
5. THE test suite SHALL verify `cat_open_counts` groups `Open` findings by CAT
   label and omits labels with no open findings.
6. THE test suite SHALL verify `StatusTally.__add__` aggregation equals the tally
   of the concatenated inputs.

### Requirement 9: Model-level scoring tests for Checklist and AuthorizationPackage

**User Story:** As a maintainer, I want the scoring verified at the model level so
that delegation and serialization parity are covered end to end.

#### Acceptance Criteria

1. THE test suite SHALL verify a `Checklist` with mixed statuses reports the
   expected `status_counts`, `cat_open_counts`, `compliance_score`, and
   `coverage`.
2. THE test suite SHALL verify an empty `Checklist` reports `compliance_score`
   and `coverage` equal to `100.0`.
3. THE test suite SHALL verify system-wide aggregation across multiple checklists
   in an `AuthorizationPackage` equals the tally of all their results combined.
4. THE test suite SHALL verify `component_scores` keys system-level checklists
   (no `component`) under `__system__` and keys component-bound checklists by
   their `component` id.
5. THE test suite SHALL assert serialization parity: the `model_dump(mode="json")`
   output of representative `Checklist` and `AuthorizationPackage` fixtures equals
   committed golden expectations.

### Requirement 10: Portability, no new dependencies, and re-export hygiene

**User Story:** As a maintainer, I want the change to stay portable with no new
dependencies and clean re-exports, so that the package can still be vendored
unchanged.

#### Acceptance Criteria

1. THE Scoring_Module SHALL depend only on Pydantic-free standard library plus
   `network_models.system.vocab`, introducing no new third-party dependency.
2. THE `network_models/system/scoring.py` module SHALL declare an `__all__`
   listing `StatusTally`.
3. WHERE `StatusTally` is surfaced beyond the module, THE re-export SHALL keep it
   an internal helper importable from `network_models.system.scoring`, without
   requiring it to be part of the top-level public model surface.
4. THE change SHALL introduce no import cycle: `scoring.py` SHALL NOT import
   `assessment.py` or `authorization.py`.

## Non-Goals / Out of Scope

The following are deliberately excluded. The boundary is documented so it is
explicit, but no requirement here demands their implementation.

1. **No change to public model fields.** The fields of `RuleResult`,
   `Checklist`, and `AuthorizationPackage` are untouched; this is a pure internal
   deepening.
2. **No change to the CAT / severity mapping.** `SEVERITY_TO_CAT` and
   `RuleResult.cat` stay exactly as they are; the tally consumes `.cat`, it does
   not recompute severity.
3. **No change to `rolled_up_control_status` or `draft_poam_from_findings`.**
   Those non-scoring helpers on `AuthorizationPackage` are out of scope.
4. **No new metric.** The feature concentrates the existing four metrics (plus
   `component_scores`); it does not add scoring surfaces.
5. **No shared `cat_for(severity)` helper here.** A separate `concentrate-shared-rules`
   spec may introduce a shared `cat_for(severity)` helper; this spec does not
   depend on it and does not create it. The tally relies only on results already
   exposing `.cat`.
</content>
</invoke>
