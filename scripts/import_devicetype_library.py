"""Import every device type from the Nautobot ``devicetype-library`` and validate
it against :class:`DeviceDefinition`.

This is an integration test of the model against real-world data. The upstream
library (https://github.com/nautobot/devicetype-library) is *not* a byte-for-byte
match for our schema, so a thin adapter normalizes each YAML document before
validation:

* Hyphenated component keys (``power-ports``) -> snake_case (``power_ports``).
* Upstream-only keys we don't model (``front_image``, ``rear_image``,
  ``is_powered``) are dropped.
* ``slug`` is synthesized (upstream omits it; Nautobot generates it at import).
* ``category`` / ``platform`` are required by our model but absent upstream, so
  neutral ``"other"`` values are injected — this test exercises the physical and
  component vocabularies, not the identity taxonomy.
* Empty ``subdevice_role: ''`` -> ``None``.

Run::

    python scripts/import_devicetype_library.py /path/to/devicetype-library

Exits non-zero if any file fails validation, printing a summary grouped by the
first validation error location so unsupported enum values surface immediately.

Pass ``--out DIR`` to also persist every device that validates as canonical
JSON, mirroring the upstream vendor directory layout, plus a ``manifest.json``
index. The default output location (``converted/`` at the repo root) is local
and gitignored, so the converted corpus stays on this machine::

    python scripts/import_devicetype_library.py /path/to/devicetype-library --out
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

# Ensure the package is importable when run as a plain script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from device_definition_models import DeviceDefinition  # noqa: E402

# Repo root and the default local (gitignored) destination for converted output.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO_ROOT / "converted"

# Upstream component keys use hyphens; our model uses snake_case.
_KEY_RENAMES = {
    "console-ports": "console_ports",
    "console-server-ports": "console_server_ports",
    "power-ports": "power_ports",
    "power-outlets": "power_outlets",
    "front-ports": "front_ports",
    "rear-ports": "rear_ports",
    "device-bays": "device_bays",
    "module-bays": "module_bays",
    "inventory-items": "inventory_items",
}

# Upstream keys we intentionally do not model.
_DROP_KEYS = {"front_image", "rear_image", "is_powered"}


def slugify(manufacturer: str, model: str) -> str:
    """Build a Nautobot-compatible slug from manufacturer + model."""
    raw = f"{manufacturer}-{model}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or "device"


def adapt(doc: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw upstream YAML document into DeviceDefinition kwargs."""
    out: dict[str, Any] = {}
    for key, value in doc.items():
        if key in _DROP_KEYS:
            continue
        out[_KEY_RENAMES.get(key, key)] = value

    out.setdefault("category", "other")
    out.setdefault("platform", "other")
    if "slug" not in out:
        out["slug"] = slugify(str(doc.get("manufacturer", "")), str(doc.get("model", "")))

    if out.get("subdevice_role") in ("", None):
        out.pop("subdevice_role", None)

    return out


def _first_error_key(exc: ValidationError) -> str:
    """A compact grouping key for the first validation error in *exc*."""
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err["loc"] if not isinstance(p, int))
    return f"{loc or '<root>'}: {err['type']}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "library",
        type=Path,
        help="Path to a cloned nautobot/devicetype-library repository",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=8,
        help="Max example failures to print per error group",
    )
    parser.add_argument(
        "--out",
        type=Path,
        nargs="?",
        const=_DEFAULT_OUT,
        default=None,
        metavar="DIR",
        help=(
            "Persist each validated device as canonical JSON under DIR, "
            f"mirroring the vendor layout (default: {_DEFAULT_OUT} when the "
            "flag is given without a value)."
        ),
    )
    args = parser.parse_args()

    device_types_dir = args.library / "device-types"
    if not device_types_dir.is_dir():
        print(f"error: {device_types_dir} not found", file=sys.stderr)
        return 2

    files = sorted(device_types_dir.rglob("*.yaml")) + sorted(
        device_types_dir.rglob("*.yml")
    )
    if not files:
        print(f"error: no YAML files under {device_types_dir}", file=sys.stderr)
        return 2

    out_dir: Path | None = args.out
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    total = ok = written = 0
    failures: dict[str, list[tuple[str, str]]] = {}
    load_errors: list[tuple[str, str]] = []
    manifest: list[dict[str, str]] = []

    for path in files:
        rel = str(path.relative_to(device_types_dir))
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            load_errors.append((rel, str(e).splitlines()[0]))
            continue
        if not isinstance(raw, dict):
            load_errors.append((rel, "top-level YAML is not a mapping"))
            continue

        total += 1
        try:
            device = DeviceDefinition(**adapt(raw))
            ok += 1
        except ValidationError as exc:
            key = _first_error_key(exc)
            msg = exc.errors()[0]["msg"]
            failures.setdefault(key, []).append((rel, msg))
            continue
        except Exception as exc:  # pragma: no cover - defensive
            failures.setdefault(f"<{type(exc).__name__}>", []).append((rel, str(exc)))
            continue

        if out_dir is not None:
            # Mirror the vendor sub-directory; write canonical JSON per device.
            dest = (out_dir / rel).with_suffix(".json")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(
                device.model_dump_json(indent=2, exclude_none=True) + "\n",
                encoding="utf-8",
            )
            written += 1
            manifest.append(
                {
                    "slug": device.slug,
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "source": rel,
                    "path": str(dest.relative_to(out_dir)),
                }
            )

    if out_dir is not None:
        manifest.sort(key=lambda m: (m["manufacturer"].lower(), m["model"].lower()))
        (out_dir / "manifest.json").write_text(
            json.dumps(
                {"count": len(manifest), "source": str(args.library), "devices": manifest},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    failed = total - ok
    print("=" * 72)
    print(f"Device types validated : {total}")
    print(f"  passed               : {ok}")
    print(f"  failed               : {failed}")
    if out_dir is not None:
        print(f"  written to {out_dir} : {written} (+ manifest.json)")
    if load_errors:
        print(f"YAML load errors       : {len(load_errors)}")
    print("=" * 72)

    if failures:
        print("\nFailures grouped by first validation error:\n")
        for key in sorted(failures, key=lambda k: len(failures[k]), reverse=True):
            items = failures[key]
            print(f"[{len(items):>4}]  {key}")
            for rel, msg in items[: args.max_examples]:
                print(f"           - {rel}\n             {msg}")
            if len(items) > args.max_examples:
                print(f"           ... and {len(items) - args.max_examples} more")
            print()

    if load_errors:
        print("YAML load errors:")
        for rel, msg in load_errors[: args.max_examples]:
            print(f"  - {rel}: {msg}")

    return 0 if failed == 0 and not load_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
