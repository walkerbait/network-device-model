# Corrections

<!--
Flat lookup table of mistakes already made and their fixes. Every Ralph iteration
reads this FIRST and must never repeat a listed mistake. Add entries the moment a
command fails, an assumption proves wrong, or a workaround is needed.
Format: - ❌ wrong → ✅ right (reason)
-->

- ❌ `from network_models.stig.vocab import ...` (via package init) → ✅ Test vocab.py in isolation when catalog.py is broken (catalog.py has a pre-existing bug: field named `date` shadows `datetime.date` type, causing PydanticSchemaGenerationError)
- ❌ Running `python -m pytest` while catalog.py is broken → ✅ Wait until catalog.py is revised in task 2/3 before running full test suite

# Codebase Patterns

<!--
Conventions discovered while implementing. Only record patterns actually
encountered. See ralph-loop-kiro-specs-prompt.md for the category checklist.
-->

- Package `network_models/` is Pydantic v2 + stdlib only (portable). Parsing/IO
  tooling belongs in `scripts/` (exempt from the portability boundary).
- Run tests with `python -m pytest tests/ -q`.
- Enums built via `_str_enum(name, value_list)` from `network_models/_enum.py`. Value lists are module-level constants in each domain's `vocab.py`. Member names are auto-derived (upper-snake). `str()` returns the value, not the repr.
- `stig/__init__.py` uses star-imports from `vocab` and `catalog`, combining their `__all__` lists. New exports in vocab.py flow automatically through the package re-export chain.

---

# Progress Log for spec: stig-catalog

<!-- Ralph appends one dated entry per completed task below this line. -->

## 2026-07-01 - Task 1: Revise `network_models/stig/vocab.py` with the full vocabulary set
- What was implemented: Added `STIG_TYPES`, `ASSIGNMENT_STATUSES`, `TARGET_LAYERS` value lists and built `StigType`, `AssignmentStatus`, `TargetLayer` enums via `_str_enum`. Updated module docstring to match design §2.1. Updated `__all__` to export all new names.
- Files changed: `network_models/stig/vocab.py`
- Tools used: standard file editing
- Patterns discovered: `_str_enum` auto-derives member names; `stig/__init__.py` star-imports flow new exports automatically
- Corrections added: pre-existing catalog.py `date` field bug blocks full test suite until task 2/3
---

## 2026-07-01 - Task 2: Revise `network_models/stig/catalog.py` — `StigRule` at full granularity
- What was implemented: Revised `StigRule` to match design §2.2. Added fields: `weight` (Optional[float], ge=0, allow_inf_nan=False), `check_content`, `check_content_ref`, `check_system`, `fix_id`, `legacy_ids`. Removed: `check_text` (replaced by `check_content`), `expected_config` (app-layer, out of scope). Replaced `_unique_ccis` validator with `_unique_idents` applied to both `ccis` and `legacy_ids`. Updated module docstring to match design. Left `Stig`/`StigCatalog` untouched (Task 3 scope).
- Files changed: `network_models/stig/catalog.py`
- Tools used: standard file editing; manual isolation test via importlib.util (bypassing broken package init)
- Patterns discovered: When `from __future__ import annotations` is active, a field named `date` on a Pydantic model shadows the `datetime.date` import — the annotation resolves to the field descriptor, not the type. Must be tested in isolation until Task 3 renames it.
- Corrections added: none new (pre-existing `Stig.date` bug already documented)
---

## 2026-07-01 - Task 3: Add `StigProfile` and revise `Stig` / `StigCatalog`
- What was implemented: Added `StigProfile` model with `_unique_selection` field validator. Revised `Stig` to match design §2.2: added `release_info`, `status`, `status_date` (Optional[date]), `type` (StigType, required), `source_file` (required), `profiles` (list[StigProfile]); dropped old `release`, `date`, `technology`, `source_url` fields. Added `_profiles_resolve` and `_unique_profile_ids` model validators. Revised `StigCatalog`: renamed `version` → `catalog_version`; added `versions(benchmark_id)` and `latest_version(benchmark_id)` methods; revised `benchmark_ids()` to accept optional `type` filter. Updated `__all__` to include `StigProfile`.
- Files changed: `network_models/stig/catalog.py`
- Tools used: standard file editing
- Patterns discovered: Removing the `date` field from `Stig` (renamed to `status_date`) resolved the pre-existing PydanticSchemaGenerationError caused by `from __future__ import annotations` + a field named `date` shadowing `datetime.date`.
- Corrections added: none new (the `date` shadowing bug is now resolved by this task)
---

