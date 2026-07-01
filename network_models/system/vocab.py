"""Vocabularies for the deployed-system model: classification tiers, environment,
ATO status, link media, and the Layer-2 enums aligned with the Cisco NaC IOS-XE
ethernet interface schema.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from network_models._enum import _str_enum

SYSTEM_SCHEMA_VERSION = "0.2-draft"


# ---------------------------------------------------------------------------
# System vocabularies
# ---------------------------------------------------------------------------
# Classification tiers, ordered least -> most sensitive. The index is the
# ordering used to lay enclaves out left -> right and to compute the system's
# high-water mark.
CLASSIFICATIONS = [
    "UNCLASSIFIED",
    "CUI",
    "CONFIDENTIAL",
    "SECRET",
    "TOP_SECRET",
    "TS_SCI",
]
CLASSIFICATION_LEVEL = {name: idx for idx, name in enumerate(CLASSIFICATIONS)}

ENVIRONMENTS = ["production", "staging", "development", "test", "lab"]
ATO_STATUSES = [
    "authorized",
    "in_process",
    "reauthorization",
    "expired",
    "denied",
    "not_started",
]

# Physical/logical media of a connection (drives styling; trunk is separate).
LINK_MEDIA = ["copper", "fiber", "wireless", "serial", "virtual", "other"]

Classification = _str_enum("Classification", CLASSIFICATIONS)
Environment = _str_enum("Environment", ENVIRONMENTS)
AtoStatus = _str_enum("AtoStatus", ATO_STATUSES)
LinkMedia = _str_enum("LinkMedia", LINK_MEDIA)


# ---------------------------------------------------------------------------
# Authorization-package (RMF / OpenRMF) vocabularies
# ---------------------------------------------------------------------------
# CKL / STIG Viewer rule-result status values (verbatim wire strings), used for
# evaluated checklist results and the OpenRMF-style scoring rollup.
CHECKLIST_STATUSES = ["Open", "NotAFinding", "Not_Reviewed", "Not_Applicable"]

# NIST SP 800-53(A) control assessment states.
CONTROL_STATUSES = [
    "compliant",
    "non_compliant",
    "not_applicable",
    "not_assessed",
    "inherited",
    "planned",
]

# POA&M lifecycle states (RMF) and per-milestone states.
POAM_STATUSES = ["ongoing", "completed", "risk_accepted", "not_started"]
MILESTONE_STATUSES = ["pending", "in_progress", "completed", "delayed"]

# FIPS-199 impact levels, ordered least -> most (index drives the categorization
# high-water mark, mirroring CLASSIFICATION_LEVEL above).
IMPACT_LEVELS = ["LOW", "MODERATE", "HIGH"]
IMPACT_LEVEL_RANK = {name: idx for idx, name in enumerate(IMPACT_LEVELS)}

ChecklistStatus = _str_enum("ChecklistStatus", CHECKLIST_STATUSES)
ControlStatus = _str_enum("ControlStatus", CONTROL_STATUSES)
PoamStatus = _str_enum("PoamStatus", POAM_STATUSES)
MilestoneStatus = _str_enum("MilestoneStatus", MILESTONE_STATUSES)
ImpactLevel = _str_enum("ImpactLevel", IMPACT_LEVELS)

# XCCDF <rule-result><result> value -> CKL ChecklistStatus. The SCAP importer in
# network_models.io reads this as its single source of truth; unmapped values are
# treated conservatively as Not_Reviewed. error/unknown/informational are
# un-reviewed; pass/fixed pass; notapplicable/notselected are N/A.
XCCDF_RESULT_TO_STATUS = {
    "pass": "NotAFinding",
    "fixed": "NotAFinding",
    "fail": "Open",
    "notchecked": "Not_Reviewed",
    "error": "Not_Reviewed",
    "unknown": "Not_Reviewed",
    "informational": "Not_Reviewed",
    "notapplicable": "Not_Applicable",
    "notselected": "Not_Applicable",
}


# ---------------------------------------------------------------------------
# Layer-2 vocabularies (aligned verbatim with the Cisco NaC IOS-XE ethernet
# interface schema so a generator can map these to NaC YAML near-directly).
#   https://netascode.cisco.com/docs/data_models/iosxe/interface/ethernet/
# ---------------------------------------------------------------------------
# switchport.mode
SWITCHPORT_MODES = [
    "access",
    "trunk",
    "dot1q-tunnel",
    "private-vlan-host",
    "private-vlan-promiscuous",
    "private-vlan-trunk",
]
# ethernets.port_channel_mode (LACP / PAgP / static)
PORT_CHANNEL_MODES = ["active", "passive", "on", "auto", "desirable"]
# spanning_tree.guard
STP_GUARD_MODES = ["loop", "root", "none"]
# spanning_tree.link_type
STP_LINK_TYPES = ["shared", "point-to-point"]

SwitchportMode = _str_enum("SwitchportMode", SWITCHPORT_MODES)
PortChannelMode = _str_enum("PortChannelMode", PORT_CHANNEL_MODES)
StpGuard = _str_enum("StpGuard", STP_GUARD_MODES)
StpLinkType = _str_enum("StpLinkType", STP_LINK_TYPES)

# 802.1Q VLAN id range (NaC constrains access_vlan / native_vlan / trunk ids to 1..4094).
VlanId = Annotated[int, Field(ge=1, le=4094)]


__all__ = [
    "SYSTEM_SCHEMA_VERSION",
    "CLASSIFICATIONS", "CLASSIFICATION_LEVEL", "ENVIRONMENTS", "ATO_STATUSES",
    "LINK_MEDIA", "SWITCHPORT_MODES", "PORT_CHANNEL_MODES", "STP_GUARD_MODES",
    "STP_LINK_TYPES",
    "CHECKLIST_STATUSES", "CONTROL_STATUSES", "POAM_STATUSES", "MILESTONE_STATUSES",
    "IMPACT_LEVELS", "IMPACT_LEVEL_RANK", "XCCDF_RESULT_TO_STATUS",
    "Classification", "Environment", "AtoStatus", "LinkMedia",
    "SwitchportMode", "PortChannelMode", "StpGuard", "StpLinkType", "VlanId",
    "ChecklistStatus", "ControlStatus", "PoamStatus", "MilestoneStatus", "ImpactLevel",
]
