# Corrections

<!--
Flat lookup table of mistakes already made and their fixes. Every Ralph iteration
reads this FIRST and must never repeat a listed mistake. Add entries the moment a
command fails, an assumption proves wrong, or a workaround is needed.
Format: - ❌ wrong → ✅ right (reason)
-->

# Codebase Patterns

<!--
Conventions discovered while implementing. Only record patterns actually
encountered. See ralph-loop-kiro-specs-prompt.md for the category checklist.
-->

- The opt-in ingestion layer is `network_models/io/` (`_xml.py`, `scap.py`,
  `cci.py`, `consistency.py`). It is deliberately NOT imported by the portable
  core and is exempt from the no-XML rule; it may use stdlib `xml.etree` /
  `zipfile` / `html` and, behind the `io` extra, `defusedxml`.
- The hardened, version-tolerant XML seam is `network_models/io/_xml.py`:
  `parse_xml` (prefers `defusedxml`, XXE-safe stdlib fallback, `HARDENED` flag) and
  `local_name` (strips the `{namespace}` prefix). `scap.py` already leverages it;
  this feature makes the benchmark parser leverage it too.
- Ingestion parsers mirror a dispatch trio: `parse_x_bytes` (raw bytes),
  `parse_x_file` (path), and `parse_x` (dispatch on `bytes` vs `str`/`PathLike`).
  See `scap.parse_xccdf_results*`.
- `network_models/io/__init__.py` star-imports each submodule and splices their
  `__all__` lists; a new submodule must be added to that chain to be re-exported.
  The top-level `network_models/__init__.py` does NOT re-export `io` (ingestion
  stays opt-in).
- Catalog models (`Stig`, `StigProfile`, `StigRule`, `StigCatalog`) live in
  `network_models/stig/catalog.py` and are consumed as-is by this feature — no
  field changes. `Stig.source_file` is required.
- Run tests with `.venv/bin/python -m pytest -q`. Harness integration:
  `.venv/bin/python scripts/import_stig_library.py U_SRG-STIG_Library_April_2026`.

---

# Progress Log for spec: xccdf-parser-unify

<!-- Ralph appends one dated entry per completed task below this line. -->
</content>