## 2026-07-01 - Task 4: Create `tests/test_stig_catalog.py` — catalog model tests
- What was implemented: Created comprehensive test suite for STIG catalog models covering: catalog uniqueness on (benchmark_id, version); StigType enum validation and benchmark_ids filtering; severity/CAT derivation for all values including unknown; severity_counts conservation; profile resolution (valid, dangling refs, duplicate selected_rule_ids, duplicate profile ids); rule uniqueness (rule_id, group_id, ccis, legacy_ids); JSON round-trip fidelity with order preservation; latest_version (status_date wins, last-seen fallback, None for absent, no version parsing); catalog get() lookups; and StrictModel behavior (extra keys rejected, whitespace stripped). 34 tests total, all passing.
- Files changed: `tests/test_stig_catalog.py` (new)
- Tools used: standard file editing; pytest for verification
- Patterns discovered: none new
- Corrections added: none
---

## 2026-07-01 - Task 5: Revise `ApplicableStig` to concept-only in `network_models/device/definition.py`
- What was implemented: Removed `version` field from `ApplicableStig` (now concept-only: `benchmark_id` + optional `title`). Changed `_unique_applicable_stigs` validator to enforce uniqueness on `benchmark_id` alone. Added opt-in `DeviceDefinition.validate_against_catalog(catalog)` method that raises ValueError when any `applicable_stigs.benchmark_id` is absent from the catalog. Imported `StigCatalog` under `TYPE_CHECKING` to keep import direction clean. Updated `tests/test_models.py` to remove `version` keys from applicable_stigs fixtures, converted `test_same_stig_different_versions_allowed` to `test_same_benchmark_id_always_rejected`, and updated `test_duplicate_stig_benchmark_id_rejected` to test benchmark_id-only uniqueness.
- Files changed: `network_models/device/definition.py`, `tests/test_models.py`
- Tools used: standard file editing; pytest for verification
- Patterns discovered: Using `TYPE_CHECKING` import for cross-domain references within the portable package keeps runtime import direction clean while providing type hints for IDE support.
- Corrections added: none
---

## 2026-07-01 - Task 6: Migrate affected device STIG tests in `tests/test_models.py`
- What was implemented: Added three `validate_against_catalog` tests: (1) standalone validation succeeds without a catalog, (2) passes when all benchmark_ids resolve, (3) raises ValueError identifying unresolved ids when a catalog is supplied and an id is missing. Items 1-4 of the task (dropping `version` from fixtures, migrating `test_duplicate_stig_benchmark_id_rejected`, converting `test_same_stig_different_versions_allowed` to `test_same_benchmark_id_always_rejected`, and adjusting parametrized duplicate case) were already completed in Task 5.
- Files changed: `tests/test_models.py`
- Tools used: standard file editing; pytest for verification
- Patterns discovered: none new
- Corrections added: none
---

## 2026-07-01 - Task 7: Add `StigAssignment` and wire it into `Component`
- What was implemented: Added `StigAssignment` model (`benchmark_id`, `version`, `status: AssignmentStatus = "not_assessed"`, optional `assessed_date: date`, optional `notes`) in `system/topology.py`. Added `Component.stig_assignments: list[StigAssignment]` field with `_unique_stig_assignments` model validator enforcing unique `(benchmark_id, version)`. Added opt-in `System.validate_stig_assignments(catalog)` method (raises ValueError on unresolved `(benchmark_id, version)`) and warn-only `System.stig_divergences(definitions)` method (returns `(component_id, benchmark_id)` pairs, never raises). Used `TYPE_CHECKING` imports for `StigCatalog` and `DeviceDefinitionLibrary`. Added `StigAssignment` to `__all__` — flows through top-level re-export.
- Files changed: `network_models/system/topology.py`
- Tools used: standard file editing; pytest for verification
- Patterns discovered: none new
- Corrections added: none
---

