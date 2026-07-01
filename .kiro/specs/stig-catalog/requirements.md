# Requirements Document

## Introduction

This feature adds first-class **STIG (Security Technical Implementation Guide)**
support to the portable `network_models` package. It introduces a reference
**catalog** of STIGs and SRGs modeled to full rule granularity, revises the
device-type STIG reference to be version-agnostic (concept-only), and adds a
per-component pinned STIG **assignment** with assessment status to deployed
systems. A thin, stdlib-only validation-harness script parses the local DISA
XCCDF benchmark bundle and validates every benchmark against these models.

The design deliberately keeps STIG references at three granularities so each
layer stays honest about what it knows:

1. **Catalog** — the reference library (`Stig`, `StigProfile`, `StigRule`,
   `StigCatalog`) with identity `(benchmark_id, version)`, derived verbatim from
   DISA XCCDF content.
2. **Device concept-reference** — a device *type* declares which STIGs apply by
   concept (`benchmark_id` only, no version).
3. **System pinned-assignment** — a deployed *component* pins a concrete
   `(benchmark_id, version)` and records an assessment status.

Everything in this feature lives inside the portable package (Pydantic v2 +
standard library only) plus one validation-harness script under `scripts/`. The
config-compliance evaluator, the picker suggestion mapping, the production upload
importer, and the "which devices must update" query are **app-layer and out of
scope here** (see Non-Goals / Out of Scope). This requirements document is
derived from the approved design at `.kiro/specs/stig-catalog/design.md`, which
remains the source of truth.

## Glossary

- **STIG**: Security Technical Implementation Guide — a concrete, technology-specific
  security benchmark; the only catalog type that is picker-selectable and
  assignable.
- **SRG**: Security Requirements Guide — a technology-agnostic benchmark kept in
  the catalog for lineage only; not picker-selectable.
- **XCCDF**: The eXtensible Configuration Checklist Description Format (version 1.1,
  namespace `http://checklists.nist.gov/xccdf/1.1`) used by DISA benchmark files.
- **benchmark_id**: The versionless benchmark identifier taken verbatim from the
  XCCDF `Benchmark/@id` (e.g. `AAA_Services`).
- **version**: The benchmark version taken verbatim from the XCCDF `<version>`
  element (e.g. `2`, `V5R3`); never parsed or normalized.
- **CAT (Category)**: The DISA severity label (CAT I / CAT II / CAT III) derived
  from the XCCDF `@severity` (high / medium / low).
- **Catalog**: `StigCatalog` — the reference library the web app selects from,
  unique on `(benchmark_id, version)`.
- **Catalog_Model**: The set of catalog models — `StigRule`, `StigProfile`,
  `Stig`, `StigCatalog` — in `network_models/stig/`.
- **StigRule**: A single XCCDF `<Group>/<Rule>` pair modeled to full metadata
  granularity.
- **StigProfile**: An XCCDF `<Profile>` — a named selection of rule-id references
  within one STIG.
- **ApplicableStig**: The device-type concept reference (`benchmark_id` + optional
  `title` cache) on `DeviceDefinition`.
- **StigAssignment**: The per-component pinned reference (`benchmark_id` + `version`
  + `status`) on a system `Component`.
- **AssignmentStatus**: The closed vocabulary of assessment statuses for a
  `StigAssignment`.
- **Import_Harness**: The `scripts/import_stig_library.py` validation harness.
- **StrictModel**: The strict Pydantic base (`extra="forbid"`,
  `str_strip_whitespace=True`, `validate_assignment=True`) every model inherits.
- **DISA_Bundle**: The local `U_SRG-STIG_Library_April_2026` DISA SRG-STIG Library
  (XCCDF 1.1 ZIPs plus loose XML).

## Requirements

### Requirement 1: STIG catalog models in the portable package

**User Story:** As a model author, I want STIG catalog models defined in
`network_models/stig/` using only Pydantic and the standard library, so that the
catalog stays portable and can be vendored or extracted unchanged.

#### Acceptance Criteria

1. THE Catalog_Model SHALL define `Stig`, `StigProfile`, `StigRule`, and
   `StigCatalog` in `network_models/stig/`.
