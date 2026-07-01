"""Vocabularies for the STIG catalog domain.

Values mirror the DISA XCCDF benchmark content so the importer can map fields
verbatim. ``severity`` uses the XCCDF ``@severity`` attribute values (which map to
the familiar CAT I/II/III categories).
"""

from __future__ import annotations

from network_models._enum import _str_enum

STIG_SCHEMA_VERSION = "0.1-draft"

# XCCDF rule @severity -> DISA CAT level:
#   high = CAT I, medium = CAT II, low = CAT III. "unknown" is the XCCDF default.
RULE_SEVERITIES = ["high", "medium", "low", "unknown"]

# CAT category labels (derived view / display), kept as a parallel vocabulary.
SEVERITY_TO_CAT = {"high": "CAT I", "medium": "CAT II", "low": "CAT III"}

RuleSeverity = _str_enum("RuleSeverity", RULE_SEVERITIES)


__all__ = [
    "STIG_SCHEMA_VERSION",
    "RULE_SEVERITIES",
    "SEVERITY_TO_CAT",
    "RuleSeverity",
]
