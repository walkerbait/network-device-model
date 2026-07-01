# Requirements Document

## Introduction

This feature **unifies the two XCCDF parsers** the repository currently ships and
deepens the opt-in ingestion layer. Today there are two, split across the
portability boundary:

1. The XCCDF **results** parser (`network_models/io/scap.py::parse_xccdf_results`)
   turns an XCCDF `TestResult` into a `Checklist`. It is **version-tolerant**
   (matches elements by *local* tag name via `io/_xml.local_name`, so XCCDF 1.1
   and 1.2 both parse) and **hardened** (parses via `io/_xml.parse_xml`, which
   prefers `defusedxml`). It lives inside the portable package's opt-in `io/`
   layer.
2. The XCCDF **benchmark** parser (`parse_benchmark`, ~165 LOC of parsing) lives
   in `scripts/import_stig_library.py`, **outside** the portable package. It uses
   a **hardcoded** namespace `{http://checklists.nist.gov/xccdf/1.1}` over raw
   `xml.etree.ElementTree.fromstring`, has **no hardening**, and has **zero unit
   tests**. Meanwhile the `stig/` docstrings advertise a "byte-for-byte importer"
   that the package itself does not ship.

The two parsers share a subject (XCCDF) and a hardened, version-tolerant XML
**seam** (`io/_xml`), yet only one of them leverages it. This feature promotes
benchmark parsing into a new **deep module** `network_models/io/xccdf.py` that
sits beside `scap.py` in the opt-in `io/` layer, shares the `io/_xml` seam
(hardened `parse_xml` + version-tolerant `local_name` matching, dropping the
hardcoded namespace), and mirrors `scap.py`'s interface shape. The script is
reduced to a **thin CLI adapter** with no parsing logic of its own. This makes
the advertised importer real, portable, hardened, and testable — collapsing two
divergent implementations of the same idea into one canonical, deep interface.

The change is confined to the ingestion (`io/`) layer and the harness script. The
`network_models/` core stays Pydantic + standard library and XML-free; the new
module is imported only from within `io/`, behind the existing `io` extra. No new
third-party dependencies are introduced beyond the already-optional `defusedxml`.

## Glossary

- **XCCDF**: The eXtensible Configuration Checklist Description Format used by DISA
  benchmark files. Benchmark documents appear in both the 1.1 namespace
  (`http://checklists.nist.gov/xccdf/1.1`) and the 1.2 namespace
  (`http://checklists.nist.gov/xccdf/1.2`).
- **Benchmark document**: An XCCDF `<Benchmark>` describing a STIG or SRG — its
  `<Group>`/`<Rule>` tree, `<Profile>`s, and header metadata. Parsed into a `Stig`.
- **Results document**: An XCCDF `<TestResult>` a SCAP tool emits after scanning —
  parsed into a `Checklist` by the existing `parse_xccdf_results`.
- **Ingestion_Layer**: The opt-in `network_models/io/` subpackage
  (`scap.py`, `cci.py`, `consistency.py`, and the new `xccdf.py`), deliberately
  not imported by the portable core, behind the `io` extra.
- **XML_Seam**: `network_models/io/_xml.py` — the shared hardened-XML helper
  exposing `parse_xml` (prefers `defusedxml`, XXE-safe stdlib fallback) and
  `local_name` (namespace-stripping local tag match).
- **Benchmark_Parser**: The new `network_models/io/xccdf.py` module that parses
  XCCDF benchmark documents into `Stig` and folds collections into `StigCatalog`.
- **Import_Harness**: The `scripts/import_stig_library.py` CLI, reduced to a thin
  adapter over `Benchmark_Parser`.
- **Catalog_Model**: The STIG catalog models (`Stig`, `StigProfile`, `StigRule`,
  `StigCatalog`) in `network_models/stig/`, unchanged by this feature.
- **DISA_Bundle**: The local `U_SRG-STIG_Library_April_2026` DISA SRG-STIG Library
  (XCCDF ZIPs plus loose XML), plus the loose repo fixture
  `U_AAA_Services_SRG_V2R2_Manual-xccdf.xml`.
- **local_name matching**: Resolving an element by its local tag name only,
  ignoring the `{namespace}` prefix, so a single parser handles multiple XCCDF
  namespace versions (the technique `scap.py` already uses).
- **StrictModel**: The strict Pydantic base every catalog model inherits
  (`extra="forbid"`, `str_strip_whitespace=True`, `validate_assignment=True`).

