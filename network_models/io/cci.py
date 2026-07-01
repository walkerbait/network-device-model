"""Build a CCI -> NIST 800-53 control map from DISA's ``U_CCI_List.xml``.

The map produced here is what
:attr:`~network_models.system.authorization.AuthorizationPackage.cci_control_map`
expects, so an authorization package can roll evaluated rule results (which carry
CCIs) up to 800-53 controls without embedding the ~3000-entry CCI catalog in the
library core.
"""

from __future__ import annotations

import os
import re
from typing import Union

from network_models.io._xml import local_name, parse_xml

# Leading control token in a reference index, e.g. "AC-2", "AC-2 (1)" -> AC-2(1).
_CONTROL_RE = re.compile(r"^\s*([A-Z]{2}-\d+)(?:\s*\((\d+)\))?")


def _control_id(index: str) -> Union[str, None]:
    m = _CONTROL_RE.match(index or "")
    if not m:
        return None
    base, enhancement = m.group(1), m.group(2)
    return f"{base}({enhancement})" if enhancement else base


def parse_cci_list_bytes(data: bytes) -> dict[str, list[str]]:
    """Parse ``U_CCI_List.xml`` bytes into ``{cci_id: [control_id, ...]}``."""
    root = parse_xml(data)
    mapping: dict[str, list[str]] = {}
    for item in root.iter():
        if local_name(item.tag) != "cci_item":
            continue
        cci_id = item.get("id")
        if not cci_id:
            continue
        controls: list[str] = []
        references = [e for e in item.iter() if local_name(e.tag) == "reference"]
        # Prefer 800-53 references; fall back to all if none are labelled as such.
        sp = [r for r in references if "800-53" in (r.get("title") or "")]
        for ref in sp or references:
            control = _control_id(ref.get("index") or "")
            if control and control not in controls:
                controls.append(control)
        if controls:
            mapping[cci_id] = controls
    return mapping


def parse_cci_list(source: Union[str, bytes, os.PathLike]) -> dict[str, list[str]]:
    """Parse a CCI list from raw ``bytes`` or a file path (``str`` / ``PathLike``)."""
    if isinstance(source, (bytes, bytearray)):
        return parse_cci_list_bytes(bytes(source))
    with open(source, "rb") as fh:
        return parse_cci_list_bytes(fh.read())


__all__ = ["parse_cci_list", "parse_cci_list_bytes"]
