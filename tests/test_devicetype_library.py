"""Opt-in integration test: validate the model against the real Nautobot
``devicetype-library`` (https://github.com/nautobot/devicetype-library).

This test is **skipped by default** because it needs a local checkout of the
(large) upstream repository. To run it, clone the library and point an
environment variable at it::

    git clone --depth 1 https://github.com/nautobot/devicetype-library /tmp/dtl
    DEVICETYPE_LIBRARY=/tmp/dtl python -m pytest tests/test_devicetype_library.py -v

The upstream YAML format is not identical to our schema, so each document is
normalized by :func:`scripts.import_devicetype_library.adapt` before validation.

The test asserts that at least ``MIN_PASS_RATIO`` of the corpus validates. It is
deliberately a ratio rather than "100%" because a small number of upstream files
contain genuine data errors that our strict model *correctly* rejects (e.g. an
interface ``type`` that is invalid under Nautobot's own schema, or a power outlet
that references a non-existent power port). Those known-bad files are enumerated
in :data:`KNOWN_UPSTREAM_DATA_ERRORS` and must always fail; if one starts passing
the model has silently become too lax.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from network_models import DeviceDefinition

# Make the sibling ``scripts`` package importable so the test and the CLI share
# the exact same adapter logic (single source of truth for normalization).
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
from scripts.import_devicetype_library import adapt  # noqa: E402

# Fraction of the corpus that must validate for the suite to pass.
MIN_PASS_RATIO = 0.98

# Upstream files with genuine data errors our strict model *should* reject.
# Keys are paths relative to ``device-types/``; values describe the defect.
KNOWN_UPSTREAM_DATA_ERRORS = {
    "Mellanox/SN2100B.yml": "interface type '40gbase-x-qsfp28' invalid upstream too",
    "HPE/J9805A.yaml": "power_outlet references undefined power_port PS1/PS2/PS3",
}


def _library_root() -> Path | None:
    env = os.environ.get("DEVICETYPE_LIBRARY")
    if not env:
        return None
    root = Path(env).expanduser()
    return root if (root / "device-types").is_dir() else None


_LIBRARY = _library_root()
_SKIP_REASON = (
    "Set DEVICETYPE_LIBRARY to a clone of nautobot/devicetype-library to run "
    "this integration test."
)


def _device_type_files() -> list[Path]:
    root = _LIBRARY / "device-types"
    return sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml"))


@pytest.mark.skipif(_LIBRARY is None, reason=_SKIP_REASON)
def test_devicetype_library_pass_ratio():
    """The bulk of the real library validates against DeviceDefinition."""
    files = _device_type_files()
    assert files, "no device-type YAML files found in the library checkout"

    root = _LIBRARY / "device-types"
    total = ok = 0
    failures: list[tuple[str, str]] = []
    for path in files:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            continue
        total += 1
        try:
            DeviceDefinition(**adapt(raw))
            ok += 1
        except ValidationError as exc:
            rel = str(path.relative_to(root))
            failures.append((rel, exc.errors()[0]["msg"]))

    ratio = ok / total if total else 0.0
    detail = "\n".join(f"  {rel}: {msg}" for rel, msg in failures[:25])
    assert ratio >= MIN_PASS_RATIO, (
        f"only {ok}/{total} ({ratio:.1%}) validated; "
        f"expected >= {MIN_PASS_RATIO:.0%}.\nSample failures:\n{detail}"
    )


@pytest.mark.skipif(_LIBRARY is None, reason=_SKIP_REASON)
@pytest.mark.parametrize("rel", sorted(KNOWN_UPSTREAM_DATA_ERRORS))
def test_known_bad_files_are_rejected(rel):
    """Files with real upstream data defects must keep failing validation.

    Guards against the model becoming too permissive: if one of these starts
    passing, either upstream fixed the data (update this list) or the schema
    lost strictness (a regression).
    """
    path = _LIBRARY / "device-types" / rel
    if not path.is_file():
        pytest.skip(f"{rel} no longer present upstream")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        DeviceDefinition(**adapt(raw))
