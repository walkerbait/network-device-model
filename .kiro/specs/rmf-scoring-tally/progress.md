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

- Package `network_models/` is Pydantic v2 + stdlib only (portable). `StatusTally`
  should use *less* — a stdlib `dataclasses.dataclass`, no Pydantic — so it never
  enters the model schema.
- Scoring is exposed on models via `@computed_field @property`, so it serializes
  into `model_dump()`. `ComputedFieldModel` (`network_models/base.py`) drops a
  model's own computed-field keys on input so a dump round-trips through
  `model_validate`. Keep both facts intact — parity depends on them.
- The four CKL statuses are `CHECKLIST_STATUSES = ["Open", "NotAFinding",
  "Not_Reviewed", "Not_Applicable"]` in `network_models/system/vocab.py`; the seed
  `{s: 0 for s in CHECKLIST_STATUSES}` is currently restated 3× (Checklist,
  AuthorizationPackage.status_counts, AuthorizationPackage.component_scores).
- `RuleResult` already exposes `.status` (str-able `ChecklistStatus`) and `.cat`
  (`Optional[str]` via `SEVERITY_TO_CAT`), so it satisfies the tally's `Evaluated`
  structural type with no change.
- `str(enum_member)` returns the value string (enums built via `_str_enum`), which
  is why scoring compares `str(r.status) == "Open"`.
- Existing scoring tests live in `tests/test_system_assessment.py`
  (`test_checklist_scoring`, `test_system_wide_scoring_matches_single_checklist`,
  `test_scores_serialize_and_roundtrip`) — treat them as the pre-refactor golden
  baseline; do not edit them, keep them green.
- Run tests with `.venv/bin/python -m pytest -q`.

---

# Progress Log for spec: rmf-scoring-tally

<!-- Ralph appends one dated entry per completed task below this line. -->
</content>
