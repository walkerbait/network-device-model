"""Strict Pydantic v2 data models for reusable **device definitions**.

A *device definition* describes a reusable device **type** (e.g. "Cisco Catalyst
9300-48P") — its identity, physical attributes, ports/interfaces, applicable
STIGs, baseline layers, and Cisco Network-as-Code (NaC) integration — as
distinct from a concrete device *instance* (a specific unit with a hostname and
management IP). Definitions are the building blocks selected when generating
configs for a system or device.

Design goals
------------
* **Portable / self-contained.** Depends only on ``pydantic>=2.5`` and the
  standard library, with no imports from this application, so the package can be
  vendored here today and extracted into its own shared repository later.
* **Strict enforcement.** Every model forbids unknown keys, strips whitespace,
  and validates on assignment. Constrained fields use enums whose values are
  taken *verbatim* from the authoritative schemas below, so an out-of-model
  value fails validation instead of silently passing.
* **Open to extension.** Enum value lists are defined as module-level constants
  (the auditable source of truth). Onboarding a new interface/port type or
  device category is a one-line change, and most vocabularies keep an
  ``"other"`` escape hatch mirroring the upstream schemas.

Sources of truth
----------------
* Nautobot ``devicetype-library`` component schema — interface/port ``type``
  enums, PoE, airflow, weight, subdevice role:
  https://github.com/nautobot/devicetype-library
* Cisco Network as Code (NaC) — IOS-XE ``device_group`` entity, configuration
  domains, and Catalyst SD-WAN device personalities:
  https://netascode.cisco.com/docs/data_models/
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Enum construction helper
# ---------------------------------------------------------------------------
def _member_name(value: str) -> str:
    """Derive a valid, upper-snake Python identifier from an enum *value*."""
    name = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").upper()
    if not name:
        return "UNSET"
    if name[0].isdigit():
        name = f"N{name}"
    return name


def _str_enum(name: str, values: list[str]) -> type[Enum]:
    """Build a ``str``-valued :class:`Enum` from a verbatim list of values.

    Member *names* are derived automatically so the value list stays the single,
    auditable source of truth (matching the upstream schema byte-for-byte).
    """
    members: dict[str, str] = {}
    for value in values:
        member = _member_name(value)
        candidate, suffix = member, 2
        while candidate in members:
            candidate = f"{member}_{suffix}"
            suffix += 1
        members[candidate] = value
    cls = Enum(name, members, type=str)  # type: ignore[assignment]
    # A functional str-Enum member renders as its *repr* ("InterfaceType.N1000BASE_T")
    # under str()/format()/f-strings, not its value — which would corrupt generated
    # config text. Give the class value-returning dunders. (enum.StrEnum would do this
    # but is 3.11+; the supported floor is 3.10, so assign explicitly.)
    cls.__str__ = lambda self: str(self.value)  # type: ignore[assignment]
    cls.__format__ = lambda self, spec: format(self.value, spec)  # type: ignore[assignment]
    return cls  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Vocabularies — device taxonomy (this project) + Cisco NaC personalities
# ---------------------------------------------------------------------------
DEVICE_CATEGORIES = [
    "switch",
    "router",
    "firewall",
    "wireless-ap",
    "wireless-controller",
    "radio",
    "server",
    "storage",
    "computer",
    "laptop",
    "load-balancer",
    "ids-ips",
    "vpn-concentrator",
    "console-server",
    "pdu",
    "appliance",
    "sensor",
    "other",
]

# Network operating system / platform. ``cisco-*`` aligns with NaC device-centric
# models; ``cisco-catalyst-sdwan`` covers controller/edge (cEdge) devices.
NETWORK_OS = [
    "cisco-ios-xe",
    "cisco-nx-os",
    "cisco-ios-xr",
    "cisco-catalyst-sdwan",
    "cisco-ftd",
    "cisco-asa",
    "cisco-aireos",
    "arista-eos",
    "juniper-junos",
    "paloalto-panos",
    "fortinet-fortios",
    "linux",
    "rhel",
    "windows",
    "windows-server",
    "harris-os",
    "other",
]

# Roles: superset aligned with this project's existing ``DeviceRole`` plus common
# hierarchy roles and Cisco SD-WAN personalities.
DEVICE_ROLES = [
    "router",
    "switch",
    "firewall-edge",
    "wireless-controller",
    "access",
    "distribution",
    "core",
    "edge",
    "management",
    "cedge",
    "vedge",
    # project-specific enclave switch/router roles
    "red_ess",
    "black_ess",
    "grey_ess",
    "red_esr",
    "black_esr",
    "grey_esr",
    "other",
]

# Cisco NaC IOS-XE intent/configuration domains (device_group.configuration.*).
NAC_CONFIG_DOMAINS = [
    "system",
    "aaa",
    "interfaces",
    "routing",
    "switching",
    "vlans",
    "security",
    "services",
    "qos",
    "multicast",
    "mpls",
    "vpn",
    "wireless",
    "monitoring",
    "other",
]

SDWAN_PERSONALITIES = ["cedge", "vedge", "vsmart", "vbond", "vmanage"]


# ---------------------------------------------------------------------------
# Vocabularies — Nautobot devicetype-library (verbatim enum values)
# ---------------------------------------------------------------------------
INTERFACE_TYPES = [
    "virtual", "bridge", "lag",
    # Ethernet (copper)
    "100base-fx", "100base-lfx", "100base-tx", "100base-t1", "1000base-t",
    "2.5gbase-t", "5gbase-t", "10gbase-t", "10gbase-cx4",
    # Ethernet (modular / fiber)
    "1000base-x-gbic", "1000base-x-sfp", "10gbase-x-sfpp", "10gbase-x-xfp",
    "10gbase-x-xenpak", "10gbase-x-x2", "25gbase-x-sfp28", "50gbase-x-sfp56",
    "50gbase-x-sfp28",
    "40gbase-x-qsfpp", "100gbase-x-cfp", "100gbase-x-cfp2", "200gbase-x-cfp2",
    "400gbase-x-cfp2", "100gbase-x-cfp4", "100gbase-x-cxp", "100gbase-x-cpak",
    "100gbase-x-dsfp", "100gbase-x-sfpdd", "100gbase-x-qsfp28",
    "100gbase-x-qsfpdd", "200gbase-x-qsfp56", "200gbase-x-qsfpdd",
    "400gbase-x-qsfp112", "400gbase-x-qsfpdd", "400gbase-x-osfp",
    "400gbase-x-osfp-rhs", "400gbase-x-cdfp", "400gbase-x-cfp8",
    "800gbase-x-qsfpdd", "800gbase-x-osfp",
    # Ethernet (backplane)
    "1000base-kx", "10gbase-kr", "10gbase-kx4", "25gbase-kr", "40gbase-kr4",
    "50gbase-kr", "100gbase-kp4", "100gbase-kr2", "100gbase-kr4",
    # Wireless
    "ieee802.11a", "ieee802.11g", "ieee802.11n", "ieee802.11ac",
    "ieee802.11ad", "ieee802.11ax", "ieee802.11ay", "ieee802.15.1",
    "other-wireless",
    # Cellular
    "gsm", "cdma", "lte",
    # SONET
    "sonet-oc3", "sonet-oc12", "sonet-oc48", "sonet-oc192", "sonet-oc768",
    "sonet-oc1920", "sonet-oc3840",
    # Fibre Channel
    "1gfc-sfp", "2gfc-sfp", "4gfc-sfp", "8gfc-sfpp", "16gfc-sfpp",
    "32gfc-sfp28", "64gfc-qsfpp", "128gfc-qsfp28",
    # InfiniBand
    "infiniband-sdr", "infiniband-ddr", "infiniband-qdr", "infiniband-fdr10",
    "infiniband-fdr", "infiniband-edr", "infiniband-hdr", "infiniband-ndr",
    "infiniband-xdr",
    # Serial / access
    "t1", "e1", "t3", "e3", "xdsl", "docsis",
    # PON
    "gpon", "xg-pon", "xgs-pon", "ng-pon2", "epon", "10g-epon",
    # Stacking
    "cisco-stackwise", "cisco-stackwise-plus", "cisco-flexstack",
    "cisco-flexstack-plus", "cisco-stackwise-80", "cisco-stackwise-160",
    "cisco-stackwise-320", "cisco-stackwise-480", "cisco-stackwise-1t",
    "juniper-vcp", "extreme-summitstack", "extreme-summitstack-128",
    "extreme-summitstack-256", "extreme-summitstack-512",
    "other",
]

CONSOLE_PORT_TYPES = [
    "de-9", "db-25", "rj-11", "rj-12", "rj-45", "mini-din-8",
    "usb-a", "usb-b", "usb-c", "usb-mini-a", "usb-mini-b",
    "usb-micro-a", "usb-micro-b", "usb-micro-ab", "other",
]

# console-server ports share the console-port vocabulary in the upstream schema
CONSOLE_SERVER_PORT_TYPES = list(CONSOLE_PORT_TYPES)

POWER_PORT_TYPES = [
    "iec-60320-c6", "iec-60320-c8", "iec-60320-c14", "iec-60320-c16",
    "iec-60320-c20", "iec-60320-c22", "iec-60309-p-n-e-4h",
    "iec-60309-p-n-e-6h", "iec-60309-p-n-e-9h", "iec-60309-2p-e-4h",
    "iec-60309-2p-e-6h", "iec-60309-2p-e-9h", "iec-60309-3p-e-4h",
    "iec-60309-3p-e-6h", "iec-60309-3p-e-9h", "iec-60309-3p-n-e-4h",
    "iec-60309-3p-n-e-6h", "iec-60309-3p-n-e-9h", "iec-60906-1",
    "nbr-14136-10a", "nbr-14136-20a",
    "nema-1-15p", "nema-5-15p", "nema-5-20p", "nema-5-30p", "nema-5-50p",
    "nema-6-15p", "nema-6-20p", "nema-6-30p", "nema-6-50p", "nema-10-30p",
    "nema-10-50p", "nema-14-20p", "nema-14-30p", "nema-14-50p", "nema-14-60p",
    "nema-15-15p", "nema-15-20p", "nema-15-30p", "nema-15-50p", "nema-15-60p",
    "nema-l1-15p", "nema-l5-15p", "nema-l5-20p", "nema-l5-30p", "nema-l5-50p",
    "nema-l6-15p", "nema-l6-20p", "nema-l6-30p", "nema-l6-50p", "nema-l10-30p",
    "nema-l14-20p", "nema-l14-30p", "nema-l14-50p", "nema-l14-60p",
    "nema-l15-20p", "nema-l15-30p", "nema-l15-50p",
    "nema-l15-60p", "nema-l21-20p", "nema-l21-30p", "nema-l22-30p",
    "cs6361c", "cs6365c", "cs8165c", "cs8265c", "cs8365c", "cs8465c",
    "ita-c", "ita-e", "ita-f", "ita-ef", "ita-g", "ita-h", "ita-i", "ita-j",
    "ita-k", "ita-l", "ita-m", "ita-n", "ita-o",
    "usb-a", "usb-b", "usb-c", "usb-mini-a", "usb-mini-b", "usb-micro-a",
    "usb-micro-b", "usb-micro-ab", "usb-3-b", "usb-3-micro-b",
    "dc-terminal", "saf-d-grid", "neutrik-powercon-20", "neutrik-powercon-32",
    "neutrik-powercon-true1", "neutrik-powercon-true1-top",
    "ubiquiti-smartpower", "hardwired", "other",
]

POWER_OUTLET_TYPES = [
    "iec-60320-c5", "iec-60320-c7", "iec-60320-c13", "iec-60320-c15",
    "iec-60320-c19", "iec-60320-c21", "iec-60309-p-n-e-4h",
    "iec-60309-p-n-e-6h", "iec-60309-p-n-e-9h", "iec-60309-2p-e-4h",
    "iec-60309-2p-e-6h", "iec-60309-2p-e-9h", "iec-60309-3p-e-4h",
    "iec-60309-3p-e-6h", "iec-60309-3p-e-9h", "iec-60309-3p-n-e-4h",
    "iec-60309-3p-n-e-6h", "iec-60309-3p-n-e-9h", "iec-60906-1",
    "nbr-14136-10a", "nbr-14136-20a",
    "nema-1-15r", "nema-5-15r", "nema-5-20r", "nema-5-30r", "nema-5-50r",
    "nema-6-15r", "nema-6-20r", "nema-6-30r", "nema-6-50r", "nema-10-30r",
    "nema-10-50r", "nema-14-20r", "nema-14-30r", "nema-14-50r", "nema-14-60r",
    "nema-15-15r", "nema-15-20r", "nema-15-30r", "nema-15-50r", "nema-15-60r",
    "nema-l1-15r", "nema-l5-15r", "nema-l5-20r", "nema-l5-30r", "nema-l5-50r",
    "nema-l6-15r", "nema-l6-20r", "nema-l6-30r", "nema-l6-50r", "nema-l10-30r",
    "nema-l14-20r", "nema-l14-30r", "nema-l14-50r", "nema-l14-60r",
    "nema-l15-20r", "nema-l15-30r", "nema-l15-50r", "nema-l15-60r",
    "nema-l21-20r", "nema-l21-30r", "nema-l22-30r",
    "CS6360C", "CS6364C", "CS8164C", "CS8264C", "CS8364C", "CS8464C",
    "ita-e", "ita-f", "ita-g", "ita-h", "ita-i", "ita-j", "ita-k", "ita-l",
    "ita-m", "ita-n", "ita-o", "ita-multistandard",
    "usb-a", "usb-micro-b", "usb-c",
    "dc-terminal", "hdot-cx", "saf-d-grid", "neutrik-powercon-20a",
    "neutrik-powercon-32a", "neutrik-powercon-true1",
    "neutrik-powercon-true1-top", "ubiquiti-smartpower", "hardwired", "other",
]

# front and rear ports share the same pass-through connector vocabulary
PASSTHROUGH_PORT_TYPES = [
    "8p8c", "8p6c", "8p4c", "8p2c", "6p6c", "6p4c", "6p2c", "4p4c", "4p2c",
    "gg45", "tera-4p", "tera-2p", "tera-1p", "110-punch", "bnc", "f", "n",
    "mrj21", "fc", "lc", "lc-pc", "lc-upc", "lc-apc", "lsh", "lsh-pc",
    "lsh-upc", "lsh-apc", "lx5", "lx5-pc", "lx5-upc", "lx5-apc", "mpo",
    "mtrj", "sc", "sc-pc", "sc-upc", "sc-apc", "st", "cs", "sn", "sma-905",
    "sma-906", "urm-p2", "urm-p4", "urm-p8", "splice", "other",
]

POE_MODES = ["pd", "pse"]
POE_TYPES = [
    "type1-ieee802.3af", "type2-ieee802.3at", "type3-ieee802.3bt",
    "type4-ieee802.3bt", "passive-24v-2pair", "passive-24v-4pair",
    "passive-48v-2pair", "passive-48v-4pair",
]
WEIGHT_UNITS = ["kg", "g", "lb", "oz"]
AIRFLOW = [
    "front-to-rear", "rear-to-front", "left-to-right", "right-to-left",
    "side-to-rear", "passive", "mixed",
]
SUBDEVICE_ROLES = ["parent", "child"]
FEED_LEGS = ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Enum types
# ---------------------------------------------------------------------------
DeviceCategory = _str_enum("DeviceCategory", DEVICE_CATEGORIES)
NetworkOS = _str_enum("NetworkOS", NETWORK_OS)
DeviceRole = _str_enum("DeviceRole", DEVICE_ROLES)
NacConfigDomain = _str_enum("NacConfigDomain", NAC_CONFIG_DOMAINS)
SdwanPersonality = _str_enum("SdwanPersonality", SDWAN_PERSONALITIES)
InterfaceType = _str_enum("InterfaceType", INTERFACE_TYPES)
ConsolePortType = _str_enum("ConsolePortType", CONSOLE_PORT_TYPES)
ConsoleServerPortType = _str_enum("ConsoleServerPortType", CONSOLE_SERVER_PORT_TYPES)
PowerPortType = _str_enum("PowerPortType", POWER_PORT_TYPES)
PowerOutletType = _str_enum("PowerOutletType", POWER_OUTLET_TYPES)
PassthroughPortType = _str_enum("PassthroughPortType", PASSTHROUGH_PORT_TYPES)
PoEMode = _str_enum("PoEMode", POE_MODES)
PoEType = _str_enum("PoEType", POE_TYPES)
WeightUnit = _str_enum("WeightUnit", WEIGHT_UNITS)
Airflow = _str_enum("Airflow", AIRFLOW)
SubdeviceRole = _str_enum("SubdeviceRole", SUBDEVICE_ROLES)
FeedLeg = _str_enum("FeedLeg", FEED_LEGS)


# ---------------------------------------------------------------------------
# Strict base model
# ---------------------------------------------------------------------------
class StrictModel(BaseModel):
    """Base for every model: reject unknown keys, strip strings, validate writes."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
    )


