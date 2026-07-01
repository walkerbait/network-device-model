"""The deployed-system topology: enclaves, components, connections, and System.

Where a :class:`~network_models.device.definition.DeviceDefinition` describes a
reusable device *type*, a :class:`System` describes a concrete deployment: a set
of **enclaves** (security zones ordered least -> most classified), the
**components** (device instances) that live in them, and the **connections**
between component interfaces. It mirrors the System Viewer design:

    System context bar  -> System (id, customer, network, project, environment, ATO, ...)
    Enclave columns     -> Enclave (name, classification)  [ordered least->most]
    Component nodes     -> Component (id, category, device_definition slug, enclave)
    Connections + trunk -> Connection (endpoint a/b with interface, trunk flag)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, IPvAnyAddress, StrictBool, field_validator, model_validator

from network_models.base import StrictModel
from network_models.device.vocab import DeviceCategory
from network_models.system.l2 import SpanningTree, Switchport, Vlan
from network_models.system.vocab import (
    CLASSIFICATION_LEVEL,
    SYSTEM_SCHEMA_VERSION,
    AtoStatus,
    Classification,
    Environment,
    LinkMedia,
    PortChannelMode,
    SwitchportMode,
)


# ---------------------------------------------------------------------------
# Enclave
# ---------------------------------------------------------------------------
class Enclave(StrictModel):
    """A security zone that contains components, keyed by classification."""

    name: str = Field(..., min_length=1)
    classification: Classification
    description: Optional[str] = None

    @property
    def level(self) -> int:
        """Ordering index (0 = least classified)."""
        return CLASSIFICATION_LEVEL[str(self.classification)]


# ---------------------------------------------------------------------------
# Component (a device instance deployed in an enclave)
# ---------------------------------------------------------------------------
class Component(StrictModel):
    """A concrete device in the system (an instance of a device definition)."""

    id: str = Field(..., min_length=1, description="Unique within the system, e.g. 'edge-fw-01'")
    name: Optional[str] = None
    enclave: str = Field(..., min_length=1, description="Name of the containing enclave")
    category: DeviceCategory
    device_definition: Optional[str] = Field(
        None, description="Slug of the device definition this instance is built from"
    )
    hostname: Optional[str] = None
    mgmt_ip: Optional[IPvAnyAddress] = None
    role: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Connection (a link between two component interfaces)
# ---------------------------------------------------------------------------
class Endpoint(StrictModel):
    """One end of a connection: a component and the interface(s) it terminates on.

    A single physical link uses ``interface``. An aggregated (LAG / port-channel)
    link uses ``members`` to list the bundled physical interfaces, mirroring NaC's
    ``port_channel_id`` / ``port_channel_mode`` on the member ethernets.
    """

    component: str = Field(..., min_length=1, description="Component id")
    interface: Optional[str] = Field(
        None,
        description="Interface name on the component's device definition, e.g. 'Gi0/2'",
    )
    members: list[str] = Field(
        default_factory=list,
        description="Physical member interfaces when this end is a LAG/port-channel",
    )
    port_channel_id: Optional[int] = Field(None, ge=1, le=512)
    port_channel_mode: Optional[PortChannelMode] = None
    switchport: Optional[Switchport] = None
    spanning_tree: Optional[SpanningTree] = None

    @model_validator(mode="after")
    def _lag_consistency(self) -> "Endpoint":
        if self.members and self.interface is not None:
            raise ValueError(
                "endpoint uses either 'interface' (single link) or 'members' (LAG), not both"
            )
        if self.members:
            if len(self.members) != len(set(self.members)):
                raise ValueError("duplicate interface in LAG members")
            if self.port_channel_id is None:
                raise ValueError("LAG endpoint (members set) requires port_channel_id")
        if self.port_channel_mode is not None and self.port_channel_id is None:
            raise ValueError("port_channel_mode requires port_channel_id")
        return self


class Connection(StrictModel):
    """A link between two component interfaces. `trunk` marks switch-to-switch VLAN trunks."""

    a: Endpoint
    b: Endpoint
    trunk: StrictBool = False
    media: Optional[LinkMedia] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def _distinct_ends(self) -> "Connection":
        if self.a.component == self.b.component:
            raise ValueError("a connection must join two different components")
        return self

    @model_validator(mode="after")
    def _switchport_mode_agreement(self) -> "Connection":
        # If both ends declare a switchport mode, they must match (an access<->trunk
        # link is a misconfiguration), and `trunk` must reflect that mode.
        modes = [e.switchport.mode for e in (self.a, self.b) if e.switchport is not None]
        if len(modes) == 2 and modes[0] != modes[1]:
            raise ValueError(
                f"connection ends disagree on switchport mode: {modes[0]} vs {modes[1]}"
            )
        if modes:
            declared_trunk = modes[0] == SwitchportMode("trunk")
            if declared_trunk != bool(self.trunk):
                raise ValueError(
                    "connection 'trunk' flag disagrees with endpoint switchport mode"
                )
        return self


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------
class System(StrictModel):
    """A deployed network: enclaves, components, and their connections."""

    # --- Context bar ---
    id: str = Field(..., min_length=1, description="System identifier, e.g. 'SYS-00428'")
    name: str = Field(..., min_length=1)
    customer: Optional[str] = None
    network: Optional[str] = Field(None, description="Customer network, e.g. 'TGB', 'TEP', 'SIPR'")
    project: Optional[str] = None
    environment: Optional[Environment] = None
    ato_status: Optional[AtoStatus] = None
    last_synced: Optional[datetime] = None

    # --- Topology ---
    enclaves: list[Enclave] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)
    vlans: list[Vlan] = Field(
        default_factory=list,
        description="System-wide VLAN table; switchport VLAN ids must resolve here",
    )

    schema_version: str = SYSTEM_SCHEMA_VERSION

    # -- derived views --
    @property
    def classification_high_water(self) -> Optional[Classification]:
        """The most sensitive classification across the system's enclaves."""
        if not self.enclaves:
            return None
        return max(self.enclaves, key=lambda e: e.level).classification

    @property
    def enclaves_least_to_most(self) -> list[Enclave]:
        """Enclaves ordered least -> most classified (left -> right in the viewer)."""
        return sorted(self.enclaves, key=lambda e: e.level)

    # -- integrity --
    @field_validator("enclaves")
    @classmethod
    def _unique_enclave_names(cls, v: list[Enclave]) -> list[Enclave]:
        names = [e.name for e in v]
        if len(names) != len(set(names)):
            raise ValueError("enclave names must be unique")
        return v

    @field_validator("components")
    @classmethod
    def _unique_component_ids(cls, v: list[Component]) -> list[Component]:
        ids = [c.id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("component ids must be unique")
        return v

    @field_validator("vlans")
    @classmethod
    def _unique_vlan_ids(cls, v: list[Vlan]) -> list[Vlan]:
        ids = [vlan.id for vlan in v]
        if len(ids) != len(set(ids)):
            raise ValueError("VLAN ids must be unique")
        return v

    @model_validator(mode="after")
    def _references_resolve(self) -> "System":
        enclave_names = {e.name for e in self.enclaves}
        for c in self.components:
            if c.enclave not in enclave_names:
                raise ValueError(
                    f"component '{c.id}' references unknown enclave '{c.enclave}'"
                )
        component_ids = {c.id for c in self.components}
        for conn in self.connections:
            for end in (conn.a, conn.b):
                if end.component not in component_ids:
                    raise ValueError(
                        f"connection references unknown component '{end.component}'"
                    )
        return self

    @model_validator(mode="after")
    def _switchport_vlans_defined(self) -> "System":
        # Every VLAN id referenced by a switchport must exist in the VLAN table
        # (only enforced when a table is provided, so partial drafts stay usable).
        if not self.vlans:
            return self
        defined = {vlan.id for vlan in self.vlans}
        for conn in self.connections:
            for end in (conn.a, conn.b):
                sp = end.switchport
                if sp is None:
                    continue
                referenced: set[int] = set()
                if sp.access_vlan is not None:
                    referenced.add(sp.access_vlan)
                if sp.native_vlan is not None:
                    referenced.add(sp.native_vlan)
                if sp.allowed_vlans is not None:
                    referenced |= sp.allowed_vlans.expand()
                missing = referenced - defined
                if missing:
                    raise ValueError(
                        f"switchport on component '{end.component}' references "
                        f"undefined VLAN id(s): {sorted(missing)}"
                    )
        return self


__all__ = [
    "Enclave", "Component", "Endpoint", "Connection", "System",
]
