"""Vocabularies and enum types for reusable device definitions.

The module-level value lists are the auditable source of truth; the enums are
derived from them. Onboarding a new interface/port type or device category is a
one-line change here.

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

from network_models._enum import _str_enum

SCHEMA_VERSION = "1.0"


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


__all__ = [
    "SCHEMA_VERSION",
    # value lists
    "DEVICE_CATEGORIES", "NETWORK_OS", "DEVICE_ROLES", "NAC_CONFIG_DOMAINS",
    "SDWAN_PERSONALITIES", "INTERFACE_TYPES", "CONSOLE_PORT_TYPES",
    "CONSOLE_SERVER_PORT_TYPES", "POWER_PORT_TYPES", "POWER_OUTLET_TYPES",
    "PASSTHROUGH_PORT_TYPES", "POE_MODES", "POE_TYPES", "WEIGHT_UNITS",
    "AIRFLOW", "SUBDEVICE_ROLES", "FEED_LEGS",
    # enums
    "DeviceCategory", "NetworkOS", "DeviceRole", "NacConfigDomain",
    "SdwanPersonality", "InterfaceType", "ConsolePortType",
    "ConsoleServerPortType", "PowerPortType", "PowerOutletType",
    "PassthroughPortType", "PoEMode", "PoEType", "WeightUnit", "Airflow",
    "SubdeviceRole", "FeedLeg",
]
