# Design: STIG Catalog Importer

## Overview

This design adds an **XCCDF → model importer** for the STIG domain. It reads DISA
XCCDF benchmark XML (the `*-xccdf.xml` "Manual" files DISA distributes) and
produces validated `network_models.stig` objects: a `Stig` per benchmark, a
`StigRule` per Group/Rule, assembled into a `StigCatalog`.

It intentionally mirrors the shape of the existing
`scripts/import_devicetype_library.py`: a `scripts/`-resident tool that may use
non-portable dependencies, a pure parsing/validation core, and a thin CLI with an
optional `--out` JSON dump. The `network_models/` package is **not** modified for
parsing — parsing is a `scripts/` concern so the package stays Pydantic + stdlib
and free of file/format coupling.

## Architecture

```
             U_*-xccdf.xml (DISA XCCDF Manual)
                     │
                     ▼
        ┌──────────────────────────┐
        │  xccdf.py  (parse core)  │   scripts/ — stdlib xml.etree only
        │  ─ parse_benchmark()     │
        │  ─ parse_rule()          │
        │  ─ extract helpers       │
        └──────────────────────────┘
                     │ builds
                     ▼
     network_models.stig  ── Stig / StigRule / StigCatalog (validation)
                     ▲
                     │ used by
        ┌──────────────────────────┐
        │ import_stig_library.py   │   scripts/ — CLI (arg parse, summary, --out)
        └──────────────────────────┘
```

Two files, one boundary:

- **`scripts/xccdf.py`** — the reusable, testable parse core. Pure functions that
  take XML (a path or an `ElementTree.Element`) and return validated models. No
  argument parsing, no printing, no `sys.exit`. This is what the tests import.
- **`scripts/import_stig_library.py`** — the CLI wrapper: argument parsing, the
  directory walk, human-readable summary, `--out` persistence, exit codes. Thin;
  delegates all parsing to `xccdf.py`.

This split matches the devicetype importer's separation of "validate one thing"
from "walk a tree and report", and keeps the parse logic unit-testable without
spawning a process.

## XCCDF structure (grounded in the bundled fixture)

Confirmed against `U_AAA_Services_SRG_V2R2_Manual-xccdf.xml`:

- Root `<Benchmark id="AAA_Services">` in default namespace
  `http://checklists.nist.gov/xccdf/1.1`.
- Direct children: `status` (`@date`), `title`, `description`, `version`,
  several `<plain-text>` (notably `id="release-info"` →
  `Release: 2 Benchmark Date: 30 Jan 2025`), `Profile` (ignored), and 77
  `<Group>` elements.
- Each `<Group id="V-2046nn">` has `title`, `description`, and one `<Rule>`.
- Each `<Rule id="SV-...r..._rule" severity="medium">` has: `version`
  (`SRG-APP-...`), `title`, `description` (contains an escaped `<VulnDiscussion>`
  block), one or more `<ident>` (`@system` = `.../cci` → `CCI-######`, or
  `.../legacy` → `V-`/`SV-` legacy ids), `fixtext`, `fix`, and `check`
  (with nested `<check-content>`).

### Field mapping table

| Model field            | XCCDF source                                             |
| ---------------------- | -------------------------------------------------------- |
| `Stig.benchmark_id`    | `Benchmark/@id`                                          |
| `Stig.title`           | `Benchmark/title`                                        |
| `Stig.version`         | derived from `Benchmark/version` + `release-info` text   |
| `Stig.release`         | release number parsed from `release-info` (optional)     |
| `Stig.date`            | `Benchmark/status/@date`                                 |
| `Stig.technology`      | optional caller/CLI-supplied label (not in XCCDF)        |
| `Stig.source_url`      | `Benchmark/reference/@href` when present                 |
| `StigRule.group_id`    | `Group/@id`                                              |
| `StigRule.rule_id`     | `Group/Rule/@id`                                         |
| `StigRule.stig_id`     | `Group/Rule/version`                                     |
| `StigRule.severity`    | `Group/Rule/@severity` (default `unknown`)               |
| `StigRule.title`       | `Group/Rule/title`                                       |
| `StigRule.discussion`  | `VulnDiscussion` recovered from `Rule/description`       |
| `StigRule.check_text`  | `Rule/check/check-content`                               |
| `StigRule.fix_text`    | `Rule/fixtext`                                           |
| `StigRule.ccis`        | text of each `Rule/ident[@system contains 'cci']`, deduped |

## Components and interfaces

### `scripts/xccdf.py`

```python
XCCDF_NS = "http://checklists.nist.gov/xccdf/1.1"

class XccdfParseError(Exception):
    """Raised when an XML file is not a usable XCCDF benchmark. Names the file."""

def parse_benchmark(path: str | os.PathLike) -> Stig:
    """Parse one XCCDF Manual file into a validated Stig (with all rules)."""

def parse_rule(group_el: Element) -> StigRule:
    """Build one StigRule from an <xccdf:Group> element (and its nested <Rule>)."""

def build_catalog(root: str | os.PathLike, version: str,
                  strict: bool = False) -> tuple[StigCatalog, list[FileError]]:
    """Walk a directory for *-xccdf.xml files, parse each, assemble a catalog.
    Returns (catalog, errors). In strict mode the first error raises."""
```

