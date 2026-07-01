# Requirements Document

## Introduction

This feature consolidates **cross-aggregate reference resolution** in the portable
`network_models` package into a single, opt-in **resolver module**. Today the
question "does this reference resolve against another aggregate?" is answered by
three separate, opt-in methods smeared across two models:
`System.validate_stig_assignments(catalog)` (raises),
`System.stig_divergences(definitions)` (warn-only), and
`DeviceDefinition.validate_against_catalog(catalog)` (raises). Two further
referential edges resolve against **nothing**: `Component.device_definition` (a
slug) is never checked against a `DeviceDefinitionLibrary`, and `Endpoint.interface`
is never checked against the component's device definition's actual interface names.

The design deepens a single module `network_models/system/resolve.py` exposing one
entry point — `resolve(system, *, definitions=None, catalog=None) -> IntegrityReport`
— that runs every cross-aggregate check that its supplied aggregates can support,
and returns a serializable, non-raising `IntegrityReport`. The three existing
scattered methods are **kept for back-compat** (tests depend on them) but
**reimplemented to delegate** to the resolver's focused checks, so there is exactly
one implementation of each check (locality).

The distinction that keeps each layer honest:

1. **Intra-aggregate invariants** — component→enclave, connection→component,
   switchport→VLAN — are enforced *inside* `System` model_validators. They stay
   exactly as they are; this spec does not touch them.
2. **Cross-aggregate edges** — System ↔ DeviceDefinitionLibrary ↔ StigCatalog —
   cannot be `model_validator`s because a partial `System`/`DeviceDefinition` draft
   must construct standalone without the sibling aggregates present. These are what
   the resolver owns, opt-in.

Everything in this feature lives inside the portable package (Pydantic v2 +
standard library only): the resolver imports the models, and the models never
import the resolver, mirroring the existing `TYPE_CHECKING`-only imports in
`topology.py` and `definition.py`. No app-layer compliance, no XML, no new deps.
This requirements document is derived from the approved design at
`.kiro/specs/cross-aggregate-resolver/design.md`, which remains the source of truth.

## Glossary

- **Aggregate**: A top-level model root that owns its own invariants — `System`,
  `DeviceDefinitionLibrary`, `StigCatalog`. Cross-aggregate edges point from one
  root into another.
- **Cross-aggregate edge**: A referential field whose target lives in a *different*
  aggregate: `Component.device_definition` → `DeviceDefinition.slug`;
  `Endpoint.interface` / `Endpoint.members` → the component definition's interface
  names; `Component.stig_assignments[*]` → `StigCatalog` `(benchmark_id, version)`;
  `DeviceDefinition.applicable_stigs[*]` → `StigCatalog` `benchmark_id`.
- **Intra-aggregate invariant**: A referential rule whose target lives in the *same*
  aggregate (component→enclave, connection→component, switchport→VLAN). Enforced by
  `System` model_validators; out of scope here.
- **Resolver**: `network_models/system/resolve.py` — the module exposing `resolve(...)`
  and `IntegrityReport`. The single home for cross-aggregate resolution.
- **IntegrityReport**: The serializable `StrictModel` returned by `resolve(...)`,
  collecting every finding as structured lists plus `.ok`, `.errors()`, and
  `.raise_for_errors()`.
- **Finding**: One structured record of an unresolved edge or a divergence. Each
  finding class is a distinct list field on `IntegrityReport`.
- **Divergence**: A *warn-only* finding: a component pins a STIG its device type
  does not declare in `applicable_stigs`. Legitimate (staggered patching), so it
  never affects `.ok` and never raises.
- **Opt-in**: The resolver is called explicitly, never as a `model_validator`, so
  partial drafts construct without the sibling aggregates.
- **Seam invariant**: The import-direction rule — `resolve.py` imports the models;
  the models import the resolver only inside method bodies (or under `TYPE_CHECKING`),
  never at module load, keeping the model core acyclic.
- **StrictModel**: The strict Pydantic base (`extra="forbid"`,
  `str_strip_whitespace=True`, `validate_assignment=True`) every model inherits.
- **DeviceDefinitionLibrary**: The `network_models.device.definition` container whose
  `definitions` a component's `device_definition` slug resolves against.