# ---------------------------------------------------------------------------
# Components (Nautobot devicetype-library compatible)
# ---------------------------------------------------------------------------
class Interface(StrictModel):
    name: str = Field(..., min_length=1)
    type: InterfaceType
    label: Optional[str] = None
    description: Optional[str] = None
    mgmt_only: StrictBool = False
    poe_mode: Optional[PoEMode] = None
    poe_type: Optional[PoEType] = None

    @model_validator(mode="after")
    def _poe_type_requires_pse(self) -> "Interface":
        if self.poe_type is not None and self.poe_mode is None:
            raise ValueError("poe_type requires poe_mode to be set")
        return self


class ConsolePort(StrictModel):
    name: str = Field(..., min_length=1)
    type: ConsolePortType
    label: Optional[str] = None
    description: Optional[str] = None
    poe: StrictBool = False


class ConsoleServerPort(StrictModel):
    name: str = Field(..., min_length=1)
    type: ConsoleServerPortType
    label: Optional[str] = None
    description: Optional[str] = None


class PowerPort(StrictModel):
    name: str = Field(..., min_length=1)
    type: PowerPortType
    label: Optional[str] = None
    description: Optional[str] = None
    maximum_draw: Optional[StrictInt] = Field(None, gt=0, description="Maximum draw (watts)")
    allocated_draw: Optional[StrictInt] = Field(None, gt=0, description="Allocated draw (watts)")

    @model_validator(mode="after")
    def _allocated_le_maximum(self) -> "PowerPort":
        if (
            self.maximum_draw is not None
            and self.allocated_draw is not None
            and self.allocated_draw > self.maximum_draw
        ):
            raise ValueError("allocated_draw cannot exceed maximum_draw")
        return self