2. THE Catalog_Model SHALL define the vocabulary enums `RuleSeverity`, `StigType`,
   `AssignmentStatus`, and `TargetLayer` in `network_models/stig/vocab.py`.
3. THE Catalog_Model SHALL inherit from StrictModel so unknown keys are forbidden,
   whitespace is stripped, and assignment is validated.
4. THE Catalog_Model SHALL import only Pydantic and the Python standard library.
5. WHERE a constrained string field is defined, THE Catalog_Model SHALL build its
   enum with the `_str_enum` helper from a verbatim value list held as a
   module-level constant in `vocab.py`.
6. THE Catalog_Model SHALL declare `__all__` in each subpackage module so every
   public model and enum is re-exported from the top-level `network_models`
   package.

### Requirement 2: Distinguish SRGs from STIGs by type

**User Story:** As a picker user, I want SRGs and STIGs distinguished by an
explicit type, so that only STIGs are offered for selection while SRGs remain
available for lineage.

#### Acceptance Criteria

1. THE Catalog_Model SHALL represent each catalog entry with a `type` field whose
   value is `srg` or `stig`.
2. IF a `Stig` is constructed with a `type` value outside `{srg, stig}`, THEN THE
   Catalog_Model SHALL raise a `ValidationError`.
3. WHEN `StigCatalog.benchmark_ids` is called with `type="stig"`, THE Catalog_Model
   SHALL return only benchmark ids whose entries are of type `stig`.
4. WHEN `StigCatalog.benchmark_ids` is called with `type="srg"`, THE Catalog_Model
   SHALL return only benchmark ids whose entries are of type `srg`.
5. THE Catalog_Model SHALL retain SRG entries in the catalog for lineage.

### Requirement 3: Catalog identity and uniqueness

**User Story:** As a catalog maintainer, I want catalog identity keyed on
versionless `benchmark_id` plus a separate `version`, so that the same benchmark
can appear at multiple versions without collision and every entry traces back to
its source file.

#### Acceptance Criteria

1. THE Catalog_Model SHALL store `benchmark_id` verbatim from the XCCDF
   `Benchmark/@id`.
2. THE Catalog_Model SHALL store `version` verbatim from the XCCDF `<version>`
   element as a separate field.
3. THE Catalog_Model SHALL store the originating `source_file` name verbatim on
   each `Stig`.
4. IF two entries in a `StigCatalog` share the same `(benchmark_id, version)`,
   THEN THE Catalog_Model SHALL raise a `ValidationError`.
5. WHEN a `StigCatalog` is constructed with entries whose `(benchmark_id, version)`
   keys are all distinct, THE Catalog_Model SHALL construct successfully.
6. WHEN `StigCatalog.get` is called with a `benchmark_id` and a `version`, THE
   Catalog_Model SHALL return the matching `Stig` or `None` when no entry matches.

### Requirement 4: Full rule granularity for StigRule

**User Story:** As a compliance tooling author, I want each STIG rule captured at
full metadata granularity, so that downstream evaluation has faithful access to
identifiers, severity, checks, and fixes.

#### Acceptance Criteria

1. THE Catalog_Model SHALL capture on each `StigRule` the fields `group_id`,
   `rule_id`, `stig_id`, `severity`, `weight`, `title`, `discussion`,
   `check_content`, `check_content_ref`, `check_system`, `fix_text`, `fix_id`,
   `ccis`, and `legacy_ids`.
2. THE Catalog_Model SHALL store `severity` verbatim as one of `high`, `medium`,
   `low`, or `unknown`.
3. WHEN a `StigRule` has severity `high`, `medium`, or `low`, THE Catalog_Model
   SHALL expose a derived `cat` property equal to `CAT I`, `CAT II`, or `CAT III`
   respectively.
4. WHEN a `StigRule` has severity `unknown`, THE Catalog_Model SHALL expose a `cat`
   property equal to `None`.
5. WHEN a `StigRule` `discussion` is populated from XCCDF, THE Catalog_Model SHALL
   store the best-effort `<VulnDiscussion>` text and fall back to the raw
   `<description>` text when no `<VulnDiscussion>` is present.
