# Tasks: STIG Catalog Importer

Each top-level task is one Ralph iteration. Subtasks are implemented together
with their parent. Task IDs are referenced from `progress.md` and `specs_time.md`.

- [ ] 1. Scaffold the parse core and CLI skeleton
  - [ ] 1.1 Create `scripts/xccdf.py` with `XCCDF_NS`, the `XccdfParseError`
        exception, the namespaced-tag helper `_q`, and the `_text` helper.
        (`from __future__ import annotations`; stdlib `xml.etree.ElementTree`.)
  - [ ] 1.2 Add function stubs `parse_benchmark`, `parse_rule`, and
        `build_catalog` with signatures and docstrings from the design (raising
        `NotImplementedError` for now).
  - [ ] 1.3 Create `scripts/import_stig_library.py` with an `argparse` CLI
        matching the design (`path` positional; `--out`, `--catalog-version`,
        `--technology`, `--strict` options) and a `main()` that wires to
        `xccdf.py`. It may print "not implemented" until later tasks.
  - _Requirements: R1 (structure), R5 (CLI shape)._

- [ ] 2. Parse benchmark metadata into a `Stig`
  - [ ] 2.1 Implement `parse_benchmark` to open the file, guard that the root is
        `{ns}Benchmark` (else `XccdfParseError` naming the file), and map
        `benchmark_id`, `title`, `date`, and `source_url`.
  - [ ] 2.2 Implement `_derive_version` folding `<version>` + the
        `release-info` `<plain-text>` into a stable version string; set
        `Stig.version` and `Stig.release`.
  - [ ] 2.3 Return a `Stig` with an empty `rules` list for now (rules added in
        task 3). Handle `ET.ParseError` → `XccdfParseError`.
  - _Requirements: R1._

- [ ] 3. Map Group/Rule pairs into `StigRule`s
  - [ ] 3.1 Implement `parse_rule(group_el)` mapping `group_id`, `rule_id`,
        `stig_id` (`Rule/version`), `severity` (default `unknown`), and `title`.
  - [ ] 3.2 Wire `parse_benchmark` to iterate `{ns}Group` and populate
        `Stig.rules` via `parse_rule`.
  - [ ] 3.3 Let missing mandatory fields and bad severity surface as the model's
        `ValidationError`; ensure the error identifies the offending Group.
  - _Requirements: R2._

- [ ] 4. Extract discussion, check, fix, and CCI content
  - [ ] 4.1 Implement `_extract_discussion` to recover `<VulnDiscussion>` prose
        from the Rule `<description>` (unescape, then pull the discussion body).
  - [ ] 4.2 Map `check_text` ← `Rule/check/check-content` and `fix_text` ←
        `Rule/fixtext`.
  - [ ] 4.3 Implement `_extract_ccis` — ordered, de-duplicated CCI ident texts
        filtered to `@system` containing `cci`, excluding `legacy`.
  - _Requirements: R3._

- [ ] 5. Build a `StigCatalog` from a directory
  - [ ] 5.1 Implement `build_catalog(root, version, strict)` to walk for
        `*-xccdf.xml` files (recursively), parse each, and assemble a
        `StigCatalog`.
  - [ ] 5.2 Collect `(file, error)` pairs in non-strict mode and continue; raise
        on first failure in strict mode. Skip non-XCCDF files silently.
  - [ ] 5.3 Ensure the assembled catalog satisfies `(benchmark_id, version)`
        uniqueness.
  - _Requirements: R4._

- [ ] 6. Finish the CLI (summary + `--out`)
  - [ ] 6.1 Implement single-file vs directory dispatch in `main()`.
  - [ ] 6.2 Print a summary: files parsed, STIGs, total rules, rule counts by CAT
        (via `Stig.severity_counts`), and per-file errors.
  - [ ] 6.3 Implement `--out`: write each `Stig` and the whole `StigCatalog` as
        JSON under `converted/stig/` (gitignored); confirm `converted/` is in
        `.gitignore`.
  - [ ] 6.4 Exit non-zero only under `--strict` when a file failed.
  - _Requirements: R5._

- [ ] 7. Tests
  - [ ] 7.1 Add `tests/test_stig_importer.py` unit tests with inline XCCDF
        fixtures for metadata mapping, Group/Rule mapping, severity default, CCI
        dedup + legacy exclusion, and discussion recovery.
  - [ ] 7.2 Add error-path tests: malformed XML and missing mandatory field.
  - [ ] 7.3 Add an integration test parsing
        `U_AAA_Services_SRG_V2R2_Manual-xccdf.xml` asserting
        `benchmark_id == "AAA_Services"`, 77 rules, valid severities, and at
        least one fully-populated rule.
  - [ ] 7.4 Confirm `python -m pytest tests/ -q` passes.
  - _Requirements: R6._

- [ ] 8. Documentation
  - [ ] 8.1 Add an "Importing STIGs" section to `README.md` with example
        commands, parallel to the devicetype-library section.
  - [ ] 8.2 Add the STIG importer command to `.kiro/steering/tech.md` "Common
        commands".
  - _Requirements: R7._
