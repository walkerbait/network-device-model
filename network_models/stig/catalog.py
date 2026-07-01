"""STIG catalog models: the reference library of STIGs and their rules.

This is *reference data* derived from the DISA SRG-STIG Library (XCCDF benchmark
content). It is the source a web app reads to populate a STIG/rule selector, and
— because the end goal is proving a generated config satisfies a STIG — it is
modeled down to individual **rules** (not just benchmark metadata).

Layering (see ``network_models.device`` / ``network_models.system``):

* A :class:`~network_models.device.definition.DeviceDefinition` references a STIG
  by *concept* (``benchmark_id`` only) — "this device type is subject to the
  IOS-XE Switch NDM STIG".
* A deployed ``Component`` pins a specific ``version`` and tracks compliance.
* This catalog holds the actual STIG + rule content those references resolve to.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import Field, field_validator, model_validator

from network_models.base import StrictModel
from network_models.stig.vocab import SEVERITY_TO_CAT, RuleSeverity


class StigRule(StrictModel):
    """A single STIG rule (one XCCDF ``<Group>``/``<Rule>`` pair).

    Identifiers follow DISA/XCCDF conventions:

    * ``group_id``   — the Vuln ID, e.g. ``V-220518``
    * ``rule_id``    — the Rule ID, e.g. ``SV-220518r991589_rule``
    * ``stig_id``    — the human STIG-ID / version, e.g. ``CISC-ND-000010``
    """

    group_id: str = Field(..., min_length=1, description="Vuln ID, e.g. 'V-220518'")
    rule_id: str = Field(..., min_length=1, description="Rule ID, e.g. 'SV-220518r991589_rule'")
    stig_id: Optional[str] = Field(None, description="STIG-ID, e.g. 'CISC-ND-000010'")
    severity: RuleSeverity
    title: str = Field(..., min_length=1)
    discussion: Optional[str] = None
    check_text: Optional[str] = Field(None, description="How to verify compliance (XCCDF check)")
    fix_text: Optional[str] = Field(None, description="How to remediate (XCCDF fixtext)")
    ccis: list[str] = Field(
        default_factory=list, description="Associated CCI identifiers, e.g. 'CCI-000213'"
    )

    # --- Compliance-tracing hook (populated later by the compliance engine) ---
    # Reserved for mapping a rule to the concrete device config it expects, so a
    # generated NaC config can be checked against it. Intentionally unstructured
    # for now; the compliance work will formalize this.
    expected_config: Optional[dict] = Field(
        default=None,
        description="RESERVED: expected-config expression for automated checking (not yet used)",
    )

    @property
    def cat(self) -> Optional[str]:
        """DISA CAT label (CAT I/II/III) derived from severity."""
        return SEVERITY_TO_CAT.get(str(self.severity))

    @field_validator("ccis")
    @classmethod
    def _unique_ccis(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("duplicate CCI in rule")
        return v


class Stig(StrictModel):
    """A single STIG benchmark at a specific version, with its rules."""

    benchmark_id: str = Field(
        ..., min_length=1, description="XCCDF Benchmark id, e.g. 'Cisco_IOS_XE_Switch_NDM_STIG'"
    )
    title: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1, description="e.g. 'V2R9' or a version+release string")
    release: Optional[str] = None
    date: Optional[date] = Field(None, description="Benchmark status/release date")
    technology: Optional[str] = Field(
        None, description="Human technology/platform label for filtering, e.g. 'Cisco IOS-XE'"
    )
    source_url: Optional[str] = None
    rules: list[StigRule] = Field(default_factory=list)

    @property
    def severity_counts(self) -> dict[str, int]:
        """Count of rules by CAT label (selector/summary display)."""
        counts: dict[str, int] = {}
        for r in self.rules:
            label = r.cat or "unknown"
            counts[label] = counts.get(label, 0) + 1
        return counts

    @model_validator(mode="after")
    def _unique_rule_ids(self) -> "Stig":
        ids = [r.rule_id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate rule_id within a STIG")
        groups = [r.group_id for r in self.rules]
        if len(groups) != len(set(groups)):
            raise ValueError("duplicate group_id (Vuln ID) within a STIG")
        return self


class StigCatalog(StrictModel):
    """A collection of STIGs (the reference library the web app selects from).

    Uniqueness is on ``(benchmark_id, version)`` — matching the pinning key used
    for ``Component`` STIG assignments — so the same benchmark may appear at
    multiple versions in one catalog.
    """

    version: str = Field(..., min_length=1, description="Catalog build id, e.g. 'April_2026'")
    stigs: list[Stig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_benchmark_version(self) -> "StigCatalog":
        keys = [(s.benchmark_id, s.version) for s in self.stigs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate (benchmark_id, version) in catalog")
        return self

    def get(self, benchmark_id: str, version: Optional[str] = None) -> Optional[Stig]:
        """Look up a STIG by benchmark id, optionally pinned to a version.

        With no ``version``, returns the first matching benchmark (useful for the
        device-type *concept* reference, which is version-agnostic).
        """
        for s in self.stigs:
            if s.benchmark_id == benchmark_id and (version is None or s.version == version):
                return s
        return None

    def benchmark_ids(self) -> list[str]:
        """Distinct benchmark ids present in the catalog (selector population)."""
        seen: dict[str, None] = {}
        for s in self.stigs:
            seen.setdefault(s.benchmark_id, None)
        return list(seen)


__all__ = ["StigRule", "Stig", "StigCatalog"]
