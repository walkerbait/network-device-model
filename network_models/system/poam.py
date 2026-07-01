"""Plan of Action & Milestones (POA&M) models for the authorization package.

A :class:`PoamItem` records a weakness that must be tracked to closure, with
traceability hooks back to the finding it came from (``source_rule_id`` /
``source_cci`` / ``component``) and a list of :class:`Milestone` steps. POA&M
items are typically seeded from Open checklist findings — see
``AuthorizationPackage.draft_poam_from_findings``.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import Field, model_validator

from network_models.base import StrictModel
from network_models.stig.vocab import SEVERITY_TO_CAT, RuleSeverity
from network_models.system.vocab import MilestoneStatus, PoamStatus


class Milestone(StrictModel):
    """A POA&M milestone with a scheduled date and status."""

    description: str = Field(..., min_length=1)
    scheduled_date: Optional[date] = None
    completion_date: Optional[date] = None
    status: MilestoneStatus = MilestoneStatus("pending")

    @model_validator(mode="after")
    def _completion_requires_completed(self) -> "Milestone":
        if self.completion_date is not None and str(self.status) != "completed":
            raise ValueError(
                "milestone completion_date is set but status is not 'completed'"
            )
        return self


class PoamItem(StrictModel):
    """A Plan of Action & Milestones entry for the authorization package.

    ``severity`` reuses the STIG :class:`~network_models.stig.vocab.RuleSeverity`
    vocabulary so there is one severity scale across the whole library. The
    ``source_*`` / ``component`` fields tie an item back to the finding it derives
    from (used for dedup when drafting from checklist results).
    """

    id: str = Field(..., min_length=1, description="POA&M id, unique within the package")
    weakness: str = Field(..., min_length=1, description="Weakness / deficiency description")
    source_control: Optional[str] = Field(None, description="Originating 800-53 control, e.g. 'AC-2'")
    source_rule_id: Optional[str] = Field(None, description="Source finding rule_id, if from a checklist")
    source_cci: Optional[str] = Field(None, description="Source CCI, if applicable")
    severity: Optional[RuleSeverity] = None
    component: Optional[str] = Field(None, description="Affected component id")
    resources_required: Optional[str] = None
    scheduled_completion: Optional[date] = None
    milestones: list[Milestone] = Field(default_factory=list)
    status: PoamStatus = PoamStatus("not_started")
    comments: Optional[str] = None

    @property
    def cat(self) -> Optional[str]:
        """DISA CAT label derived from severity, if set."""
        return SEVERITY_TO_CAT.get(str(self.severity)) if self.severity is not None else None


__all__ = ["Milestone", "PoamItem"]