## Requirements

### Requirement 1: Benchmark parser in the opt-in ingestion layer

**User Story:** As a model consumer, I want a first-class XCCDF benchmark parser
inside `network_models/io/`, mirroring the results parser's shape, so that the
"byte-for-byte importer" the `stig/` docstrings advertise actually ships in the
portable package and is importable without the harness script.

#### Acceptance Criteria

1. THE Benchmark_Parser SHALL be defined in a new module
   `network_models/io/xccdf.py`.
2. THE Benchmark_Parser SHALL expose
   `parse_xccdf_benchmark(source, *, source_file=None) -> Stig`, accepting raw
   `bytes`, a `str` path, or an `os.PathLike`.
3. WHEN `parse_xccdf_benchmark` is called with `bytes` (or `bytearray`), THE
   Benchmark_Parser SHALL treat the argument as the raw benchmark document.
4. WHEN `parse_xccdf_benchmark` is called with a `str` or `os.PathLike`, THE
   Benchmark_Parser SHALL read that path and, WHERE no explicit `source_file` is
   given, default `source_file` to the path's base name.
5. THE Benchmark_Parser SHALL provide the byte- and file-level entry points
   `parse_xccdf_benchmark_bytes` and `parse_xccdf_benchmark_file`, mirroring the
   `parse_xccdf_results_bytes` / `parse_xccdf_results_file` / `parse_xccdf_results`
   dispatch shape in `scap.py`.
6. WHEN `parse_xccdf_benchmark` returns, THE Benchmark_Parser SHALL return a
   fully validated `Stig` instance whose `source_file` is populated.

### Requirement 2: Collection fold into a catalog

**User Story:** As a maintainer, I want a single call that folds a directory of
ZIPs, a single ZIP, a loose XCCDF file, or a directory of loose XML into a
`StigCatalog`, so that the collection logic living in the script moves into the
reusable ingestion layer.

#### Acceptance Criteria

1. THE Benchmark_Parser SHALL expose
   `parse_xccdf_catalog(source, *, catalog_version) -> StigCatalog`.
2. WHEN `source` is a directory, THE Benchmark_Parser SHALL collect every
   `*-xccdf.xml` member of each contained `*.zip` and every loose `*-xccdf.xml`
   file directly under the directory.
3. WHEN `source` is a single `*.zip` file, THE Benchmark_Parser SHALL collect
   every `*-xccdf.xml` member of that archive.
4. WHEN `source` is a loose `*-xccdf.xml` file, THE Benchmark_Parser SHALL collect
   that single document.
5. WHERE a benchmark document originates from a ZIP archive, THE Benchmark_Parser
   SHALL record the outer archive's file name as the `Stig.source_file`.
6. WHERE a benchmark document is a loose XML file, THE Benchmark_Parser SHALL
   record that file's base name as the `Stig.source_file`.
7. THE Benchmark_Parser SHALL read ZIP archives using only the standard-library
   `zipfile` module, which is permitted within the opt-in `io/` layer.
8. WHEN every collected document parses and the resulting `(benchmark_id, version)`
   keys are distinct, THE Benchmark_Parser SHALL return a validated `StigCatalog`
   carrying the supplied `catalog_version`.

### Requirement 3: Version-tolerant parsing via local_name

**User Story:** As a maintainer ingesting benchmarks across XCCDF releases, I want
the benchmark parser to match elements by local tag name rather than a hardcoded
namespace, so that XCCDF 1.1 and 1.2 documents both parse — parity with the
results parser.

#### Acceptance Criteria

1. THE Benchmark_Parser SHALL resolve every element by its `local_name`, using the
   `local_name` helper from `io/_xml`, and SHALL NOT hardcode the
   `http://checklists.nist.gov/xccdf/1.1` namespace.
2. WHEN a benchmark document is served in the XCCDF 1.1 namespace, THE
   Benchmark_Parser SHALL parse it into a `Stig`.
3. WHEN a benchmark document is served in the XCCDF 1.2 namespace, THE
   Benchmark_Parser SHALL parse it into a `Stig` producing the same field values
   as the 1.1 equivalent.
4. WHERE the same local tag name appears at different depths (e.g. a benchmark-level
   `<version>` versus a rule-level `<version>`), THE Benchmark_Parser SHALL resolve
   each from its correct parent scope so that benchmark `version` and rule
   `stig_id` are not conflated.