6. IF a `StigRule` is constructed with duplicate entries in `ccis` or `legacy_ids`,
   THEN THE Catalog_Model SHALL raise a `ValidationError`.
7. IF a `StigRule` is constructed with a `severity` value outside the vocabulary,
   THEN THE Catalog_Model SHALL raise a `ValidationError`.

### Requirement 5: Rule and profile integrity within a STIG

**User Story:** As a catalog maintainer, I want a STIG to enforce internal
consistency of its rules and profiles, so that references never dangle and
identifiers never collide.

#### Acceptance Criteria

1. IF a `Stig` is constructed with duplicate `rule_id` values among its rules,
   THEN THE Catalog_Model SHALL raise a `ValidationError`.
2. IF a `Stig` is constructed with duplicate `group_id` values among its rules,
   THEN THE Catalog_Model SHALL raise a `ValidationError`.
3. IF a `Stig` is constructed with duplicate `id` values among its profiles, THEN
   THE Catalog_Model SHALL raise a `ValidationError`.
4. IF a `StigProfile` references a rule id in `selected_rule_ids` that does not
   exist among the STIG's rules, THEN THE Catalog_Model SHALL raise a
   `ValidationError`.
5. WHEN every `selected_rule_ids` entry in every profile references an existing
   rule id, THE Catalog_Model SHALL construct the `Stig` successfully.
6. THE `Stig.severity_counts` derived view SHALL report rule counts grouped by CAT
   label such that the sum of the counts equals the number of rules in the STIG.

### Requirement 6: Profiles store rule references only

**User Story:** As a catalog maintainer, I want profiles to store only rule-id
references rather than rule bodies, so that overlapping profiles do not duplicate
rule content and JSON stays compact.

#### Acceptance Criteria

1. THE Catalog_Model SHALL store profile selections as `selected_rule_ids`
   containing rule-id references only, with no embedded rule bodies.
2. IF a `StigProfile` is constructed with duplicate entries in `selected_rule_ids`,
   THEN THE Catalog_Model SHALL raise a `ValidationError`.
3. THE `selected_rule_ids` on a `StigProfile` SHALL reference `StigRule.rule_id`
   values within the same `Stig`.

### Requirement 7: JSON serialization round-trip fidelity

**User Story:** As a tooling author, I want catalog models to round-trip through
JSON without loss, so that the harness can persist per-benchmark JSON and reload
it faithfully.

#### Acceptance Criteria

1. WHEN a valid `Stig` is serialized with `model_dump(mode="json")` and then
   re-validated with `model_validate`, THE Catalog_Model SHALL produce an object
   equal to the original.
2. THE Catalog_Model SHALL preserve rule order, `ccis` order, `legacy_ids` order,
   and profiles across a JSON round-trip with no field loss.

### Requirement 8: Device-type concept reference (revised ApplicableStig)

**User Story:** As a device library maintainer, I want a device type to declare
applicable STIGs by concept using `benchmark_id` only, so that device definitions
do not churn on every STIG release.

#### Acceptance Criteria

1. THE `ApplicableStig` model SHALL contain a required `benchmark_id` and an
   optional `title` display cache.
2. THE `ApplicableStig` model SHALL NOT contain a `version` field.
3. IF a `DeviceDefinition` is constructed with duplicate `benchmark_id` values in
   `applicable_stigs`, THEN THE Catalog_Model SHALL raise a `ValidationError`.
4. WHEN a `DeviceDefinition` has `applicable_stigs` with distinct `benchmark_id`
   values, THE Catalog_Model SHALL construct successfully.

### Requirement 9: Optional catalog resolver for device definitions

**User Story:** As a device library maintainer, I want catalog resolution to be
opt-in, so that device definitions validate standalone but can be checked against
a catalog when one is supplied.

#### Acceptance Criteria

1. WHEN a `DeviceDefinition` is constructed without a catalog, THE Catalog_Model
   SHALL validate the definition without requiring any `benchmark_id` to resolve.
