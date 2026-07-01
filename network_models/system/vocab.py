"""Vocabularies for the deployed-system model: classification tiers, environment,
ATO status, link media, and the Layer-2 enums aligned with the Cisco NaC IOS-XE
ethernet interface schema.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from network_models._enum import _str_enum

SYSTEM_SCHEMA_VERSION = "0.1-draft"


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
    "Classification", "Environment", "AtoStatus", "LinkMedia",
    "SwitchportMode", "PortChannelMode", "StpGuard", "StpLinkType", "VlanId",
]
