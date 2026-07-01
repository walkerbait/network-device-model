# Corrections

<!--
Flat lookup table of mistakes already made and their fixes. Every Ralph iteration
reads this FIRST and must never repeat a listed mistake. Add entries the moment a
command fails, an assumption proves wrong, or a workaround is needed.
Format: - ❌ wrong → ✅ right (reason)
-->

- ❌ Importing `resolve` at module load in `topology.py` / `definition.py` → ✅ Import `_check_*` functions lazily inside the delegating method bodies (seam invariant: models must never import the resolver at load or the model core becomes cyclic)
- ❌ Making a cross-aggregate check a `model_validator` → ✅ Keep it in `resolve()` / an opt-in method (partial `System`/`DeviceDefinition` drafts must construct without the sibling aggregates)
- ❌ Letting `stig_divergences` flip `.ok` or raise → ✅ Treat divergences as warn-only; only the four unresolved/error classes affect `.ok` and `.raise_for_errors()` (preserves current `System.stig_divergences` semantics)

# Codebase Patterns

<!--
Conventions discovered while implementing. Only record patterns actually
encountered. See ralph-loop-kiro-specs-prompt.md for the category checklist.
-->

- Package `network_models/` is Pydantic v2 + stdlib only (portable). The resolver is
  pure model logic (no I/O, no XML) so it belongs in the core, but must obey the
  one-directional import seam (`resolve.py → models`).
- Models already import sibling aggregates (`StigCatalog`,
  `DeviceDefinitionLibrary`) only under `TYPE_CHECKING` in `topology.py` and
  `definition.py`; follow the same pattern for any resolver reference.
- Interface names live on `DeviceDefinition.interfaces[].name`
  (`network_models/device/components.py::Interface`); an `Endpoint` uses either
  `interface` (single link) or `members` (LAG), never both.
- `StigCatalog.get(benchmark_id, version)` returns `None` when unresolved;
  `StigCatalog.benchmark_ids()` returns the distinct ids for applicable-STIG checks.
- Run tests with `.venv/bin/python -m pytest -q`.

---

# Progress Log for spec: cross-aggregate-resolver

<!-- Ralph appends one dated entry per completed task below this line. -->
</content>
