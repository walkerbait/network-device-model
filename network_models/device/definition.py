"""The reusable device *type* definition and its catalog/compliance/config parts.

A *device definition* describes a reusable device **type** (e.g. "Cisco Catalyst
9300-48P") — its identity, physical attributes, ports/interfaces, applicable
STIGs, baseline layers, and Cisco Network-as-Code (NaC) integration — as distinct
from a concrete device *instance*. Definitions are the building blocks selected
when generating configs for a system or device.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pydantic import Field, StrictBool, field_validator, model_validator

if TYPE_CHECKING:
    from network_models.stig.catalog import StigCatalog

from network_models.base import StrictModel
from network_models.device.components import (
    ConsolePort,
    ConsoleServerPort,
    DeviceBay,
    FrontPort,
    Interface,
    InventoryItem,
    ModuleBay,
    PowerOutlet,
    PowerPort,
    RearPort,
)
from network_models.device.vocab import (
    SCHEMA_VERSION,
    Airflow,
    DeviceCategory,
    DeviceRole,
    NacConfigDomain,
    NetworkOS,
    SdwanPersonality,
    SubdeviceRole,
    WeightUnit,
)


# ---------------------------------------------------------------------------
# Device image, applicable STIGs, baseline layers, NaC integration
# ---------------------------------------------------------------------------
class DeviceImage(StrictModel):
    """References to a front and/or rear device image (path, URL, or asset id)."""

    front: Optional[str] = None
    rear: Optional[str] = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "DeviceImage":
        if self.front is None and self.rear is None:
            raise ValueError("device image must set at least one of front/rear")
        return self


class ApplicableStig(StrictModel):
    """A STIG that applies to this device *type*, referenced by concept.

    Version-agnostic on purpose: a device type is subject to a benchmark
    regardless of which release is current. The concrete version is pinned at the
    deployed-component layer (system.StigAssignment). ``title`` is an optional
    denormalized display cache so a picker can render without loading the catalog.
    """

    benchmark_id: str = Field(..., min_length=1)
    title: Optional[str] = None


class BaselineLayers(StrictModel):
    """Ordered configuration inheritance (NaC defaults/templates).

    ``common`` and ``role`` are required; ``system`` and ``program`` overlays are
    optional so a definition can be reused across systems/programs.
    """

    common: str = Field(..., min_length=1, description="Common baseline template id")
    role: str = Field(..., min_length=1, description="Role baseline template id")
    system: Optional[str] = Field(None, description="System overlay template id")
    program: Optional[str] = Field(None, description="Program overlay template id")


class SdwanProfile(StrictModel):
    """Cisco Catalyst SD-WAN device attributes (for cEdge/vEdge definitions)."""

    personality: SdwanPersonality
    device_model: str = Field(..., min_length=1, description="e.g. C8000V, ISR4451")
    feature_profiles: list[str] = Field(default_factory=list)
    edge_device_template: Optional[str] = None


class NacIntegration(StrictModel):
    """Cisco Network as Code integration for the device type."""

    config_domains: list[NacConfigDomain] = Field(
        default_factory=list,
        description="IOS-XE intent domains this definition contributes",
    )
    device_groups: list[str] = Field(
        default_factory=list,
        description="NaC device_group names this device type belongs to",
    )
    sdwan: Optional[SdwanProfile] = None

    @field_validator("config_domains", "device_groups")
    @classmethod
    def _unique(cls, v: list) -> list:
        if len(v) != len(set(v)):
            raise ValueError("values must be unique")
        return v


# ---------------------------------------------------------------------------
# Device definition (the reusable device type)
# ---------------------------------------------------------------------------
class DeviceDefinition(StrictModel):
    """A reusable device *type* definition."""

    # --- Identity ---
    manufacturer: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    slug: str = Field(
        ...,
        pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$",
        description="URL-safe identifier, lowercase (Nautobot-compatible)",
    )
    part_number: Optional[str] = None
    category: DeviceCategory
    platform: NetworkOS
    software_version: Optional[str] = None
    role: Optional[DeviceRole] = None
    description: Optional[str] = None
    comments: Optional[str] = None

    # --- Physical (Nautobot device-type) ---
    u_height: float = Field(1.0, ge=0, allow_inf_nan=False, description="Rack units; multiple of 0.5")
    is_full_depth: StrictBool = True
    subdevice_role: Optional[SubdeviceRole] = None
    airflow: Optional[Airflow] = None
    weight: Optional[float] = Field(None, gt=0, allow_inf_nan=False)
    weight_unit: Optional[WeightUnit] = None

    # --- Components ---
    interfaces: list[Interface] = Field(default_factory=list)
    console_ports: list[ConsolePort] = Field(default_factory=list)
    console_server_ports: list[ConsoleServerPort] = Field(default_factory=list)
    power_ports: list[PowerPort] = Field(default_factory=list)
    power_outlets: list[PowerOutlet] = Field(default_factory=list)
    front_ports: list[FrontPort] = Field(default_factory=list)
    rear_ports: list[RearPort] = Field(default_factory=list)
    device_bays: list[DeviceBay] = Field(default_factory=list)
    module_bays: list[ModuleBay] = Field(default_factory=list)
    inventory_items: list[InventoryItem] = Field(default_factory=list)

    # --- Catalog / compliance / config ---
    image: Optional[DeviceImage] = None
    applicable_stigs: list[ApplicableStig] = Field(default_factory=list)
    baseline_layers: Optional[BaselineLayers] = None
    nac: NacIntegration = Field(default_factory=NacIntegration)
    tags: list[str] = Field(default_factory=list)

    @field_validator("u_height")
    @classmethod
    def _u_height_half_increments(cls, v: float) -> float:
        if round(v * 2) != v * 2:
            raise ValueError("u_height must be a multiple of 0.5")
        return v

    @model_validator(mode="after")
    def _weight_pairing(self) -> "DeviceDefinition":
        if (self.weight is None) != (self.weight_unit is None):
            raise ValueError("weight and weight_unit must be provided together")
        return self

    @model_validator(mode="after")
    def _unique_applicable_stigs(self) -> "DeviceDefinition":
        # Uniqueness reverts to benchmark_id alone (version now lives on the
        # deployed Component's StigAssignment, not on the device *type*).
        ids = [s.benchmark_id for s in self.applicable_stigs]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate benchmark_id in applicable_stigs")
        return self

    def validate_against_catalog(self, catalog: "StigCatalog") -> "DeviceDefinition":
        """Assert every applicable STIG resolves to a catalog benchmark_id.

        Opt-in: call explicitly when a catalog is available. Standalone validation
        (no catalog) never requires resolution, so device libraries with empty or
        unresolved applicable_stigs still load. Returns self for chaining.
        """
        known = set(catalog.benchmark_ids())
        missing = [s.benchmark_id for s in self.applicable_stigs if s.benchmark_id not in known]
        if missing:
            raise ValueError(f"applicable_stigs do not resolve in catalog: {missing}")
        return self

    @model_validator(mode="after")
    def _component_names_unique(self) -> "DeviceDefinition":
        for attr in (
            "interfaces", "console_ports", "console_server_ports", "power_ports",
            "power_outlets", "front_ports", "rear_ports", "device_bays",
            "module_bays", "inventory_items",
        ):
            names = [c.name for c in getattr(self, attr)]
            if len(names) != len(set(names)):
                raise ValueError(f"duplicate component name in {attr}")
        return self

    @model_validator(mode="after")
    def _port_references_resolve(self) -> "DeviceDefinition":
        rear_names = {p.name: p for p in self.rear_ports}
        seen_fp: set = set()
        for fp in self.front_ports:
            rp = rear_names.get(fp.rear_port)
            if rp is None:
                raise ValueError(
                    f"front_port '{fp.name}' references unknown rear_port '{fp.rear_port}'"
                )
            if fp.rear_port_position > rp.positions:
                raise ValueError(
                    f"front_port '{fp.name}' position {fp.rear_port_position} "
                    f"exceeds rear_port '{rp.name}' positions ({rp.positions})"
                )
            key = (fp.rear_port, fp.rear_port_position)
            if key in seen_fp:
                raise ValueError(
                    f"multiple front_ports map to rear_port '{fp.rear_port}' "
                    f"position {fp.rear_port_position}"
                )
            seen_fp.add(key)
        power_names = {p.name for p in self.power_ports}
        for outlet in self.power_outlets:
            if outlet.power_port is not None and outlet.power_port not in power_names:
                raise ValueError(
                    f"power_outlet '{outlet.name}' references unknown power_port "
                    f"'{outlet.power_port}'"
                )
        return self


class DeviceDefinitionLibrary(StrictModel):
    """Top-level container: a versioned collection of device definitions."""

    version: str = Field(default=SCHEMA_VERSION)
    definitions: list[DeviceDefinition] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def _supported_version(cls, v: str) -> str:
        if v != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema version: {v!r}")
        return v

    @model_validator(mode="after")
    def _unique_slugs(self) -> "DeviceDefinitionLibrary":
        slugs = [d.slug for d in self.definitions]
        if len(slugs) != len(set(slugs)):
            raise ValueError("definition slugs must be unique within a library")
        return self


__all__ = [
    "DeviceImage", "ApplicableStig", "BaselineLayers", "SdwanProfile",
    "NacIntegration", "DeviceDefinition", "DeviceDefinitionLibrary",
]
