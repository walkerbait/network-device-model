"""Vocabularies for the STIG catalog domain.

Values mirror DISA XCCDF 1.1 benchmark content verbatim so the importer maps
fields byte-for-byte. Keep every value list as the single, auditable source of
truth; adding a value is a one-line change.
"""

from __future__ import annotations

from network_models._enum import _str_enum

STIG_SCHEMA_VERSION = "0.1-draft"

# XCCDF Rule/@severity -> DISA CAT level:
#   high = CAT I, medium = CAT II, low = CAT III. "unknown" is the XCCDF default.
RULE_SEVERITIES = ["high", "medium", "low", "unknown"]
SEVERITY_TO_CAT = {"high": "CAT I", "medium": "CAT II", "low": "CAT III"}

# Whether a catalog entry is a Security Requirements Guide (technology-agnostic,
# lineage only) or a STIG (concrete, selectable/assignable in the picker).
STIG_TYPES = ["srg", "stig"]

# Per-component assessment status of a pinned STIG assignment.
#   inherited_pending = applies via inheritance/overlay but not yet assessed here.
ASSIGNMENT_STATUSES = [
    "not_assessed",
    "compliant",
    "open",
    "not_applicable",
    "inherited_pending",
]

# Where a (future, app-layer) ComplianceCheck asserts. Kept here so the vocabulary
# is shared, even though ComplianceCheck itself is out of scope for this package.
#   nac_config = assert against the rendered Cisco NaC document (primary surface)
#   model      = assert against the network_models instances (alternative)
TARGET_LAYERS = ["nac_config", "model"]

RuleSeverity = _str_enum("RuleSeverity", RULE_SEVERITIES)
StigType = _str_enum("StigType", STIG_TYPES)
AssignmentStatus = _str_enum("AssignmentStatus", ASSIGNMENT_STATUSES)
TargetLayer = _str_enum("TargetLayer", TARGET_LAYERS)

__all__ = [
    "STIG_SCHEMA_VERSION",
    "RULE_SEVERITIES", "SEVERITY_TO_CAT", "STIG_TYPES",
    "ASSIGNMENT_STATUSES", "TARGET_LAYERS",
    "RuleSeverity", "StigType", "AssignmentStatus", "TargetLayer",
]