### Requirement 4: Field-mapping fidelity

**User Story:** As a catalog maintainer, I want the promoted parser to preserve the
current field mapping exactly, so that migrating from the script's `parse_benchmark`
to `io/xccdf.py` produces byte-for-byte identical `Stig` output on the same input.

#### Acceptance Criteria

1. THE Benchmark_Parser SHALL populate `benchmark_id` from `Benchmark/@id` and
   `version` from the benchmark-level `<version>` element, both verbatim.
2. THE Benchmark_Parser SHALL populate `release_info` from the `<plain-text>`
   element whose `@id` is `release-info`, and `status` / `status_date` from the
   `<status>` element text and its `@date` attribute (invalid dates left `None`).
3. WHEN populating a rule's `discussion`, THE Benchmark_Parser SHALL apply
   `html.unescape` to the raw `<description>` text and return the substring between
   `<VulnDiscussion>` and `</VulnDiscussion>` when present, falling back to the raw
   unescaped description otherwise.
4. THE Benchmark_Parser SHALL classify a `Stig` as `srg` when `srg` or
   `security requirements guide` appears (case-insensitively) in the combined
   `benchmark_id`, `title`, and `source_file`, and `stig` otherwise.
5. THE Benchmark_Parser SHALL populate each `StigRule` with `group_id`, `rule_id`,
   `stig_id` (rule-level `<version>`), `severity` (verbatim `@severity`, default
   `unknown`), `weight` (parsed float, `None` on failure), `title`,
   `check_content`, `check_content_ref` (`@name` then `@href`), `check_system`
   (`<check @system>`), `fix_text`, and `fix_id` (`<fix @id>` then
   `<fixtext @fixref>`).
6. THE Benchmark_Parser SHALL split `<ident>` values by `@system` suffix, assigning
   values whose system ends in `/cci` to `ccis` and values ending in `/legacy` to
   `legacy_ids`, de-duplicating each list while preserving first-seen order.
7. THE Benchmark_Parser SHALL build each `StigProfile` from the `<Profile>`
   `<select>` entries whose `@selected` is `true`, remapping each selected Group
   `@id` to its child `Rule` `@id` so `selected_rule_ids` resolve against rule ids.
8. WHEN the same `(benchmark_id, source_file, document)` triple is parsed by both
   the pre-existing `scripts.import_stig_library.parse_benchmark` and the new
   `parse_xccdf_benchmark`, THE Benchmark_Parser SHALL produce an equal `Stig`.

### Requirement 5: Hardened untrusted-content parsing

**User Story:** As a security-conscious maintainer, I want benchmark parsing to
route through the hardened XML seam like the results parser, so that untrusted
DISA content is parsed with XXE and entity-expansion protection when the `io`
extra is installed.

#### Acceptance Criteria

1. THE Benchmark_Parser SHALL parse XML bytes through `io/_xml.parse_xml` rather
   than calling `xml.etree.ElementTree.fromstring` directly.
2. WHERE the `io` extra (`defusedxml`) is installed, THE Benchmark_Parser SHALL
   parse benchmark content with the hardened backend.
3. WHERE the `io` extra is not installed, THE Benchmark_Parser SHALL parse with the
   XXE-safe standard-library fallback, matching the documented behavior of the
   existing ingestion modules.
4. IF a benchmark document is malformed and cannot be parsed, THEN THE
   Benchmark_Parser SHALL raise a parse error that a caller can catch to record the
   file in a failure summary and continue.

### Requirement 6: The harness becomes a thin CLI adapter

**User Story:** As a maintainer, I want `scripts/import_stig_library.py` to contain
no parsing logic of its own, only CLI orchestration over the ingestion layer, so
that there is a single source of truth for XCCDF benchmark parsing.

#### Acceptance Criteria

1. THE Import_Harness SHALL delegate all XCCDF parsing and collection to
   `network_models/io/xccdf.py` and SHALL NOT define its own benchmark-parsing or
   ZIP-collection functions.
2. THE Import_Harness SHALL preserve its current command-line surface: a positional
   library path, `--max-examples`, and `--out` (defaulting to a gitignored
   `stig_catalog/` directory when given without a value).
3. WHERE `--out` is supplied, THE Import_Harness SHALL write one JSON file per
   benchmark named `<benchmark_id>_<version>.json` plus a `catalog_manifest.json`
   index, as it does today.