class PowerOutlet(StrictModel):
    name: str = Field(..., min_length=1)
    type: PowerOutletType
    label: Optional[str] = None
    description: Optional[str] = None
    power_port: Optional[str] = Field(None, description="Name of the feeding power_port")
    feed_leg: Optional[FeedLeg] = None


class FrontPort(StrictModel):
    name: str = Field(..., min_length=1)
    type: PassthroughPortType
    label: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = Field(None, description="6-digit hex RGB, no '#'")
    rear_port: str = Field(..., description="Name of the mapped rear_port")
    rear_port_position: StrictInt = Field(1, ge=1)

    @field_validator("color")
    @classmethod
    def _valid_hex_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"[0-9a-fA-F]{6}", v):
            raise ValueError("color must be a 6-digit hex RGB value (e.g. 'aa1409')")
        return v.lower() if v else v


class RearPort(StrictModel):
    name: str = Field(..., min_length=1)
    type: PassthroughPortType
    label: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = Field(None, description="6-digit hex RGB, no '#'")
    positions: StrictInt = Field(1, ge=1)
    poe: StrictBool = False

    @field_validator("color")
    @classmethod
    def _valid_hex_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"[0-9a-fA-F]{6}", v):
            raise ValueError("color must be a 6-digit hex RGB value (e.g. 'aa1409')")
        return v.lower() if v else v


