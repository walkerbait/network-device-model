"""Parse SCAP / XCCDF *result* documents into evaluated :class:`Checklist`s.

This is the ingestion side of the authorization package: an XCCDF ``TestResult``
(what a SCAP tool emits after scanning) is turned into a :class:`Checklist` of
:class:`RuleResult`s, mapping each ``<result>`` through
:data:`~network_models.system.vocab.XCCDF_RESULT_TO_STATUS` to a CKL status.

Version-tolerant: elements are matched by *local* tag name, so XCCDF 1.1 and 1.2
namespaces both work. When the source embeds the benchmark ``<Group>``/``<Rule>``
tree, each result's Vuln ID (``group_id``) and rule severity are resolved from
it; a bare results-only document leaves ``group_id`` as ``None`` (``rule_id`` is
always the reliable key).
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Union

from network_models.io._xml import local_name, parse_xml
from network_models.stig.vocab import RULE_SEVERITIES
from network_models.system.assessment import Checklist, RuleResult
from network_models.system.vocab import XCCDF_RESULT_TO_STATUS

_CCI_HINT = "cci"


def _iter_local(elem, name: str):
    """Yield all descendants (and self) whose local tag name is ``name``."""
    for e in elem.iter():
        if local_name(e.tag) == name:
            yield e


def _first_local(elem, name: str):
    return next(_iter_local(elem, name), None)


def _parse_end_time(test_result) -> Optional[datetime]:
    raw = test_result.get("end-time")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _benchmark_rule_index(root) -> dict[str, tuple[Optional[str], Optional[str]]]:
    """Map rule_id -> (group_id, severity) from an embedded benchmark, if present.

    Walks ``<Group>`` elements (whose ``@id`` is the Vuln ID) and their child
    ``<Rule>`` elements (whose ``@id`` is the Rule ID, carrying ``@severity``).
    """
    index: dict[str, tuple[Optional[str], Optional[str]]] = {}
    for group in _iter_local(root, "Group"):
        group_id = group.get("id")
        for rule in _iter_local(group, "Rule"):
            rule_id = rule.get("id")
            if rule_id:
                index[rule_id] = (group_id, rule.get("severity"))
    return index


def _clean_severity(raw: Optional[str]) -> str:
    return raw if raw in RULE_SEVERITIES else "unknown"


def _extract_ccis(rule_result) -> list[str]:
    ccis: list[str] = []
    for ident in _iter_local(rule_result, "ident"):
        system = (ident.get("system") or "").lower()
        text = (ident.text or "").strip()
        if _CCI_HINT in system and text and text not in ccis:
            ccis.append(text)
    return ccis


def parse_xccdf_results_bytes(data: bytes, *, component: Optional[str] = None) -> Checklist:
    """Parse raw XCCDF result XML bytes into a :class:`Checklist`."""
    root = parse_xml(data)
    test_result = root if local_name(root.tag) == "TestResult" else _first_local(root, "TestResult")
    if test_result is None:
        raise ValueError("no XCCDF <TestResult> element found in document")

    rule_index = _benchmark_rule_index(root)

    # Benchmark identity: prefer the TestResult's <benchmark> ref, else a wrapping
    # <Benchmark> element's id.
    benchmark_el = _first_local(test_result, "benchmark")
    benchmark_id = None
    if benchmark_el is not None:
        benchmark_id = benchmark_el.get("id") or benchmark_el.get("href")
    if not benchmark_id:
        bench = root if local_name(root.tag) == "Benchmark" else _first_local(root, "Benchmark")
        if bench is not None:
            benchmark_id = bench.get("id")
    benchmark_id = benchmark_id or "UNKNOWN"

    title_el = _first_local(test_result, "title")
    title = title_el.text.strip() if title_el is not None and title_el.text else None
    version = test_result.get("version")

    results: list[RuleResult] = []
    for rr in _iter_local(test_result, "rule-result"):
        rule_id = rr.get("idref")
        if not rule_id:
            continue
        result_el = _first_local(rr, "result")
        result_text = (result_el.text or "").strip().lower() if result_el is not None else ""
        status = XCCDF_RESULT_TO_STATUS.get(result_text, "Not_Reviewed")

        group_id, indexed_sev = rule_index.get(rule_id, (None, None))
        severity = _clean_severity(rr.get("severity") or indexed_sev)

        results.append(
            RuleResult(
                group_id=group_id,
                rule_id=rule_id,
                severity=severity,
                status=status,
                ccis=_extract_ccis(rr),
            )
        )

    return Checklist(
        benchmark_id=benchmark_id,
        title=title,
        version=version,
        component=component,
        source="SCAP",
        evaluated_at=_parse_end_time(test_result),
        results=results,
    )


def parse_xccdf_results_file(
    path: Union[str, os.PathLike], *, component: Optional[str] = None
) -> Checklist:
    """Read and parse an XCCDF result file into a :class:`Checklist`."""
    with open(path, "rb") as fh:
        return parse_xccdf_results_bytes(fh.read(), component=component)


def parse_xccdf_results(
    source: Union[str, bytes, os.PathLike], *, component: Optional[str] = None
) -> Checklist:
    """Parse XCCDF results from raw ``bytes`` or a file path (``str`` / ``PathLike``).

    ``bytes`` are treated as the raw document; ``str`` / ``PathLike`` as a path.
    """
    if isinstance(source, (bytes, bytearray)):
        return parse_xccdf_results_bytes(bytes(source), component=component)
    return parse_xccdf_results_file(source, component=component)


__all__ = [
    "parse_xccdf_results",
    "parse_xccdf_results_bytes",
    "parse_xccdf_results_file",
]
