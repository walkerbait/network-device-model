# network-models

Strict, portable **Pydantic v2** data models for network **device definitions**
and deployed **systems** — the schema-enforced building blocks selected when
generating configs for a system or device.

A *device definition* describes a reusable device **type** (e.g. "Cisco Catalyst
9300-48P") — identity, physical attributes, ports/interfaces, applicable STIGs,
baseline layers, and Cisco Network-as-Code integration — as distinct from a
concrete device **instance** (a specific unit with a hostname and management IP).
A *system* describes a concrete deployment: enclaves (security zones), the
components (device instances) in them, and the Layer-2 connections between them.

## Why

- **Strict enforcement.** Every model forbids unknown keys, strips whitespace,
  and validates on assignment. Constrained fields are enums whose values come
  *verbatim* from the authoritative upstream schemas, so an out-of-model value
  raises `ValidationError` instead of silently passing.
- **Portable.** Depends only on `pydantic>=2.5` and the standard library — no
  imports from any application — so it can be vendored in a consuming repo or
  hosted as its own shared package/repository.
- **Open to extension.** Enum value lists are module-level constants (the
  auditable source of truth); adding an interface/port type or device category
  is a one-line change, and most vocabularies keep an `"other"` escape hatch.

## Sources of truth

| Concern | Source |
| --- | --- |
| Interface & port `type` enums, PoE, airflow, weight, subdevice role, physical attrs | [Nautobot `devicetype-library`](https://github.com/nautobot/devicetype-library) |
| Device groups, configuration domains, SD-WAN personalities | [Cisco Network as Code](https://netascode.cisco.com/docs/data_models/) |

## Usage

```python
from network_models import DeviceDefinition, DeviceDefinitionLibrary

d = DeviceDefinition(
    manufacturer="Cisco",
    model="Catalyst 9300-48P",
    slug="cisco-catalyst-9300-48p",
    category="switch",
    platform="cisco-ios-xe",
    software_version="17.9.4",
    role="access",
    u_height=1.0,
    interfaces=[
        {"name": "GigabitEthernet1/0/1", "type": "1000base-t"},
        {"name": "GigabitEthernet0/0", "type": "1000base-t", "mgmt_only": True},
    ],
    applicable_stigs=[
        {"benchmark_id": "CISCO_IOS_XE_SW_NDM", "version": "V2R9"},
    ],
    baseline_layers={"common": "ios-xe-common-v2.1", "role": "switch-baseline-v1.5"},
    nac={"config_domains": ["system", "aaa", "interfaces"], "device_groups": ["ACCESS_SWITCHES"]},
)

library = DeviceDefinitionLibrary(definitions=[d])
```

Invalid input is rejected:

```python
DeviceDefinition(..., interfaces=[{"name": "x", "type": "10000base-lol"}])  # ValidationError
DeviceDefinition(..., slug="Cisco Catalyst 9300")                            # ValidationError (slug pattern)
DeviceDefinition(..., u_height=1.3)                                          # ValidationError (0.5 increments)
```

## Authorization package (RMF / OpenRMF)

A `System` can carry an optional **authorization package** — the RMF authorization
boundary, inspired by [OpenRMF](https://github.com/Cingulara/openrmf-docs). Where
the `stig` catalog holds rules *as published*, this holds *evaluated results*:

- **`Checklist` / `RuleResult`** — an evaluated CKL (one benchmark against a
  component or the whole system); each rule carries a status (`Open`,
  `NotAFinding`, `Not_Reviewed`, `Not_Applicable`), self-contained severity and
  CCIs, and finding detail.
- **`ControlAssessment`** — NIST 800-53 control status; rule results roll up to
  controls via the package's `cci_control_map` (CCI → control ids).
- **`PoamItem` / `Milestone`** — Plan of Action & Milestones entries, with
  traceability back to the finding they came from.
- **`Categorization`** — FIPS-199 C/I/A impact triad (with derived overall
  high-water), plus authorizing official and ATO dates.

Scores are OpenRMF-style and exposed as serialized `@computed_field`s: a
conservative `compliance_score` (Not_Reviewed counts against) alongside a
`coverage` percent, with `status_counts` / `cat_open_counts` (CAT I/II/III),
per-checklist and system-wide. `AuthorizationPackage` also offers
`rolled_up_control_status()` and a non-mutating `draft_poam_from_findings()`.

```python
from network_models import System, AuthorizationPackage, Checklist

sys = System(
    id="SYS-00428", name="Edge", enclaves=[{"name": "dmz", "classification": "CUI"}],
    components=[{"id": "edge-fw-01", "enclave": "dmz", "category": "firewall"}],
    authorization=AuthorizationPackage(checklists=[Checklist(
        benchmark_id="CISCO_IOS_XE_NDM", component="edge-fw-01",
        results=[{"rule_id": "SV-1_rule", "severity": "high", "status": "Open"}],
    )]),
)
sys.authorization.compliance_score      # -> 0.0
sys.authorization.draft_poam_from_findings()  # -> [PoamItem(...)]
```

### Ingestion (`network_models.io`, opt-in)

Parsers that build these models from files live in a separate, opt-in layer so the
core stays pydantic-only:

```python
from network_models.io import parse_xccdf_results, parse_cci_list

checklist = parse_xccdf_results("results.xml", component="edge-fw-01")  # SCAP/XCCDF result
cci_map = parse_cci_list("U_CCI_List.xml")                              # DISA CCI -> 800-53
```

Install the `io` extra for hardened XML parsing of untrusted content
(`pip install network-device-model[io]`); without it the stdlib parser is used as
an XXE-safe (but not DoS-hardened) fallback.

## Package structure

The package is split into domains under `network_models/`, with shared building
blocks at the top:

```
network_models/
  base.py              # StrictModel (shared strict base)
  _enum.py             # _str_enum helper (verbatim value lists -> str enums)
  device/              # reusable device *type* definitions
    vocab.py           #   value lists + enums (Nautobot + NaC vocab)
    components.py      #   Interface, ConsolePort, PowerPort, ...
    definition.py      #   DeviceDefinition, DeviceDefinitionLibrary, STIG, NaC
  system/              # deployed *system* topology + L2 + authorization package
    vocab.py           #   classification/environment/ATO + L2 + RMF status enums
    l2.py              #   Vlan, VlanRange, TrunkAllowedVlans, Switchport, SpanningTree
    topology.py        #   Enclave, Component, Endpoint, Connection, System
    assessment.py      #   RuleResult, Checklist, ControlAssessment (+ scoring)
    poam.py            #   Milestone, PoamItem
    authorization.py   #   Categorization, AuthorizationPackage
  io/                  # opt-in ingestion (NOT imported by the core)
    scap.py            #   parse_xccdf_results (SCAP/XCCDF result -> Checklist)
    cci.py             #   parse_cci_list (DISA U_CCI_List.xml -> CCI->control map)
    consistency.py     #   check_result_consistency (result vs catalog drift)
```

Everything except the `io` layer is re-exported from the top level
(`from network_models import ...`), and each domain is also importable directly
(`from network_models.system import System`). Ingestion is imported explicitly
(`from network_models.io import parse_xccdf_results`).

## Model map

- **Identity** — `manufacturer`, `model`, `slug`, `part_number`, `category`,
  `platform`, `software_version`, `role`, `description`, `comments`
- **Physical** — `u_height`, `is_full_depth`, `subdevice_role`, `airflow`,
  `weight`, `weight_unit`
- **Components** — `interfaces`, `console_ports`, `console_server_ports`,
  `power_ports`, `power_outlets`, `front_ports`, `rear_ports`, `device_bays`,
  `module_bays`, `inventory_items`
- **Catalog / compliance / config** — `image` (front/rear), `applicable_stigs`,
  `baseline_layers` (common/role/system/program), `nac`
  (config domains, device groups, SD-WAN profile), `tags`
- **Container** — `DeviceDefinitionLibrary` (versioned, unique slugs)

## Test

```bash
python -m pytest tests/test_models.py -q
# or
python tests/test_models.py
```

## Extracting to its own repository

Move the `network_models/` package directory along with `pyproject.toml` and
`README.md` into a new repo. No code changes are required — the package depends
only on `pydantic>=2.5` and has no dependency on this application.
