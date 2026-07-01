"""Tests for the RMF/OpenRMF authorization-package models.

Covers evaluated checklists + scoring, 800-53 control rollup, FIPS-199
categorization, POA&M drafting, JSON round-trip (including computed scores), and
the strict-schema rejections.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from network_models import (
    AuthorizationPackage,
    Categorization,
    Checklist,
    ControlAssessment,
    Milestone,
    PoamItem,
    RuleResult,
    System,
)


def _system(**auth_kwargs) -> System:
    """A minimal System with one enclave + component and an authorization package."""
    return System(
        id="SYS-1",
        name="Edge",
        enclaves=[{"name": "dmz", "classification": "CUI"}],
        components=[{"id": "edge-fw-01", "enclave": "dmz", "category": "firewall"}],
        authorization=AuthorizationPackage(**auth_kwargs),
    )


THREE_RESULTS = [
    {"rule_id": "SV-1_rule", "severity": "high", "status": "Open", "ccis": ["CCI-000213"]},
    {"rule_id": "SV-2_rule", "severity": "medium", "status": "NotAFinding"},
    {"rule_id": "SV-3_rule", "severity": "low", "status": "Not_Applicable"},
]


def _checklist(**over):
    base = {"benchmark_id": "B", "component": "edge-fw-01", "results": THREE_RESULTS}
    base.update(over)
    return Checklist(**base)


def test_checklist_scoring():
    cl = _checklist()
    assert cl.status_counts == {"Open": 1, "NotAFinding": 1, "Not_Reviewed": 0, "Not_Applicable": 1}
    assert cl.cat_open_counts == {"CAT I": 1}
    # NotAFinding(1) / (total 3 - N/A 1) = 50.0
    assert cl.compliance_score == 50.0
    # nothing Not_Reviewed -> fully covered
    assert cl.coverage == 100.0


def test_system_wide_scoring_matches_single_checklist():
    sysm = _system(checklists=[_checklist()])
    ap = sysm.authorization
    assert ap.status_counts == {"Open": 1, "NotAFinding": 1, "Not_Reviewed": 0, "Not_Applicable": 1}
    assert ap.cat_open_counts == {"CAT I": 1}
    assert ap.compliance_score == 50.0
    assert ap.coverage == 100.0
    assert ap.component_scores()["edge-fw-01"]["Open"] == 1


def test_scores_serialize_and_roundtrip():
    sysm = _system(checklists=[_checklist()])
    dumped = sysm.model_dump(mode="json")
    cl_json = dumped["authorization"]["checklists"][0]
    assert cl_json["compliance_score"] == 50.0
    assert cl_json["coverage"] == 100.0
    assert cl_json["cat_open_counts"] == {"CAT I": 1}
    # computed fields present in the dump must not break re-validation
    reloaded = System.model_validate(dumped)
    assert reloaded.authorization.compliance_score == 50.0


def test_control_rollup_and_explicit_override():
    ap = _system(
        checklists=[_checklist()],
        cci_control_map={"CCI-000213": ["AC-3"]},
    ).authorization
    # CCI-000213 has an Open result -> control is non_compliant
    assert ap.rolled_up_control_status()["AC-3"] == "non_compliant"

    # An explicit assessment overrides the derived value.
    ap2 = _system(
        checklists=[_checklist()],
        controls=[ControlAssessment(control_id="AC-3", status="compliant")],
        cci_control_map={"CCI-000213": ["AC-3"]},
    ).authorization
    assert ap2.rolled_up_control_status()["AC-3"] == "compliant"


def test_categorization_overall_high_water():
    cat = Categorization(confidentiality="LOW", integrity="HIGH", availability="MODERATE")
    assert str(cat.overall) == "HIGH"


def test_draft_poam_from_findings():
    ap = _system(checklists=[_checklist()]).authorization
    drafts = ap.draft_poam_from_findings()
    assert len(drafts) == 1
    d = drafts[0]
    assert d.source_rule_id == "SV-1_rule"
    assert d.component == "edge-fw-01"
    assert str(d.severity) == "high"
    assert str(d.status) == "not_started"

    # Already-covered findings are not re-drafted.
    ap2 = _system(
        checklists=[_checklist()],
        poam_items=[PoamItem(id="P1", weakness="known", component="edge-fw-01", source_rule_id="SV-1_rule")],
    ).authorization
    assert ap2.draft_poam_from_findings() == []


def test_poam_milestone_roundtrip():
    item = PoamItem(
        id="P1",
        weakness="Weak crypto",
        severity="high",
        component="edge-fw-01",
        milestones=[Milestone(description="Patch", status="completed", completion_date="2026-06-01")],
    )
    reloaded = PoamItem.model_validate(item.model_dump(mode="json"))
    assert reloaded.cat == "CAT I"
    assert reloaded.milestones[0].completion_date.isoformat() == "2026-06-01"


# --- rejections -------------------------------------------------------------

def test_reject_checklist_unknown_component():
    with pytest.raises(ValidationError):
        _system(checklists=[Checklist(benchmark_id="B", component="ghost")])


def test_reject_poam_unknown_component():
    with pytest.raises(ValidationError):
        _system(poam_items=[PoamItem(id="P1", weakness="w", component="ghost")])


def test_reject_duplicate_rule_id():
    with pytest.raises(ValidationError):
        Checklist(benchmark_id="B", results=[
            {"rule_id": "dup", "severity": "low", "status": "Open"},
            {"rule_id": "dup", "severity": "low", "status": "Open"},
        ])


def test_reject_duplicate_control_id():
    with pytest.raises(ValidationError):
        AuthorizationPackage(controls=[
            ControlAssessment(control_id="AC-2"),
            ControlAssessment(control_id="AC-2"),
        ])


def test_reject_duplicate_poam_id():
    with pytest.raises(ValidationError):
        AuthorizationPackage(poam_items=[
            PoamItem(id="P1", weakness="a"),
            PoamItem(id="P1", weakness="b"),
        ])


def test_reject_duplicate_cci_in_result():
    with pytest.raises(ValidationError):
        RuleResult(rule_id="r", severity="low", status="Open", ccis=["CCI-1", "CCI-1"])


def test_reject_invalid_status():
    with pytest.raises(ValidationError):
        RuleResult(rule_id="r", severity="low", status="Bogus")


def test_reject_milestone_completion_without_completed_status():
    with pytest.raises(ValidationError):
        Milestone(description="x", status="in_progress", completion_date="2026-06-01")