- **StigCatalog**: The `network_models.stig.catalog` reference library that STIG pins
  and applicable STIGs resolve against, keyed `(benchmark_id, version)`.

## Requirements

### Requirement 1: Single resolver entry point

**User Story:** As a model consumer, I want one function that answers every
cross-aggregate "does this reference resolve?" question, so that resolution logic
stops being smeared across multiple opt-in methods on two models.

#### Acceptance Criteria

1. THE Resolver SHALL define `resolve(system, *, definitions=None, catalog=None)`
   and `IntegrityReport` in `network_models/system/resolve.py`.
2. WHEN `resolve` is called, THE Resolver SHALL return an `IntegrityReport` and
   SHALL NOT raise for any structurally valid `System`, `DeviceDefinitionLibrary`,
   or `StigCatalog` input.
3. THE Resolver SHALL accept `definitions` and `catalog` as keyword-only optional
   arguments defaulting to `None`.
4. WHEN a needed aggregate is not supplied, THE Resolver SHALL skip the class(es)
   of finding that depend on it and SHALL leave those finding lists empty.
5. WHEN neither `definitions` nor `catalog` is supplied, THE Resolver SHALL return
   an `IntegrityReport` with every finding list empty and `.ok` equal to `True`.

### Requirement 2: Resolve the device-definition slug edge

**User Story:** As a system author, I want each component's `device_definition`
slug checked against the device library, so that a typo'd or stale slug is caught
instead of silently resolving against nothing.

#### Acceptance Criteria

1. WHEN `resolve` is called with a `definitions` library, THE Resolver SHALL record
   a `(component_id, slug)` finding for every component whose non-null
   `device_definition` slug is absent from the library's definition slugs.
2. WHEN a component's `device_definition` is `None`, THE Resolver SHALL NOT record
   an unresolved-device-definition finding for that component.
3. WHEN `resolve` is called without a `definitions` library, THE Resolver SHALL NOT
   record any unresolved-device-definition finding.
4. WHEN every component's `device_definition` resolves to a library slug, THE
   Resolver SHALL leave the unresolved-device-definition finding list empty.

### Requirement 3: Resolve the endpoint-interface edge

**User Story:** As a system author, I want each connection endpoint's interface (and
each LAG member) checked against the actual interface names of the component's
device definition, so that a connection to a non-existent port is caught.

#### Acceptance Criteria

1. WHEN `resolve` is called with a `definitions` library, THE Resolver SHALL record
   a `(component_id, interface)` finding for every endpoint `interface` that is not
   among the interface names declared by the endpoint component's resolved device
   definition.
2. WHEN an endpoint is a LAG (its `members` list is populated), THE Resolver SHALL
   check each member interface name and record a `(component_id, member)` finding
   for every member absent from the resolved device definition's interface names.
3. WHEN an endpoint's component has no `device_definition`, or its
   `device_definition` slug does not resolve to a library definition, THE Resolver
   SHALL NOT record an unresolved-endpoint-interface finding for that endpoint
   (the missing definition is already reported per Requirement 2).
4. WHEN an endpoint's `interface` is `None` and its `members` list is empty, THE
   Resolver SHALL NOT record an unresolved-endpoint-interface finding for that
   endpoint.
5. WHEN `resolve` is called without a `definitions` library, THE Resolver SHALL NOT
   record any unresolved-endpoint-interface finding.

### Requirement 4: Resolve the STIG-pin and applicable-STIG edges

**User Story:** As a compliance author, I want pinned component STIGs and device-type
applicable STIGs checked against the catalog in the same pass, so that every
catalog-facing edge is covered by the one resolver.

#### Acceptance Criteria

1. WHEN `resolve` is called with a `catalog`, THE Resolver SHALL record a
   `(component_id, benchmark_id, version)` finding for every component STIG
   assignment whose `(benchmark_id, version)` does not resolve in the catalog.
2. WHEN `resolve` is called with both a `definitions` library and a `catalog`, THE
   Resolver SHALL record a `(slug, benchmark_id)` finding for every definition
   `applicable_stigs` `benchmark_id` absent from the catalog's benchmark ids.
3. WHEN `resolve` is called with a `definitions` library, THE Resolver SHALL record
   the `(component_id, benchmark_id)` divergence pairs a component assigns that its
   resolved device definition does not declare in `applicable_stigs`.
