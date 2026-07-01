# Requirements: STIG Catalog Importer

## Overview

The `network_models.stig` package already defines the target data models —
`StigRule`, `Stig`, and `StigCatalog` — but nothing populates them from real
DISA content. This spec covers building a **STIG catalog importer**: tooling that
parses DISA XCCDF benchmark XML (a `*-xccdf.xml` "Manual" file) into validated
`Stig`/`StigRule` objects and assembles a `StigCatalog` from one or more such
files.

The importer follows the existing precedent set by
`scripts/import_devicetype_library.py` (which validates the Nautobot
devicetype-library into `DeviceDefinition` objects): it lives in `scripts/`, may
use tooling beyond the package's portability boundary, and exposes a small CLI
with an optional `--out` mode that persists validated objects as JSON.

The repository ships a real sample file at the root —
`U_AAA_Services_SRG_V2R2_Manual-xccdf.xml` (the DISA "AAA Services SRG") — which
is the integration fixture the importer must parse cleanly.

## Terminology

- **XCCDF** — the XML schema DISA publishes STIG/SRG benchmark content in
  (namespace `http://checklists.nist.gov/xccdf/1.1`).
- **Benchmark** — the root `<Benchmark>` element; maps to one `Stig`.
- **Group** — an `<xccdf:Group>` whose `id` is the Vuln ID (e.g. `V-204636`);
  contains exactly one `<Rule>`. Maps (with its Rule) to one `StigRule`.
- **Rule** — the `<xccdf:Rule>` carrying `@severity`, `<version>` (the human
  STIG-ID / SRG-ID), `<title>`, `<description>`, `<check>`, `<fixtext>`, and
  `<ident>` elements.
- **CCI** — Control Correlation Identifier; an `<ident>` whose `@system` contains
  `cci` (value like `CCI-000015`).

---

## Requirement 1: Parse a single XCCDF benchmark into a `Stig`

**As** a catalog builder, **I want** to load one XCCDF Manual XML file into a
validated `Stig` object **so that** benchmark metadata and every rule are
available as strict models.

**Acceptance criteria:**

1. A function accepts a path to an XCCDF XML file and returns a `Stig`.
2. XCCDF namespaces are handled correctly (the default namespace
   `http://checklists.nist.gov/xccdf/1.1` must not require callers to know it).
3. Benchmark metadata maps as follows:
   - `Stig.benchmark_id` ← `<Benchmark id="...">`
   - `Stig.title` ← `<Benchmark>/<title>`
   - `Stig.version` ← a version+release string derived from `<version>` and the
     `release-info` `<plain-text>` (e.g. `V2R2`, or `Release: 2 Benchmark Date:
     30 Jan 2025` folded into a stable version string).
   - `Stig.date` ← the `<status date="...">` date when present.
4. Malformed or non-XCCDF XML raises a clear, typed error naming the file — it
   does not return a partially-populated `Stig`.

**Exit criteria:**
- Calling the loader on `U_AAA_Services_SRG_V2R2_Manual-xccdf.xml` returns a
  `Stig` whose `benchmark_id == "AAA_Services"` and whose `title` is the SRG
  title, with no `ValidationError`.

---

## Requirement 2: Map each Group/Rule pair to a `StigRule`

**As** a compliance engineer, **I want** every XCCDF Group/Rule turned into a
`StigRule` with identifiers and text intact **so that** the catalog is complete
down to individual rules.

**Acceptance criteria:**

1. Each `<Group>` (and its single nested `<Rule>`) becomes one `StigRule`.
2. Field mapping:
   - `StigRule.group_id` ← `<Group id="...">` (the Vuln ID, e.g. `V-204636`)
   - `StigRule.rule_id`  ← `<Rule id="...">` (e.g. `SV-204636r1043176_rule`)
   - `StigRule.stig_id`  ← `<Rule>/<version>` (e.g. `SRG-APP-000023-AAA-000030`)
   - `StigRule.severity` ← `<Rule severity="...">` (`high`/`medium`/`low`;
     default to `unknown` when the attribute is absent)
   - `StigRule.title`    ← `<Rule>/<title>`
3. `severity` values map verbatim onto `RuleSeverity`; an unexpected value is a
   validation error, not a silent pass.
4. Rules missing a mandatory field (`group_id`, `rule_id`, `title`, `severity`)
   surface a clear error identifying the offending Group.

**Exit criteria:**
- The AAA Services fixture yields one `StigRule` per `<Group>` (77 rules), each
  with a non-empty `group_id`, `rule_id`, and `title`, and a `severity` that is a
  valid `RuleSeverity`.

---

## Requirement 3: Extract discussion, check, fix, and CCI content