class DeviceBay(StrictModel):
    name: str = Field(..., min_length=1)
    label: Optional[str] = None
    description: Optional[str] = None


class ModuleBay(StrictModel):
    name: str = Field(..., min_length=1)
    label: Optional[str] = None
    description: Optional[str] = None
    position: Optional[str] = None


class InventoryItem(StrictModel):
    name: str = Field(..., min_length=1)
    label: Optional[str] = None
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    part_id: Optional[str] = None


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
    """A STIG checklist that applies to this device type."""

    benchmark_id: str = Field(..., min_length=1)
    title: Optional[str] = None
    version: Optional[str] = None


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
        ids = [s.benchmark_id for s in self.applicable_stigs]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate benchmark_id in applicable_stigs")
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
    "SCHEMA_VERSION",
    # enums
    "DeviceCategory", "NetworkOS", "DeviceRole", "NacConfigDomain",
    "SdwanPersonality", "InterfaceType", "ConsolePortType",
    "ConsoleServerPortType", "PowerPortType", "PowerOutletType",
    "PassthroughPortType", "PoEMode", "PoEType", "WeightUnit", "Airflow",
    "SubdeviceRole", "FeedLeg",
    # models
    "StrictModel", "Interface", "ConsolePort", "ConsoleServerPort",
    "PowerPort", "PowerOutlet", "FrontPort", "RearPort", "DeviceBay",
    "ModuleBay", "InventoryItem", "DeviceImage", "ApplicableStig",
    "BaselineLayers", "SdwanProfile", "NacIntegration", "DeviceDefinition",
    "DeviceDefinitionLibrary",
]