Internal helpers (module-private):

- `_q(tag)` → `"{XCCDF_NS}tag"` namespaced-tag builder (avoids repeating the URI).
- `_text(el, tag)` → child text or `None`, whitespace-stripped.
- `_derive_version(benchmark_el)` → folds `<version>` + `release-info` into a
  stable version string (e.g. `V2R2`), falling back to the raw `<version>` text.
- `_extract_discussion(description_text)` → pulls `<VulnDiscussion>...</Vuln
  Discussion>` out of the Rule description. The description content is escaped
  markup, so recover the discussion by re-parsing/regex on the unescaped text and
  taking only the discussion body.
- `_extract_ccis(rule_el)` → ordered, de-duplicated list of CCI ident texts,
  filtering `@system` to those containing `cci` (case-insensitive) and excluding
  `legacy`.

### `scripts/import_stig_library.py`

```
usage: import_stig_library.py [-h] [--out] [--catalog-version VERSION]
                              [--technology LABEL] [--strict] path

positional:
  path                  XCCDF file OR directory of *-xccdf.xml files

options:
  --out                 write validated JSON under converted/stig/ (gitignored)
  --catalog-version     catalog build id label (default: derived from date, e.g. "imported")
  --technology          human technology label applied to each Stig
  --strict              fail (non-zero exit) on the first file that can't be parsed
```

Behavior:
- If `path` is a file → parse one benchmark, wrap in a one-STIG `StigCatalog`.
- If `path` is a directory → `build_catalog(path, version, strict)`.
- Print a summary: files parsed / STIGs / total rules / rule counts by CAT
  (using `Stig.severity_counts`) / per-file errors.
- With `--out`: write each `Stig` as `converted/stig/<benchmark_id>_<version>.json`
  via `model_dump(mode="json")`, and the whole catalog as
  `converted/stig/catalog.json`.
- Exit non-zero only when `--strict` and at least one file failed.

## Data flow

```
parse_benchmark(path)
  ├─ ET.parse(path)                      # stdlib, XXE-safe default (no external entity fetch)
  ├─ validate root tag == {ns}Benchmark  # else XccdfParseError(file)
  ├─ read benchmark metadata
  ├─ for each {ns}Group:
  │     parse_rule(group)                # -> StigRule (Pydantic validates)
  └─ Stig(benchmark_id=..., rules=[...]) # Pydantic validates uniqueness of rule/group ids
```

Validation is delegated entirely to the Pydantic models — the importer builds
kwargs and lets `Stig`/`StigRule`/`StigCatalog` enforce constraints (mandatory
fields, `RuleSeverity` enum membership, unique rule_ids/group_ids, unique
`(benchmark_id, version)`). The importer's own job is faithful extraction plus
turning XML/parse problems into `XccdfParseError`.

## Error handling

| Condition                          | Response                                             |
| ---------------------------------- | ---------------------------------------------------- |
| File not found / not readable      | `XccdfParseError` naming the path                    |
| Not well-formed XML                | catch `ET.ParseError` → `XccdfParseError` naming file |
| Root not `<Benchmark>`             | `XccdfParseError` (skip in dir mode, unless strict)  |
| Missing mandatory rule field       | Pydantic `ValidationError` bubbles up, file-scoped   |
| Unknown `@severity` value          | Pydantic `ValidationError` (enum) — never silent     |
| Non-XCCDF file in directory        | skipped, not counted as error                        |

In directory mode, non-strict runs collect `(file, error)` pairs and continue;
the CLI reports them and still emits the catalog of what parsed. Strict mode
raises on the first failure.

## Security considerations

- XCCDF files are untrusted input. Use `xml.etree.ElementTree`, which does **not**
  resolve external entities by default, mitigating XXE. Do not switch to a parser
  configured to fetch DTDs/entities.
- `check_text`/`fix_text`/`discussion` may be large; they are stored verbatim but
  never executed or interpolated.

## Testing strategy

- **Unit** (`tests/test_stig_importer.py`): small inline XCCDF strings exercised
  through `parse_benchmark`/`parse_rule` covering each mapping rule, the
  `unknown` severity default, CCI dedup + legacy exclusion, and discussion
  recovery. Error paths assert `XccdfParseError` for malformed XML and a
  `ValidationError`/`XccdfParseError` for a missing mandatory field.
- **Integration**: parse the bundled `U_AAA_Services_SRG_V2R2_Manual-xccdf.xml`
  and assert `benchmark_id == "AAA_Services"`, 77 rules, all severities valid,
  and at least one rule with discussion/check/fix/CCIs populated.
- Run with `python -m pytest tests/ -q` (existing convention).

## Conventions to follow (from steering)

- `network_models/` stays portable: **no** parsing code added there; the importer
  lives entirely in `scripts/` (which is exempt and may use extra tooling).
- Reuse `Stig.severity_counts` for CAT-level reporting rather than recomputing.
- Match the CLI ergonomics of `scripts/import_devicetype_library.py` (`path`
  positional, `--out` writing under a gitignored dir).
- `from __future__ import annotations` at the top of new modules; type hints
  throughout; no Python 3.11-only features (support floor is 3.10).
