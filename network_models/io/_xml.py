"""XML parsing helper for the opt-in I/O layer.

Prefers ``defusedxml`` (hardened against XXE, entity-expansion / billion-laughs,
and quadratic-blowup DoS) and falls back to the stdlib ``xml.etree.ElementTree``.

The stdlib fallback does *not* expand external entities (so it is XXE-safe), but
it is **not** hardened against entity-expansion DoS. Install the ``io`` extra
(``pip install network-device-model[io]``) to pull in ``defusedxml`` and get full
protection when parsing untrusted SCAP/CCI content.
"""

from __future__ import annotations

try:  # pragma: no cover - exercised via install-extra choice, not branch logic
    from defusedxml.ElementTree import fromstring as _fromstring  # type: ignore

    HARDENED = True
except ImportError:  # pragma: no cover
    from xml.etree.ElementTree import fromstring as _fromstring

    HARDENED = False


def local_name(tag: str) -> str:
    """Return an element's local name, dropping any ``{namespace}`` prefix."""
    return tag.rsplit("}", 1)[-1]


def parse_xml(data: bytes):
    """Parse XML bytes into an ElementTree ``Element`` using the safest backend."""
    return _fromstring(data)


__all__ = ["parse_xml", "local_name", "HARDENED"]
