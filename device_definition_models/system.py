"""DRAFT: strict Pydantic v2 model for a **system** (a deployed network).

Where a :class:`~device_definition_models.models.DeviceDefinition` describes a
reusable device *type*, a :class:`System` describes a concrete deployment: a set
of **enclaves** (security zones ordered least -> most classified), the
**components** (device instances) that live in them, and the **connections**
between component interfaces. It mirrors the System Viewer design:

    System context bar  -> System (id, customer, network, project, environment, ATO, ...)
    Enclave columns     -> Enclave (name, classification)  [ordered least->most]
    Component nodes     -> Component (id, category, device_definition slug, enclave)
    Connections + trunk -> Connection (endpoint a/b with interface, trunk flag)

This is an early draft: fields and validators are expected to evolve. It reuses
the strict base model and the device taxonomy from ``models.py`` and depends only
on ``pydantic>=2.5`` + stdlib, so it stays portable alongside the device models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import (
    Field,
    IPvAnyAddress,
    StrictBool,
    field_validator,
    model_validator,
)

from device_definition_models.models import (
    DeviceCategory,
    StrictModel,
    _str_enum,
)

SYSTEM_SCHEMA_VERSION = "0.1-draft"


# ---------------------------------------------------------------------------
# Vocabularies
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
    """One end of a connection: a component and the interface it terminates on."""

    component: str = Field(..., min_length=1, description="Component id")
    interface: Optional[str] = Field(
        None,
        description="Interface name on the component's device definition, e.g. 'Gi0/2'",
    )


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


__all__ = [
    "SYSTEM_SCHEMA_VERSION",
    "Classification", "Environment", "AtoStatus", "LinkMedia",
    "Enclave", "Component", "Endpoint", "Connection", "System",
]