2. WHEN `DeviceDefinition.validate_against_catalog` is called with a catalog in
   which every `applicable_stigs` `benchmark_id` is present, THE Catalog_Model
   SHALL return the definition without error.
3. IF `DeviceDefinition.validate_against_catalog` is called with a catalog missing
   one or more `applicable_stigs` `benchmark_id` values, THEN THE Catalog_Model
   SHALL raise a `ValidationError` identifying the unresolved ids.

### Requirement 10: System pinned STIG assignment

**User Story:** As a system operator, I want each deployed component to pin STIG
versions and record assessment status, so that instances can track compliance
independently and deviate from their device type when needed.

#### Acceptance Criteria

1. THE `StigAssignment` model SHALL contain a required `benchmark_id`, a required
   pinned `version`, a `status`, an optional `assessed_date`, and optional `notes`.
2. WHEN a `StigAssignment` is constructed without an explicit `status`, THE
   Catalog_Model SHALL default `status` to `not_assessed`.
3. THE `Component` model SHALL expose a `stig_assignments` list of `StigAssignment`
   entries that is listed explicitly and not auto-derived from the device
   definition.
4. IF a `Component` is constructed with duplicate `(benchmark_id, version)` pairs
   in `stig_assignments`, THEN THE Catalog_Model SHALL raise a `ValidationError`.
5. WHEN a `Component` has two `stig_assignments` sharing a `benchmark_id` but with
   different `version` values, THE Catalog_Model SHALL construct successfully.
6. IF a `StigAssignment` is constructed with a `status` value outside
   `{not_assessed, compliant, open, not_applicable, inherited_pending}`, THEN THE
   Catalog_Model SHALL raise a `ValidationError`.

### Requirement 11: Optional assignment resolver and warn-only divergence

**User Story:** As a system operator, I want optional catalog resolution and a
warn-only divergence report for assignments, so that I can catch unresolved pins
and intentional deviations without blocking standalone validation.

#### Acceptance Criteria

1. WHEN a `System` is constructed without a catalog, THE Catalog_Model SHALL
   validate the system without requiring any assignment to resolve.
2. WHEN `System.validate_stig_assignments` is called with a catalog in which every
   component assignment resolves to a `(benchmark_id, version)`, THE Catalog_Model
   SHALL return the system without error.
3. IF `System.validate_stig_assignments` is called with a catalog missing a pinned
   `(benchmark_id, version)`, THEN THE Catalog_Model SHALL raise a
   `ValidationError` identifying the unresolved assignment.
4. WHEN `System.stig_divergences` is called with a device definition library, THE
   Catalog_Model SHALL return exactly the `(component_id, benchmark_id)` pairs a
   component assigns that its device definition does not declare.
5. THE `System.stig_divergences` query SHALL NOT raise for any input and SHALL
   return an empty list when every assignment is backed by the device type's
   `applicable_stigs`.

### Requirement 12: latest_version lookup is well-defined

**User Story:** As a catalog consumer, I want a well-defined latest-version lookup,
so that the app layer can build the "which devices must update" query on a stable
foundation without parsing heterogeneous version strings.

#### Acceptance Criteria

1. WHEN `StigCatalog.latest_version` is called for a `benchmark_id` present in the
   catalog, THE Catalog_Model SHALL return a version value that is a member of the
   versions present for that `benchmark_id`.
2. WHEN `StigCatalog.latest_version` is called for a `benchmark_id` absent from the
   catalog, THE Catalog_Model SHALL return `None`.
3. WHERE entries for a `benchmark_id` carry `status_date` values, THE Catalog_Model
   SHALL select the version with the most recent `status_date`.
4. WHERE no entry for a `benchmark_id` carries a `status_date`, THE Catalog_Model
   SHALL select the last-seen version in catalog order.
5. THE Catalog_Model SHALL NOT parse or normalize version strings when determining
   the latest version.

### Requirement 13: XCCDF validation-harness script

**User Story:** As a maintainer, I want a stdlib-only harness that parses the DISA
bundle and validates every benchmark against the models, so that I can confirm the
schema faithfully represents real DISA content.

#### Acceptance Criteria