4. WHEN `resolve` is called without a `catalog`, THE Resolver SHALL NOT record any
   unresolved-STIG-pin or unresolved-applicable-STIG finding.
5. THE Resolver SHALL classify divergences as warn-only so that they never affect
   `.ok` and are never raised by `.raise_for_errors()`.

### Requirement 5: IntegrityReport structure and interface

**User Story:** As a tooling author, I want the resolver's output to be a
serializable report with a boolean summary, human-readable errors, and an explicit
raise path, so that callers choose their own failure policy.

#### Acceptance Criteria

1. THE IntegrityReport SHALL be a `StrictModel` collecting the finding classes as
   structured list fields: unresolved device-definition slugs `(component_id, slug)`;
   unresolved endpoint interfaces `(component_id, interface)`; unresolved STIG pins
   `(component_id, benchmark_id, version)`; unresolved device applicable STIGs
   `(slug, benchmark_id)`; and STIG divergences `(component_id, benchmark_id)`.
2. THE IntegrityReport SHALL expose an `.ok` boolean that is `True` if and only if
   every error-class finding list is empty; the warn-only divergence list SHALL NOT
   affect `.ok`.
3. THE IntegrityReport SHALL expose `.errors()` returning a list of human-readable
   strings, one per error-class finding, and SHALL exclude warn-only divergences.
4. WHEN `.raise_for_errors()` is called and `.ok` is `False`, THE IntegrityReport
   SHALL raise a single aggregated `ValueError` whose message lists every
   error-class finding.
5. WHEN `.raise_for_errors()` is called and `.ok` is `True`, THE IntegrityReport
   SHALL return without raising.
6. WHEN an IntegrityReport is serialized with `model_dump(mode="json")` and
   re-validated with `model_validate`, THE IntegrityReport SHALL produce an object
   equal to the original.

### Requirement 6: Legacy methods delegate to the resolver

**User Story:** As a maintainer, I want the three existing scattered checks kept for
back-compat but reimplemented on top of the resolver, so that there is one
implementation of each check and existing tests keep passing unchanged.

#### Acceptance Criteria

1. THE `System.validate_stig_assignments(catalog)` method SHALL be retained and
   SHALL delegate to the resolver's STIG-pin check.
2. IF a component assignment does not resolve in the supplied catalog, THEN
   `System.validate_stig_assignments` SHALL raise a `ValueError` whose message
   identifies the unresolved `benchmark_id` and `version`, and SHALL otherwise
   return the system.
3. THE `System.stig_divergences(definitions)` method SHALL be retained, SHALL
   delegate to the resolver's divergence check, SHALL return the list of
   `(component_id, benchmark_id)` pairs, and SHALL never raise.
4. THE `DeviceDefinition.validate_against_catalog(catalog)` method SHALL be retained
   and SHALL delegate to the resolver's applicable-STIG check.
5. IF a definition's `applicable_stigs` `benchmark_id` is absent from the supplied
   catalog, THEN `DeviceDefinition.validate_against_catalog` SHALL raise a
   `ValueError` identifying the unresolved ids, and SHALL otherwise return the
   definition.
6. THE delegating methods SHALL preserve the exact observable behavior asserted by
   the existing tests in `tests/test_system_stig.py` and `tests/test_models.py`.

### Requirement 7: Opt-in and standalone construction preserved

**User Story:** As a model author, I want partial `System` and `DeviceDefinition`
drafts to keep constructing without the sibling aggregates, so that authoring and
import workflows are never blocked by missing cross-aggregate data.

#### Acceptance Criteria

1. THE Resolver SHALL NOT be invoked from any `model_validator`.
2. WHEN a `System` is constructed without a `definitions` library or a `catalog`,
   THE System SHALL validate without requiring any cross-aggregate edge to resolve.
3. WHEN a `DeviceDefinition` is constructed without a `catalog`, THE DeviceDefinition
   SHALL validate without requiring any `applicable_stigs` `benchmark_id` to resolve.
4. THE intra-aggregate invariants already enforced by `System` model_validators
   (component→enclave, connection→component, switchport→VLAN) SHALL remain unchanged.

