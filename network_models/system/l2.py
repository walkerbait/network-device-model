"""Layer-2 models: VLAN table + interface switchport/STP profiles.

Aligned with the Cisco NaC IOS-XE ``switchport`` and ``spanning_tree`` classes so
a generator can map these to NaC YAML near-directly.
  https://netascode.cisco.com/docs/data_models/iosxe/interface/ethernet/
"""

from __future__ import annotations

from typing import Optional

from pydantic import ConfigDict, Field, StrictBool, model_validator

from network_models.base import StrictModel
from network_models.system.vocab import (
    StpGuard,
    StpLinkType,
    SwitchportMode,
    VlanId,
)


class Vlan(StrictModel):
    """An 802.1Q VLAN definition. VLANs are defined once (system- or device-level)
    and referenced by id from switchport profiles — mirroring NaC's device-level
    ``vlans`` section that interface ``access_vlan`` / trunk ids point at."""

    id: VlanId
    name: Optional[str] = Field(None, description="VLAN name, e.g. 'USERS'")
    description: Optional[str] = None


class VlanRange(StrictModel):
    """An inclusive VLAN id range, matching NaC ``trunk_allowed_vlans.ranges``."""

    from_: VlanId = Field(..., alias="from")
    to: VlanId

    # Accept both the NaC wire name ("from") and the python-safe "from_".
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def _ordered(self) -> "VlanRange":
        if self.from_ > self.to:
            raise ValueError("VLAN range 'from' must be <= 'to'")
        return self


class TrunkAllowedVlans(StrictModel):
    """Allowed-VLAN expression for a trunk, mirroring NaC ``trunk_allowed_vlans``.

    A trunk allows VLANs by one of: ``all``, ``none``, or an explicit set of
    ``ids`` and/or ``ranges``. These forms are mutually exclusive, matching the
    upstream schema (``all`` / ``none`` booleans vs. the ids/ranges lists).
    """

    all: StrictBool = False
    none: StrictBool = False
    ids: list[VlanId] = Field(default_factory=list)
    ranges: list[VlanRange] = Field(default_factory=list)

    @model_validator(mode="after")
    def _exclusive(self) -> "TrunkAllowedVlans":
        explicit = bool(self.ids or self.ranges)
        chosen = sum([self.all, self.none, explicit])
        if chosen > 1:
            raise ValueError(
                "trunk allowed VLANs must be exactly one of: all, none, or ids/ranges"
            )
        if self.ids and len(self.ids) != len(set(self.ids)):
            raise ValueError("duplicate VLAN id in trunk allowed ids")
        return self

    def expand(self) -> set[int]:
        """The concrete set of explicitly-allowed VLAN ids (empty for all/none)."""
        out = set(self.ids)
        for r in self.ranges:
            out.update(range(r.from_, r.to + 1))
        return out


class SpanningTree(StrictModel):
    """Per-interface STP options (subset of NaC ``spanning_tree``)."""

    portfast: Optional[StrictBool] = None
    portfast_trunk: Optional[StrictBool] = None
    bpduguard: Optional[StrictBool] = None
    guard: Optional[StpGuard] = None
    link_type: Optional[StpLinkType] = None


class Switchport(StrictModel):
    """Layer-2 switchport configuration for one interface, aligned with the NaC
    IOS-XE ``switchport`` class so it maps near-directly to NaC YAML.

    ``mode`` drives which VLAN fields are valid: ``access`` uses ``access_vlan``;
    ``trunk`` uses ``native_vlan`` / ``allowed_vlans``.
    """

    enable: StrictBool = True
    mode: SwitchportMode
    access_vlan: Optional[VlanId] = None
    native_vlan: Optional[VlanId] = None
    native_vlan_tag: Optional[StrictBool] = None
    allowed_vlans: Optional[TrunkAllowedVlans] = None
    nonegotiate: Optional[StrictBool] = None

    @model_validator(mode="after")
    def _mode_field_consistency(self) -> "Switchport":
        is_access = self.mode == SwitchportMode("access")
        is_trunk = self.mode == SwitchportMode("trunk")
        if is_access:
            if self.native_vlan is not None or self.allowed_vlans is not None:
                raise ValueError(
                    "access switchport cannot set native_vlan/allowed_vlans"
                )
        elif is_trunk:
            if self.access_vlan is not None:
                raise ValueError("trunk switchport cannot set access_vlan")
        return self


__all__ = [
    "Vlan", "VlanRange", "TrunkAllowedVlans", "SpanningTree", "Switchport",
]
