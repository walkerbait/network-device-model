# Product

`network-device-model` provides strict, portable **Pydantic v2** data models for
network **device definitions** and deployed **systems**. These are the
schema-enforced building blocks used when generating configuration for a device
or system.

## Two core domains

- **Device definition** — a reusable device *type* (e.g. "Cisco Catalyst
  9300-48P"): identity, physical attributes, ports/interfaces, applicable STIGs,
  baseline layers, and Cisco Network-as-Code integration. Distinct from a device
  *instance* (a specific unit with hostname and management IP).
- **System** — a concrete deployment: enclaves (security zones), the components
  (device instances) within them, and the Layer-2 connections between them.

## Design principles

- **Strict enforcement.** Every model forbids unknown keys, strips whitespace,
  and validates on assignment. Constrained fields are enums whose values come
  *verbatim* from authoritative upstream schemas — out-of-model values raise
  `ValidationError` rather than passing silently.
- **Portable.** Depends only on `pydantic>=2.5` and the standard library. No
  application imports, so it can be vendored into a consuming repo or hosted as
  its own package.
- **Open to extension.** Enum value lists are module-level constants (the
  auditable source of truth). Adding an interface/port type or device category
  is a one-line change; most vocabularies keep an `"other"` escape hatch.

## Sources of truth

- Interface/port `type` enums, PoE, airflow, weight, subdevice role, physical
  attributes → Nautobot `devicetype-library`.
- Device groups, configuration domains, SD-WAN personalities → Cisco Network as
  Code.
