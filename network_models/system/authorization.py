"""The RMF authorization package attached to a deployed :class:`System`.

Inspired by OpenRMF's *System* (an authorization boundary): this bundles the
evaluated checklists, NIST 800-53 control assessments, POA&M items, and a lean
authorization spine (FIPS-199 categorization, authorizing official, ATO dates)
into one optional, self-contained, separately-serializable block. Topology stays
on :class:`~network_models.system.topology.System`; this is the paperwork.

System-wide scoring is exposed as ``@computed_field`` (derived from the
checklists, serialized for the viewer/exports). Control status can be *derived*
from checklist results via the ``cci_control_map`` (rule CCIs -> controls), with
explicit :class:`~network_models.system.assessment.ControlAssessment` entries
taking precedence. POA&M drafting from open findings is a non-mutating helper.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import Field, computed_field, model_validator

from network_models.base import ComputedFieldModel, StrictModel
from network_models.system.assessment import Checklist, ControlAssessment
from network_models.system.poam import PoamItem
from network_models.system.vocab import (
    CHECKLIST_STATUSES,
    IMPACT_LEVEL_RANK,
    ImpactLevel,
)


# ---------------------------------------------------------------------------
# Categorization (FIPS-199)
# ---------------------------------------------------------------------------
class Categorization(StrictModel):
    """FIPS-199 security categorization: the C/I/A impact triad."""

    confidentiality: ImpactLevel
    integrity: ImpactLevel
    availability: ImpactLevel

    @property
    def overall(self) -> ImpactLevel:
        """Overall categorization = the high-water mark across C/I/A."""
        return max(
            (self.confidentiality, self.integrity, self.availability),
            key=lambda lvl: IMPACT_LEVEL_RANK[str(lvl)],
        )


# ---------------------------------------------------------------------------
# AuthorizationPackage
# ---------------------------------------------------------------------------
class AuthorizationPackage(ComputedFieldModel):
    """A System's RMF authorization package: assessment results + authorization spine."""

    # --- authorization spine (all optional so drafts stay usable) ---
    categorization: Optional[Categorization] = None
    authorizing_official: Optional[str] = None
    ato_date: Optional[date] = None
    ato_expiration: Optional[date] = None

    # --- assessment data ---
    checklists: list[Checklist] = Field(default_factory=list)
    controls: list[ControlAssessment] = Field(default_factory=list)
    poam_items: list[PoamItem] = Field(default_factory=list)
    cci_control_map: dict[str, list[str]] = Field(
        default_factory=dict,
        description="CCI id -> 800-53 control id(s); rolls rule results up to controls",
    )

    # -- integrity --
    @model_validator(mode="after")
    def _unique_ids(self) -> "AuthorizationPackage":
        control_ids = [c.control_id for c in self.controls]
        if len(control_ids) != len(set(control_ids)):
            raise ValueError("control_id must be unique within the package")
        poam_ids = [p.id for p in self.poam_items]
        if len(poam_ids) != len(set(poam_ids)):
            raise ValueError("POA&M id must be unique within the package")
        return self

    # -- system-wide scoring (derived, serialized) --
    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_counts(self) -> dict[str, int]:
        """System-wide result counts by CKL status across all checklists."""
        counts = {s: 0 for s in CHECKLIST_STATUSES}
        for cl in self.checklists:
            for k, n in cl.status_counts.items():
                counts[k] += n
        return counts

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cat_open_counts(self) -> dict[str, int]:
        """System-wide OPEN findings by CAT label."""
        counts: dict[str, int] = {}
        for cl in self.checklists:
            for k, n in cl.cat_open_counts.items():
                counts[k] = counts.get(k, 0) + n
        return counts

    @computed_field  # type: ignore[prop-decorator]
    @property
    def compliance_score(self) -> float:
        """System-wide compliance %: NotAFinding / (total - Not_Applicable)."""
        c = self.status_counts
        assessable = sum(c.values()) - c["Not_Applicable"]
        if assessable <= 0:
            return 100.0
        return round(100.0 * c["NotAFinding"] / assessable, 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def coverage(self) -> float:
        """System-wide reviewed %: (total - Not_Reviewed) / total."""
        c = self.status_counts
        total = sum(c.values())
        if total <= 0:
            return 100.0
        return round(100.0 * (total - c["Not_Reviewed"]) / total, 1)

    def component_scores(self) -> dict[str, dict[str, int]]:
        """Per-component status counts (system-level checklists keyed '__system__')."""
        out: dict[str, dict[str, int]] = {}
        for cl in self.checklists:
            key = cl.component or "__system__"
            bucket = out.setdefault(key, {s: 0 for s in CHECKLIST_STATUSES})
            for k, n in cl.status_counts.items():
                bucket[k] += n
        return out

    # -- 800-53 rollup --
    def rolled_up_control_status(self) -> dict[str, str]:
        """Derive each control's status from checklist results via ``cci_control_map``.

        A control is ``non_compliant`` if any in-scope CCI has an Open result;
        ``compliant`` if every in-scope result was reviewed (>=1 assessed, none
        Not_Reviewed) and none Open; else ``not_assessed``. An explicit
        :class:`ControlAssessment` whose status is not the default
        ``not_assessed`` is authoritative and overrides the derived value.
        """
        # CCI -> set of observed statuses across all rule results.
        cci_statuses: dict[str, set[str]] = {}
        for cl in self.checklists:
            for r in cl.results:
                for cci in r.ccis:
                    cci_statuses.setdefault(cci, set()).add(str(r.status))

        # Invert the CCI->controls map to control -> in-scope CCIs.
        control_ccis: dict[str, set[str]] = {}
        for cci, control_ids in self.cci_control_map.items():
            for control_id in control_ids:
                control_ccis.setdefault(control_id, set()).add(cci)

        derived: dict[str, str] = {}
        for control_id, ccis in control_ccis.items():
            statuses: set[str] = set()
            for cci in ccis:
                statuses |= cci_statuses.get(cci, set())
            if "Open" in statuses:
                derived[control_id] = "non_compliant"
            elif "Not_Reviewed" in statuses:
                derived[control_id] = "not_assessed"
            elif statuses & {"NotAFinding", "Not_Applicable"}:
                derived[control_id] = "compliant"
            else:
                derived[control_id] = "not_assessed"

        # Explicit assessments override the derived value (and add controls not
        # covered by the map at all).
        for c in self.controls:
            if str(c.status) != "not_assessed" or c.control_id not in derived:
                derived[c.control_id] = str(c.status)
        return derived

    # -- POA&M drafting --
    def draft_poam_from_findings(self) -> list[PoamItem]:
        """Return POA&M *drafts* for Open findings not yet covered by a POA&M.

        Non-mutating: the caller curates and appends the returned items. Findings
        are deduped by ``(component, rule_id)`` against existing ``poam_items``
        (matched on ``component`` + ``source_rule_id``); severity is carried over
        and ``weakness`` is prefilled from the finding.
        """
        covered = {
            (p.component, p.source_rule_id)
            for p in self.poam_items
            if p.source_rule_id is not None
        }
        drafts: list[PoamItem] = []
        seen: set[tuple[Optional[str], str]] = set()
        for cl in self.checklists:
            for r in cl.results:
                if str(r.status) != "Open":
                    continue
                key = (cl.component, r.rule_id)
                if key in covered or key in seen:
                    continue
                seen.add(key)
                weakness = r.finding_details or r.stig_id or r.rule_id
                drafts.append(
                    PoamItem(
                        id=f"POAM-{cl.component or 'system'}-{r.rule_id}",
                        weakness=weakness,
                        source_rule_id=r.rule_id,
                        source_cci=r.ccis[0] if r.ccis else None,
                        severity=r.severity,
                        component=cl.component,
                        status="not_started",
                    )
                )
        return drafts


__all__ = ["Categorization", "AuthorizationPackage"]
