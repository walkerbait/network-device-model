"""Optional drift check between evaluated results and the reference catalog.

Because :class:`~network_models.system.assessment.RuleResult` is self-contained
(it embeds ``severity`` / ``ccis`` from the wire), those values can drift from the
published :class:`~network_models.stig.catalog.StigCatalog`. This helper surfaces
such mismatches; it is advisory (returns a list of messages) and never raises.
"""

from __future__ import annotations

from network_models.stig.catalog import StigCatalog
from network_models.system.assessment import Checklist


def check_result_consistency(checklist: Checklist, catalog: StigCatalog) -> list[str]:
    """Return human-readable warnings where ``checklist`` disagrees with ``catalog``.

    Matches rules by ``rule_id``. Reports rules absent from the catalog and any
    severity / CCI-set differences. An empty list means no drift was detected.
    """
    # Index catalog rules by rule_id across every STIG in the catalog.
    catalog_rules = {
        rule.rule_id: rule for stig in catalog.stigs for rule in stig.rules
    }
    warnings: list[str] = []
    for result in checklist.results:
        ref = catalog_rules.get(result.rule_id)
        if ref is None:
            warnings.append(f"{result.rule_id}: not found in catalog")
            continue
        if str(result.severity) != str(ref.severity):
            warnings.append(
                f"{result.rule_id}: severity {result.severity} != catalog {ref.severity}"
            )
        if set(result.ccis) != set(ref.ccis):
            warnings.append(
                f"{result.rule_id}: CCIs {sorted(result.ccis)} != catalog {sorted(ref.ccis)}"
            )
    return warnings


__all__ = ["check_result_consistency"]
