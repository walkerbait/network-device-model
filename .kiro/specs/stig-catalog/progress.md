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

- Package `network_models/` is Pydantic v2 + stdlib only (portable). Parsing/IO
  tooling belongs in `scripts/` (exempt from the portability boundary).
- Run tests with `python -m pytest tests/ -q`.

---

# Progress Log for spec: stig-catalog

<!-- Ralph appends one dated entry per completed task below this line. -->