4. WHEN parsing completes, THE Import_Harness SHALL print a pass/fail summary
   grouped by first validation-error cause.
5. IF any benchmark fails to load or fails validation, THEN THE Import_Harness SHALL
   exit with a non-zero status; otherwise it SHALL exit zero.
6. IF a benchmark file is malformed and cannot be parsed, THEN THE Import_Harness
   SHALL record the file in the failure summary and continue processing the
   remaining files.

### Requirement 7: Test coverage for the ingestion layer

**User Story:** As a maintainer, I want the new benchmark parser tested and the
existing ingestion siblings backfilled with coverage, so that the ingestion layer
is verified as a whole once benchmark parsing becomes a peer of results parsing.

#### Acceptance Criteria

1. THE test suite SHALL add `tests/test_io_xccdf.py` covering the new
   `Benchmark_Parser`.
2. THE test suite SHALL verify `parse_xccdf_benchmark` produces a `Stig` from the
   loose repo fixture `U_AAA_Services_SRG_V2R2_Manual-xccdf.xml` (bytes and file
   entry points).
3. THE test suite SHALL verify version-tolerance by parsing the same synthetic
   benchmark served in both the XCCDF 1.1 and 1.2 namespaces and asserting equal
   field values.
4. THE test suite SHALL verify `parse_xccdf_catalog` folds a collection (a ZIP
   and/or loose XML) into a validated `StigCatalog`.
5. THE test suite SHALL verify the malformed-XML error path raises a catchable
   parse error.
6. THE test suite SHALL backfill coverage for `parse_xccdf_results` and
   `parse_cci_list` in `tests/test_io_ingestion.py`, since these become siblings
   of the new module.

### Requirement 8: Portability and export hygiene

**User Story:** As a package maintainer, I want the portable core to stay XML-free
and the new module confined to the opt-in `io/` layer, so that the portability
boundary and the `io` extra contract are preserved.

#### Acceptance Criteria

1. THE `network_models/` core SHALL continue to import only Pydantic and the
   standard library and SHALL NOT import `network_models.io.xccdf`.
2. THE Benchmark_Parser SHALL live in the opt-in `io/` layer and depend on
   hardened parsing only through the `io` extra (`defusedxml`), introducing no new
   third-party dependency.
3. THE `network_models/io/__init__.py` SHALL re-export the new public names, and
   `io/xccdf.py` SHALL declare an `__all__` listing them.
4. THE Benchmark_Parser SHALL import `Stig` and `StigCatalog` from
   `network_models.stig.catalog` without modifying the catalog model shape.

### Requirement 9: Back-compatible harness behavior

**User Story:** As a maintainer, I want the harness runnable exactly as before
against the DISA bundle, so that the refactor is behavior-preserving.

#### Acceptance Criteria

1. WHEN the Import_Harness is run against `U_SRG-STIG_Library_April_2026`, THE
   Import_Harness SHALL validate every collected benchmark against `Stig` with the
   same pass/fail outcome as the pre-refactor script.
2. WHEN the Import_Harness is run against the loose fixture
   `U_AAA_Services_SRG_V2R2_Manual-xccdf.xml`, THE Import_Harness SHALL parse and
   validate it successfully.
3. THE Import_Harness SHALL keep its `--out` output layout — one
   `<benchmark_id>_<version>.json` per benchmark plus `catalog_manifest.json` —
   unchanged.

## Non-Goals / Out of Scope

The following are deliberately excluded from this feature. The boundary is stated
so it is explicit, but no requirement here demands their implementation.

1. **App-layer compliance evaluator** — Proving a generated NaC config satisfies a
   STIG's rules remains app-layer and out of scope; this feature only ingests
   benchmark content into the existing `Stig`/`StigCatalog` models.
2. **Changes to the catalog model shape** — `Stig`, `StigProfile`, `StigRule`, and
   `StigCatalog` are consumed as-is. No field is added, removed, or renamed.
3. **New third-party dependencies** — Only the already-optional `defusedxml` (the
   `io` extra) is used. No new XML libraries are introduced.
4. **Refactoring the results parser** — `parse_xccdf_results` and its helpers are
   unchanged; this feature adds a sibling and backfills tests, but does not
   restructure `scap.py`.
5. **Relocating `io/consistency.py`** — The sibling spec `concentrate-shared-rules`
   also touches the `io/` layer (it relocates `io/consistency.py`). That move is
   owned there, not here; the specs are independent.
</content>
</invoke>
