"""Self-test for the device-definition models.

Runnable as a script (``python -m pytest tests/test_models.py``)
or under pytest. Proves that a well-formed definition validates and that a
representative set of malformed inputs are rejected by the strict schema.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from network_models import (
    DeviceDefinition,
    DeviceDefinitionLibrary,
    InterfaceType,
)
from network_models.device.vocab import INTERFACE_TYPES

VALID = {
    "manufacturer": "Cisco",
    "model": "Catalyst 9300-48P",
    "slug": "cisco-catalyst-9300-48p",
    "part_number": "C9300-48P",
    "category": "switch",
    "platform": "cisco-ios-xe",
    "software_version": "17.9.4",
    "role": "access",
    "u_height": 1.0,
    "is_full_depth": True,
    "weight": 8.6,
    "weight_unit": "kg",
    "interfaces": [
        {"name": "GigabitEthernet1/0/1", "type": "1000base-t", "description": "Uplink"},
        {"name": "GigabitEthernet0/0", "type": "1000base-t", "mgmt_only": True},
        {"name": "TenGigabitEthernet1/1/1", "type": "10gbase-x-sfpp"},
    ],
    "console_ports": [{"name": "Console", "type": "rj-45"}],
    "power_ports": [{"name": "PSU1", "type": "iec-60320-c14", "maximum_draw": 715}],
    "rear_ports": [{"name": "R1", "type": "8p8c", "positions": 2}],
    "front_ports": [
        {"name": "F1", "type": "8p8c", "rear_port": "R1", "rear_port_position": 1}
    ],
    "applicable_stigs": [
        {"benchmark_id": "CISCO_IOS_XE_SW_NDM", "title": "Cisco IOS XE Switch NDM STIG"},
        {"benchmark_id": "CISCO_IOS_XE_SW_L2S"},
    ],
    "baseline_layers": {"common": "ios-xe-common-v2.1", "role": "switch-baseline-v1.5"},
    "nac": {
        "config_domains": ["system", "aaa", "interfaces", "routing", "security"],
        "device_groups": ["ACCESS_SWITCHES"],
    },
}


def test_valid_definition():
    d = DeviceDefinition(**VALID)
    assert d.slug == "cisco-catalyst-9300-48p"
    assert d.interfaces[0].type == InterfaceType("1000base-t")
    assert len(d.applicable_stigs) == 2


def test_library_roundtrip():
    lib = DeviceDefinitionLibrary(definitions=[DeviceDefinition(**VALID)])
    dumped = lib.model_dump(mode="json")
    reloaded = DeviceDefinitionLibrary.model_validate(dumped)
    assert reloaded.definitions[0].model == "Catalyst 9300-48P"


def test_enum_renders_value_not_repr():
    """Regression: str()/format()/f-strings must emit the value (config templating)."""
    t = InterfaceType("1000base-t")
    assert str(t) == "1000base-t"
    assert format(t, "") == "1000base-t"
    assert f"{t}" == "1000base-t"
    assert "%s" % t == "1000base-t"
    i = DeviceDefinition(**VALID).interfaces[2]
    assert f"interface {i.name} media {i.type}".endswith("10gbase-x-sfpp")


def test_50g_sfp28_accepted():
    assert InterfaceType("50gbase-x-sfp28") in list(InterfaceType)


def test_multiple_stigs_supported():
    """A device may carry many distinct STIGs; all are preserved in order."""
    stigs = [
        {"benchmark_id": "CISCO_IOS_XE_SW_NDM", "title": "NDM STIG"},
        {"benchmark_id": "CISCO_IOS_XE_SW_L2S"},
        {"benchmark_id": "CISCO_IOS_XE_SW_RTR"},
        {"benchmark_id": "APP_GENERAL"},
    ]
    d = DeviceDefinition(**{**VALID, "applicable_stigs": stigs})
    assert len(d.applicable_stigs) == 4
    assert [s.benchmark_id for s in d.applicable_stigs] == [s["benchmark_id"] for s in stigs]


def test_multiple_stigs_survive_roundtrip():
    """Multiple STIGs survive a JSON dump/reload without loss or reordering."""
    d = DeviceDefinition(**VALID)
    reloaded = DeviceDefinition.model_validate(d.model_dump(mode="json"))
    assert [s.benchmark_id for s in reloaded.applicable_stigs] == [
        s.benchmark_id for s in d.applicable_stigs
    ]


def test_duplicate_stig_benchmark_id_rejected():
    """Duplicate benchmark_id alone is rejected (version removed from device type)."""
    with pytest.raises(ValidationError):
        DeviceDefinition(**{**VALID, "applicable_stigs": [
            {"benchmark_id": "DUP"},
            {"benchmark_id": "DUP"},
        ]})


def test_same_benchmark_id_always_rejected():
    """Same benchmark_id is now always rejected (version is no longer a differentiator)."""
    with pytest.raises(ValidationError):
        DeviceDefinition(**{**VALID, "applicable_stigs": [
            {"benchmark_id": "CISCO_IOS_XE_SW_NDM"},
            {"benchmark_id": "CISCO_IOS_XE_SW_NDM"},
        ]})


def test_validate_against_catalog_standalone():
    """DeviceDefinition validates standalone with no catalog (Req 9.1)."""
    d = DeviceDefinition(**VALID)
    # No catalog — construction succeeds regardless of applicable_stigs content
    assert d.applicable_stigs[0].benchmark_id == "CISCO_IOS_XE_SW_NDM"


def test_validate_against_catalog_all_resolve():
    """validate_against_catalog passes when all benchmark_ids resolve (Req 9.2)."""
    from network_models import StigCatalog, Stig

    d = DeviceDefinition(**VALID)
    catalog = StigCatalog(
        catalog_version="test",
        stigs=[
            Stig(
                benchmark_id="CISCO_IOS_XE_SW_NDM",
                title="NDM STIG",
                version="1",
                type="stig",
                source_file="test.zip",
            ),
            Stig(
                benchmark_id="CISCO_IOS_XE_SW_L2S",
                title="L2S STIG",
                version="1",
                type="stig",
                source_file="test.zip",
            ),
        ],
    )
    result = d.validate_against_catalog(catalog)
    assert result is d  # returns self for chaining


def test_validate_against_catalog_raises_on_missing():
    """validate_against_catalog raises identifying unresolved ids (Req 9.3)."""
    from network_models import StigCatalog, Stig

    d = DeviceDefinition(**VALID)
    # Catalog only has one of the two benchmark_ids in VALID
    catalog = StigCatalog(
        catalog_version="test",
        stigs=[
            Stig(
                benchmark_id="CISCO_IOS_XE_SW_NDM",
                title="NDM STIG",
                version="1",
                type="stig",
                source_file="test.zip",
            ),
        ],
    )
    with pytest.raises(ValueError, match="CISCO_IOS_XE_SW_L2S"):
        d.validate_against_catalog(catalog)


REJECTIONS = [
    ("unknown interface type", {**VALID, "interfaces": [{"name": "x", "type": "10000base-lol"}]}),
    ("extra/unknown key", {**VALID, "colour": "blue"}),
    ("bad slug", {**VALID, "slug": "Cisco Catalyst 9300"}),
    ("u_height not 0.5 multiple", {**VALID, "u_height": 1.3}),
    ("weight without unit", {**VALID, "weight": 5.0, "weight_unit": None}),
    ("front_port dangling rear_port", {**VALID, "front_ports": [{"name": "F1", "type": "8p8c", "rear_port": "NOPE"}]}),
    ("duplicate interface name", {**VALID, "interfaces": [
        {"name": "dup", "type": "1000base-t"}, {"name": "dup", "type": "1000base-t"}]}),
    ("bad category", {**VALID, "category": "toaster"}),
    ("negative power draw", {**VALID, "power_ports": [{"name": "P", "type": "iec-60320-c14", "maximum_draw": -1}]}),
    ("phantom power-port type nema-l15-15p", {**VALID, "power_ports": [{"name": "P", "type": "nema-l15-15p"}]}),
    ("non-finite u_height", {**VALID, "u_height": float("inf")}),
    ("bool coerced into maximum_draw", {**VALID, "power_ports": [{"name": "P", "type": "iec-60320-c14", "maximum_draw": True}]}),
    ("degenerate slug", {**VALID, "slug": "---"}),
    ("front-port position collision", {**VALID,
        "rear_ports": [{"name": "R1", "type": "8p8c", "positions": 2}],
        "front_ports": [
            {"name": "F1", "type": "8p8c", "rear_port": "R1", "rear_port_position": 1},
            {"name": "F2", "type": "8p8c", "rear_port": "R1", "rear_port_position": 1},
        ]}),
    ("duplicate applicable STIG", {**VALID, "applicable_stigs": [{"benchmark_id": "X"}, {"benchmark_id": "X"}]}),
    ("empty device image", {**VALID, "image": {}}),
]


@pytest.mark.parametrize("label,payload", REJECTIONS, ids=[r[0] for r in REJECTIONS])
def test_rejections(label, payload):
    with pytest.raises(ValidationError):
        DeviceDefinition(**payload)


if __name__ == "__main__":
    test_valid_definition()
    test_library_roundtrip()
    print(f"OK: valid definition accepted; {len(INTERFACE_TYPES)} interface types enumerated")
    failures = 0
    for label, payload in REJECTIONS:
        try:
            DeviceDefinition(**payload)
            print(f"  FAIL (accepted, should reject): {label}")
            failures += 1
        except ValidationError:
            print(f"  OK rejected: {label}")
    if failures:
        raise SystemExit(f"{failures} rejection case(s) did not raise")
    print("All rejection cases correctly raised ValidationError.")