**As** a compliance engineer, **I want** the human-readable and traceability
content extracted **so that** the catalog can drive both display and
control-mapping.

**Acceptance criteria:**

1. `StigRule.discussion` ← the `<VulnDiscussion>` text carried inside the Rule's
   `<description>` element (XCCDF packs discussion as escaped/pseudo-XML inside
   `<description>`; the importer must recover just the discussion prose).
2. `StigRule.check_text` ← `<Rule>/<check>/<check-content>`.
3. `StigRule.fix_text` ← `<Rule>/<fixtext>`.
4. `StigRule.ccis` ← the text of every `<ident>` whose `@system` contains `cci`
   (e.g. `CCI-000015`), de-duplicated in document order. `<ident>` elements that
   are legacy IDs (`@system` referencing `legacy`) are excluded.
5. Missing optional content leaves the corresponding field `None`/empty rather
   than raising.

**Exit criteria:**
- For the AAA Services fixture, at least one imported `StigRule` has a non-empty
  `discussion`, `check_text`, `fix_text`, and a `ccis` list containing values of
  the form `CCI-######`, with no duplicate CCIs in any rule.

---

## Requirement 4: Build a `StigCatalog` from a directory of benchmarks

**As** a catalog builder, **I want** to point the importer at a directory and get
a single validated `StigCatalog` **so that** the web app can select across many
benchmarks/versions at once.

**Acceptance criteria:**

1. A function accepts a directory path and a catalog `version` label and returns
   a `StigCatalog` containing one `Stig` per `*-xccdf.xml` file found
   (recursively).
2. The resulting `StigCatalog` validates, including its
   `(benchmark_id, version)` uniqueness rule.
3. A per-file parse failure is reported with the file name and does not abort the
   whole build unless the caller opts into strict mode; the default collects and
   reports errors while importing the files that succeed.
4. Files that are not XCCDF benchmarks are skipped, not treated as errors.

**Exit criteria:**
- Running the directory build against the repository root produces a
  `StigCatalog` that includes the AAA Services benchmark and validates without
  error.

---

## Requirement 5: CLI entry point mirroring the devicetype importer

**As** a developer, **I want** a command-line interface consistent with
`scripts/import_devicetype_library.py` **so that** importing STIGs feels the same
as importing device types.

**Acceptance criteria:**

1. `python scripts/import_stig_library.py <path>` accepts either a single XCCDF
   file or a directory and prints a concise summary (files parsed, STIGs built,
   total rules, rule counts by CAT level, and any per-file errors).
2. A `--out` flag persists each validated `Stig` (and/or the whole
   `StigCatalog`) as JSON under a gitignored output directory (mirroring the
   devicetype importer's `converted/` behavior).
3. Exit code is non-zero when strict mode is requested and any file fails.
4. The script only imports extra tooling (stdlib `xml.etree.ElementTree` and, if
   needed, `PyYAML`) from `scripts/`; the `network_models/` package remains
   Pydantic + stdlib only.

**Exit criteria:**
- `python scripts/import_stig_library.py U_AAA_Services_SRG_V2R2_Manual-xccdf.xml`
  exits 0 and prints a summary reporting 1 STIG and 77 rules.

---

## Requirement 6: Tests

**As** a maintainer, **I want** unit and integration tests **so that** the
importer's field mapping and error handling stay correct as XCCDF quirks are
discovered.

**Acceptance criteria:**

1. Unit tests cover, with small inline XCCDF fixtures: benchmark-metadata
   mapping, Group/Rule mapping, severity mapping (including the `unknown`
   default), CCI extraction (including exclusion of legacy idents and
   de-duplication), and `VulnDiscussion` recovery.
2. Error-path tests assert that malformed XML and a missing mandatory field
   raise the importer's typed error.
3. An integration test parses the bundled `U_AAA_Services_SRG_V2R2_Manual-xccdf.xml`
   and asserts the STIG-level and rule-count exit criteria above.
4. Tests live in `tests/` and run under `python -m pytest tests/ -q` alongside
   the existing suite.

**Exit criteria:**
- `python -m pytest tests/ -q` passes, including the new STIG importer tests.

---

## Requirement 7: Documentation

**As** a user of the repo, **I want** the README/steering to mention the STIG
importer **so that** the workflow is discoverable next to the devicetype
importer.

**Acceptance criteria:**

1. `README.md` gains a short "Importing STIGs" note (command examples) parallel
   to the devicetype-library section.
2. `.kiro/steering/tech.md` "Common commands" lists the STIG importer command.

**Exit criteria:**
- The README and steering docs reference `scripts/import_stig_library.py` with a
  working example command.