### Requirement 8: Acyclic import seam and portability

**User Story:** As a package maintainer, I want the resolver to depend on the models
one-directionally, so that the model core stays acyclic and the package stays
portable and extractable.

#### Acceptance Criteria

1. THE Resolver SHALL import the model modules it needs.
2. THE model modules SHALL NOT import the Resolver at module load; any resolver
   import in a model SHALL occur inside a method body or under `TYPE_CHECKING` only.
3. THE Resolver SHALL import only Pydantic and the Python standard library, and
   SHALL NOT introduce XML, app-layer, or third-party dependencies.
4. THE Resolver SHALL inherit `IntegrityReport` from StrictModel and SHALL declare
   `__all__` so `resolve` and `IntegrityReport` are re-exported from the top-level
   `network_models` package.

### Requirement 9: Test coverage

**User Story:** As a maintainer, I want tests covering each finding class, the skip
behavior, the report interface, and the preserved legacy behavior, so that the
consolidation is verified and the back-compat guarantee is enforced.

#### Acceptance Criteria

1. THE test suite SHALL add `tests/test_resolve.py` covering each finding class:
   unresolved device-definition slug, unresolved endpoint interface (including a LAG
   member), unresolved STIG pin, unresolved device applicable STIG, and STIG
   divergence.
2. THE test suite SHALL verify the no-aggregate-supplied skip behavior: each finding
   class stays empty when its needed aggregate is absent, and an all-empty report is
   `.ok`.
3. THE test suite SHALL verify `.ok`, `.errors()`, and `.raise_for_errors()`,
   including that warn-only divergences do not flip `.ok` or trigger a raise.
4. THE test suite SHALL verify the IntegrityReport JSON round-trip.
5. THE test suite SHALL confirm the three legacy methods still behave as their
   current tests in `tests/test_system_stig.py` and `tests/test_models.py` expect.

### Requirement 10: Record the opt-in decision as an ADR

**User Story:** As a future reviewer, I want the "keep cross-aggregate resolution
opt-in rather than a model_validator" decision recorded, so that it is not
re-litigated without understanding the trade-off.

#### Acceptance Criteria

1. THE repository SHALL contain an ADR under `docs/adr/` recording the decision to
   keep cross-aggregate resolution opt-in (a resolver function) rather than a
   `model_validator`.
2. THE ADR SHALL state the rationale: partial drafts must construct standalone; the
   model core must stay acyclic; and models hold no foreign aggregates.
3. THE ADR SHALL follow the domain-modeling ADR format if present, else a simple
   `NNNN-title.md` with Status / Context / Decision / Consequences.

### Requirement 11: Re-exports and hygiene

**User Story:** As a package consumer, I want the new public names exported and the
package layout documented, so that `resolve` and `IntegrityReport` are importable
the same way as every other model.

#### Acceptance Criteria

1. THE `network_models/system/resolve.py` module SHALL declare `__all__` with
   `resolve` and `IntegrityReport`, flowing through the top-level re-export.
2. THE steering `structure.md` SHALL reflect the new `system/resolve.py` module and
   its cross-aggregate-resolver role.
3. THE full suite SHALL pass via `.venv/bin/python -m pytest -q`.

## Non-Goals / Out of Scope

The following are deliberately excluded from this feature. The boundary is
documented so it is explicit, but no functional requirement here demands them.

1. **Making any cross-aggregate check a `model_validator`.** Opt-in is deliberate:
   partial `System`/`DeviceDefinition` drafts must construct without the sibling
   aggregates. This is the load-bearing decision recorded in the ADR.
2. **Changing the intra-aggregate invariants.** The component→enclave,
   connection→component, and switchport→VLAN validators already live correctly
   inside `System` and are not touched.
3. **App-layer compliance evaluation.** Per-rule config-compliance (JMESPath into a
   rendered NaC document, the `ComplianceCheck` evaluator) stays out of the portable
   package, exactly as in the stig-catalog spec.
4. **XML / parsing / new dependencies.** The resolver is pure Pydantic + stdlib. No
   XCCDF parsing, no third-party libraries, no new runtime deps.
5. **Auto-invoking the resolver.** No model constructs or validates by calling the
   resolver implicitly; callers opt in.
</content>
</invoke>