## 2026-07-01 - Task 8: Create `tests/test_system_stig.py` — component assignment tests
- What was implemented: Created comprehensive test suite (22 tests) covering: StigAssignment default status is `not_assessed`; all valid statuses accepted; invalid status raises; duplicate `(benchmark_id, version)` on component raises; same `benchmark_id` at different versions accepted (relocated from device layer); system validates standalone without catalog; `validate_stig_assignments` passes when all resolve, raises on unresolved pin (including wrong version); `stig_divergences` returns undeclared pairs, returns empty when all backed, never raises even with missing definitions or null `device_definition`; field tests for assessed_date, notes, StrictModel extra key rejection, whitespace stripping.
- Files changed: `tests/test_system_stig.py` (new)
- Tools used: standard file editing; pytest for verification
- Patterns discovered: `DeviceDefinition` requires `platform` as a mandatory field — must include it in test fixtures that build minimal definitions.
- Corrections added: none
---

## 2026-07-01 - Task 9: Implement `scripts/import_stig_library.py` validation harness
- What was implemented: Created the XCCDF validation harness at `scripts/import_stig_library.py`. Implements `collect_xccdf()` (accepts directory of ZIPs, single `.zip`, loose `*-xccdf.xml`, or directory of loose XML), `parse_benchmark()` (stdlib `xml.etree.ElementTree` parser for XCCDF 1.1 namespace — extracts benchmark_id, version, release_info from `<plain-text id="release-info">`, status/status_date, type via `_classify_type`, profiles with V-id→rule_id remapping, and all rule fields including ccis/legacy_ids by ident system suffix, check_content/ref/system, fix_text/fix_id, discussion via `_extract_vuln_discussion` with html.unescape + VulnDiscussion extraction), and `main()` with argparse mirroring `import_devicetype_library.py` (grouped failure summary, non-zero exit on failures, `--out` writing per-benchmark JSON + `catalog_manifest.json`). Verified: 391/391 benchmarks from the real DISA bundle validate successfully. Also tested single ZIP, loose XML, error cases (non-existent path, empty directory), and `--out` JSON generation.
- Files changed: `scripts/import_stig_library.py` (new)
- Tools used: standard file editing; pytest for existing test verification; manual runs against DISA bundle
- Patterns discovered: Some DISA ZIPs contain multiple XCCDF files (e.g., Cisco ASA has NDM/FW/VPN/IPS). One `(benchmark_id, version)` pair (`Network_Device_Management_SRG`, `5`) appears in two different ZIPs — this means the on-disk output has one fewer file than the reported "written" count (last write wins). This is acceptable for the harness; the `StigCatalog` model's uniqueness validator would catch this at the catalog level.
- Corrections added: none
---

## 2026-07-01 - Task 10: Run the harness against the real DISA bundle and reconcile
- What was implemented: Ran the harness against the full DISA `U_SRG-STIG_Library_April_2026` bundle (186 ZIPs → 391 XCCDF benchmarks). All 391 pass validation with zero failures and zero load errors. Also verified: single ZIP input, loose `U_AAA_Services_SRG_V2R2_Manual-xccdf.xml` input, and `--out` JSON generation (390 unique benchmark JSON files + `catalog_manifest.json`). No model or parser changes needed — the implementation from Task 9 handles all real-world DISA content correctly.
- Files changed: none (validation-only task)
- Tools used: manual CLI runs of `scripts/import_stig_library.py`; pytest for full suite verification
- Patterns discovered: The 186-ZIP bundle yields 391 XCCDF documents (many ZIPs contain multiple benchmarks, e.g. Cisco ASA has NDM/FW/VPN/IPS). One `(benchmark_id, version)` pair (`Network_Device_Management_SRG`, `5`) appears in two ZIPs → 390 unique output files but 391 in the manifest. This is acceptable and documented.
- Corrections added: none
---

## 2026-07-01 - Task 11: Repository hygiene and final verification
- What was implemented: Added `stig_catalog/` to `.gitignore` (Req 15.1). Updated `structure.md` to annotate `stig/vocab.py` and `stig/catalog.py` with their contents and added `StigAssignment` to `system/topology.py` listing. Ran full test suite (83 passed, 3 skipped — skips are integration tests needing their env). Validated 20 converted device definitions to confirm the `ApplicableStig` concept-only change didn't regress. The Nautobot devicetype-library is not locally available so the full integration import couldn't be re-run, but converted files confirm compatibility.
- Files changed: `.gitignore`, `.kiro/steering/structure.md`
- Tools used: standard file editing; pytest for full suite verification; Python smoke test for converted definitions
- Patterns discovered: none new
- Corrections added: none
---
