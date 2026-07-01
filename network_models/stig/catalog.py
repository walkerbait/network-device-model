"""STIG catalog models: the reference library of SRGs/STIGs and their rules.

Reference data derived from the DISA SRG-STIG Library (XCCDF 1.1 benchmark
content). Modeled down to individual rules because the end goal is proving a
generated config satisfies a STIG. Identity is versionless ``benchmark_id`` plus a
separate ``version``; catalog uniqueness is ``(benchmark_id, version)``.

Portability: pydantic + stdlib only. No expected-config / NaC coupling here — that
is the app-layer ComplianceCheck's job (see design Scope Boundary).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import Field, field_validator, model_validator

from network_models.base import StrictModel
from network_models.stig.vocab import SEVERITY_TO_CAT, RuleSeverity, StigType


class StigRule(StrictModel):
    """A single STIG rule = one XCCDF <Group>/<Rule> pair, metadata-faithful.

    Identifier conventions (DISA/XCCDF):
      * group_id — Vuln ID from Group/@id, e.g. 'V-204636'
      * rule_id  — Rule ID from Rule/@id,  e.g. 'SV-204636r1043176_rule'
      * stig_id  — STIG-ID from Rule/<version>, e.g. 'SRG-APP-000023-AAA-000030'
    """

    group_id: str = Field(..., min_length=1, description="Vuln ID, e.g. 'V-204636'")
    rule_id: str = Field(..., min_length=1, description="Rule ID, e.g. 'SV-204636r1043176_rule'")
    stig_id: Optional[str] = Field(None, description="Rule <version> / STIG-ID")
    severity: RuleSeverity                       # verbatim XCCDF @severity
    weight: Optional[float] = Field(None, ge=0, allow_inf_nan=False, description="Rule/@weight")
    title: str = Field(..., min_length=1)
    discussion: Optional[str] = Field(
        None, description="Best-effort text from <VulnDiscussion>; raw <description> fallback"
    )
    check_content: Optional[str] = Field(None, description="<check>/<check-content> text")
    check_content_ref: Optional[str] = Field(
        None, description="<check-content-ref @name or @href>"
    )
    check_system: Optional[str] = Field(None, description="<check @system>")
    fix_text: Optional[str] = Field(None, description="<fixtext> remediation text")
    fix_id: Optional[str] = Field(None, description="<fix @id> / <fixtext @fixref>")
    ccis: list[str] = Field(
        default_factory=list, description="ident system=.../cci, e.g. 'CCI-000015'"
    )
    legacy_ids: list[str] = Field(
        default_factory=list, description="ident system=.../legacy, e.g. 'V-80819'"
    )

    @property
    def cat(self) -> Optional[str]:
        """DISA CAT label (CAT I/II/III) derived from severity; None if unknown."""
        return SEVERITY_TO_CAT.get(str(self.severity))

    @field_validator("ccis", "legacy_ids")
    @classmethod
    def _unique_idents(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("duplicate identifier in rule")
        return v


class StigProfile(StrictModel):
    """An XCCDF <Profile> (e.g. a MAC level): a named selection of rules.

    Stores only rule-id references — NOT rule bodies — to avoid JSON bloat, since
    profiles overlap heavily. selected_rule_ids reference StigRule.rule_id within
    the SAME Stig.
    """

    id: str = Field(..., min_length=1, description="Profile/@id, e.g. 'MAC-1_Classified'")
    title: Optional[str] = None
    selected_rule_ids: list[str] = Field(default_factory=list)

    @field_validator("selected_rule_ids")
    @classmethod
    def _unique_selection(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("duplicate rule id in profile selection")
        return v


class Stig(StrictModel):
    """A single benchmark (SRG or STIG) at a specific version, with its rules."""

    benchmark_id: str = Field(
        ..., min_length=1, description="XCCDF Benchmark/@id VERBATIM, e.g. 'AAA_Services'"
    )
    title: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1, description="XCCDF <version> VERBATIM, e.g. '2'")
    release_info: Optional[str] = Field(
        None, description="plain-text release-info verbatim, e.g. 'Release: 2 Benchmark Date: 30 Jan 2025'"
    )
    status: Optional[str] = Field(None, description="<status> text, e.g. 'accepted'")
    status_date: Optional[date] = Field(None, description="<status @date>")
    type: StigType = Field(..., description="srg | stig; only stig is picker-selectable")
    source_file: str = Field(
        ..., min_length=1, description="Original source filename VERBATIM (traceability)"
    )
    profiles: list[StigProfile] = Field(default_factory=list)
    rules: list[StigRule] = Field(default_factory=list)

    @property
    def severity_counts(self) -> dict[str, int]:
        """Rule counts by CAT label (selector/summary display)."""
        counts: dict[str, int] = {}
        for r in self.rules:
            counts[r.cat or "unknown"] = counts.get(r.cat or "unknown", 0) + 1
        return counts

    @model_validator(mode="after")
    def _unique_rule_ids(self) -> "Stig":
        rule_ids = [r.rule_id for r in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("duplicate rule_id within a STIG")
        group_ids = [r.group_id for r in self.rules]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("duplicate group_id (Vuln ID) within a STIG")
        return self

    @model_validator(mode="after")
    def _profiles_resolve(self) -> "Stig":
        """Every profile selection must reference a rule that exists in this STIG."""
        known = {r.rule_id for r in self.rules}
        for p in self.profiles:
            missing = [rid for rid in p.selected_rule_ids if rid not in known]
            if missing:
                raise ValueError(
                    f"profile '{p.id}' selects unknown rule id(s): {missing[:5]}"
                )
        return self

    @model_validator(mode="after")
    def _unique_profile_ids(self) -> "Stig":
        ids = [p.id for p in self.profiles]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate profile id within a STIG")
        return self


class StigCatalog(StrictModel):
    """The reference library the web app selects from.

    Uniqueness is on (benchmark_id, version) — the same benchmark may appear at
    multiple versions, matching the pinning key used for Component assignments.
    """

    catalog_version: str = Field(
        ..., min_length=1, description="Catalog build id, e.g. 'April_2026'"
    )
    stigs: list[Stig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_benchmark_version(self) -> "StigCatalog":
        keys = [(s.benchmark_id, s.version) for s in self.stigs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate (benchmark_id, version) in catalog")
        return self

    # --- read-only lookups (no I/O, no mutation) ---
    def get(self, benchmark_id: str, version: Optional[str] = None) -> Optional[Stig]:
        """Look up a STIG by benchmark id, optionally pinned to a version.

        With no version, returns the first match (useful for the device-type
        *concept* reference, which is version-agnostic).
        """
        for s in self.stigs:
            if s.benchmark_id == benchmark_id and (version is None or s.version == version):
                return s
        return None

    def versions(self, benchmark_id: str) -> list[str]:
        """All versions present for a benchmark id, in catalog order."""
        return [s.version for s in self.stigs if s.benchmark_id == benchmark_id]

    def latest_version(self, benchmark_id: str) -> Optional[str]:
        """Most recent version for a benchmark, by status_date then insertion order.

        NOTE: version strings are heterogeneous ('2', 'V2R9', 'V5R3'); we do NOT
        parse them. We rank by status_date when available, else last-seen wins.
        The app-layer 'who must update' query builds on this.
        """
        candidates = [s for s in self.stigs if s.benchmark_id == benchmark_id]
        if not candidates:
            return None
        dated = [s for s in candidates if s.status_date is not None]
        if dated:
            return max(dated, key=lambda s: s.status_date).version  # type: ignore[arg-type, return-value]
        return candidates[-1].version

    def benchmark_ids(self, type: Optional[str] = None) -> list[str]:
        """Distinct benchmark ids, optionally filtered by type ('srg'|'stig')."""
        seen: dict[str, None] = {}
        for s in self.stigs:
            if type is None or str(s.type) == type:
                seen.setdefault(s.benchmark_id, None)
        return list(seen)


__all__ = ["StigRule", "StigProfile", "Stig", "StigCatalog"]