1. THE Import_Harness SHALL be provided as `scripts/import_stig_library.py`.
2. THE Import_Harness SHALL parse XCCDF content using only the standard library
   `zipfile` and `xml.etree.ElementTree` modules.
3. WHEN the source path is a directory or a single `*.zip`, THE Import_Harness SHALL
   collect each `*-xccdf.xml` member and use the outer zip name as the source file.
4. WHEN the source path is a loose `*-xccdf.xml` file or a directory containing
   loose `*-xccdf.xml` files, THE Import_Harness SHALL accept and parse those files.
5. WHEN each benchmark is parsed, THE Import_Harness SHALL validate it against the
   `Stig` model.
6. WHEN parsing completes, THE Import_Harness SHALL print a pass/fail summary
   grouped by error cause.
7. IF any benchmark fails validation or fails to load, THEN THE Import_Harness SHALL
   exit with a non-zero status.
8. WHERE the `--out` option is supplied, THE Import_Harness SHALL write one JSON file
   per benchmark named `<benchmark_id>_<version>.json` plus a `catalog_manifest.json`
   index into a `stig_catalog/` directory.
9. IF a benchmark file is malformed and cannot be parsed, THEN THE Import_Harness
   SHALL record the file in the failure summary and continue processing remaining
   files.

### Requirement 14: Test coverage and migration of existing tests

**User Story:** As a maintainer, I want tests following the existing pytest
patterns and the two affected device STIG tests migrated, so that the new behavior
is verified and prior expectations are updated to the revised model.

#### Acceptance Criteria

1. THE test suite SHALL verify catalog uniqueness on `(benchmark_id, version)`.
2. THE test suite SHALL verify severity-to-CAT derivation for `high`, `medium`,
   `low`, and `unknown`.
3. THE test suite SHALL verify profile `selected_rule_ids` resolution, including
   the dangling-reference failure case.
4. THE test suite SHALL verify the optional device and system catalog resolvers
   validate standalone and raise only when a supplied catalog fails to resolve.
5. THE test suite SHALL verify `StigAssignment` uniqueness on
   `(benchmark_id, version)` and the closed set of statuses.
6. THE test suite SHALL verify that the same `benchmark_id` at two different
   versions is accepted at the component layer.
7. THE test suite SHALL migrate `test_duplicate_stig_benchmark_id_rejected` to
   assert duplicate `benchmark_id` alone is rejected in `applicable_stigs`.
8. THE test suite SHALL migrate `test_same_stig_different_versions_allowed` to the
   system/component suite as two `StigAssignment` entries sharing `benchmark_id`
   with differing `version`.

### Requirement 15: Repository hygiene for harness output

**User Story:** As a maintainer, I want the harness output directory ignored by
git, so that generated catalog JSON never gets committed.

#### Acceptance Criteria

1. THE repository `.gitignore` SHALL include an entry for `stig_catalog/`.

## Non-Goals / Out of Scope

The following are deliberately excluded from this repository. Their contracts are
documented in the design so the boundary is explicit, but no functional
requirements in this document demand their implementation here.

1. **ComplianceCheck model and evaluator** — Lives in the app layer because it
   knows the NaC schema and uses JMESPath to assert against a rendered NaC config
   as the primary `target_layer` (with the model as an alternative). Including it
   would break the portability boundary, since `network_models/` must import only
   Pydantic and the standard library. The `TargetLayer` vocabulary is defined in
   `stig/vocab.py` for shared use, but the check model itself is out of scope.
2. **Picker suggestion mapping** — The curated
   `(category, platform, role?) -> [benchmark_id]` mapping is app-layer curated
   data (hand-seeded JSON/YAML), not a schema, and is out of scope.
3. **Production upload/ingest importer** — The user-facing upload workflow is
   app-owned. Only the thin, stdlib-only validation harness
   (`scripts/import_stig_library.py`) is in scope here.
4. **"Which devices must update on version bump" query** — An app-layer query that
   compares `StigAssignment.version` against the catalog's latest version. It reads
   the in-scope models but is not schema state, so it is out of scope. This
   repository provides only the `StigCatalog.latest_version` foundation it builds on.
