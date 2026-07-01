"""Evaluated STIG checklists and NIST 800-53 control assessments.

Where :mod:`network_models.stig` is the *reference* catalog (rules as published),
this module holds *evaluated results*: what a checklist run found. It mirrors the
OpenRMF authorization-package idea — a :class:`Checklist` is a CKL (one benchmark
evaluated against one target), and its per-rule :class:`RuleResult` lines carry a
CKL status (Open / NotAFinding / Not_Reviewed / Not_Applicable).

Results are **self-contained**: a :class:`RuleResult` embeds ``severity`` and
``ccis`` (exactly as a real ``.ckl`` / XCCDF ``<rule-result>`` does), so a
checklist can be scored and rolled up to 800-53 controls with no STIG catalog
loaded. (An optional consistency check against a catalog lives in
:mod:`network_models.io`.)

Scoring is exposed as ``@computed_field`` properties so it serializes into
``model_dump()`` for the System Viewer / exports, while staying single-source
derived from ``results`` (no stored, drift-prone score state).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, computed_field, field_validator, model_validator

from network_models.base import StrictModel
from network_models.stig.vocab import SEVERITY_TO_CAT, RuleSeverity
from network_models.system.vocab import CHECKLIST_STATUSES, ChecklistStatus, ControlStatus


# ---------------------------------------------------------------------------
# RuleResult (one evaluated rule — the result half of a CKL <VULN>)
# ---------------------------------------------------------------------------
class RuleResult(StrictModel):
    """One evaluated STIG rule: the *result* half of a CKL ``<VULN>`` line.

    Identity mirrors :class:`~network_models.stig.catalog.StigRule`
    (``group_id`` / ``rule_id`` / ``severity`` / ``ccis``) so a result correlates
    back to catalog content, but this model stores the *evaluation* (status,
    finding detail, comments). ``group_id`` (the Vuln ID) is optional: XCCDF
    ``TestResult`` documents don't always carry it, and a fake one would corrupt
    the very correlation it exists for. ``rule_id`` is the reliable key.
    """

    group_id: Optional[str] = Field(None, description="Vuln ID, e.g. 'V-220518' (may be absent)")
    rule_id: str = Field(..., min_length=1, description="Rule ID, e.g. 'SV-220518r991589_rule'")
    stig_id: Optional[str] = Field(None, description="STIG-ID, e.g. 'CISC-ND-000010'")
    severity: RuleSeverity
    status: ChecklistStatus
    ccis: list[str] = Field(
        default_factory=list, description="Associated CCI identifiers, e.g. 'CCI-000213'"
    )
    finding_details: Optional[str] = Field(None, description="CKL FINDING_DETAILS")
    comments: Optional[str] = Field(None, description="CKL COMMENTS")

    @property
    def cat(self) -> Optional[str]:
        """DISA CAT label (CAT I/II/III) derived from severity."""
        return SEVERITY_TO_CAT.get(str(self.severity))

    @field_validator("ccis")
    @classmethod
    def _unique_ccis(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("duplicate CCI in rule result")
        return v


# ---------------------------------------------------------------------------
# Checklist (one benchmark evaluated against a target — a CKL)
# ---------------------------------------------------------------------------
class Checklist(StrictModel):
    """An evaluated STIG checklist (a CKL): one benchmark run against a target.

    ``component`` binds the checklist to a :class:`~network_models.system.topology.Component`
    by id; leave it ``None`` to attach the checklist at the system level (e.g. a
    boundary/global benchmark). The owning ``System`` validates that a set
    ``component`` id resolves.
    """

    benchmark_id: str = Field(..., min_length=1, description="XCCDF Benchmark id")
    title: Optional[str] = None
    version: Optional[str] = Field(None, description="STIG version, e.g. 'V2R9'")
    release: Optional[str] = None
    component: Optional[str] = Field(None, description="Component id this checklist evaluates")
    source: Optional[str] = Field(None, description="Origin, e.g. 'SCAP', 'manual', a filename")
    evaluated_at: Optional[datetime] = None
    results: list[RuleResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_rule_ids(self) -> "Checklist":
        ids = [r.rule_id for r in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate rule_id within a checklist")
        return self

    # -- scoring (derived, but serialized via computed_field) --
    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_counts(self) -> dict[str, int]:
        """Count of results by CKL status (all four statuses always present)."""
        counts = {s: 0 for s in CHECKLIST_STATUSES}
        for r in self.results:
            counts[str(r.status)] += 1
        return counts

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cat_open_counts(self) -> dict[str, int]:
        """Count of OPEN findings by CAT label (CAT I/II/III) — the headline metric."""
        counts: dict[str, int] = {}
        for r in self.results:
            if str(r.status) == "Open":
                label = r.cat or "unknown"
                counts[label] = counts.get(label, 0) + 1
        return counts

    @computed_field  # type: ignore[prop-decorator]
    @property
    def compliance_score(self) -> float:
        """Percent compliant: NotAFinding / (total - Not_Applicable).

        Conservative RMF stance — Not_Reviewed stays in the denominator, so
        un-reviewed rules lower the score. 100.0 when nothing is assessable.
        """
        c = self.status_counts
        assessable = len(self.results) - c["Not_Applicable"]
        if assessable <= 0:
            return 100.0
        return round(100.0 * c["NotAFinding"] / assessable, 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def coverage(self) -> float:
        """Percent reviewed: (total - Not_Reviewed) / total.

        Distinguishes "failing" from "not yet looked at" (which the single score
        cannot). 100.0 for an empty checklist.
        """
        total = len(self.results)
        if total <= 0:
            return 100.0
        reviewed = total - self.status_counts["Not_Reviewed"]
        return round(100.0 * reviewed / total, 1)


# ---------------------------------------------------------------------------
# ControlAssessment (a NIST SP 800-53 control)
# ---------------------------------------------------------------------------
class ControlAssessment(StrictModel):
    """Assessment of a single NIST SP 800-53 control (or control enhancement).

    Rule results roll up to controls via CCIs: each CCI maps to one or more
    control ids (e.g. 'AC-2', 'AC-2(1)') through the ``cci_control_map`` supplied
    on the :class:`~network_models.system.authorization.AuthorizationPackage`.
    ``ccis`` lists the CCIs in scope for this control. An explicit ``status`` here
    is authoritative and overrides any derived rollup.
    """

    control_id: str = Field(..., min_length=1, description="e.g. 'AC-2' or 'AC-2(1)'")
    title: Optional[str] = None
    status: ControlStatus = ControlStatus("not_assessed")
    ccis: list[str] = Field(default_factory=list, description="CCIs in scope for this control")
    assessor: Optional[str] = None
    assessed_at: Optional[datetime] = None
    comments: Optional[str] = None

    @field_validator("ccis")
    @classmethod
    def _unique_ccis(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("duplicate CCI in control assessment")
        return v


__all__ = ["RuleResult", "Checklist", "ControlAssessment"]
