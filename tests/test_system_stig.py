"""Tests for STIG assignment on system components (network_models/system/topology.py).

Covers: StigAssignment default status, closed status vocabulary, uniqueness on
(benchmark_id, version), same benchmark at different versions accepted,
System.validate_stig_assignments (opt-in catalog resolver), and
System.stig_divergences (warn-only divergence report).
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from network_models import (
    DeviceDefinition,
    DeviceDefinitionLibrary,
)
from network_models.stig.catalog import Stig, StigCatalog
from network_models.stig.vocab import ASSIGNMENT_STATUSES, AssignmentStatus
from network_models.system.topology import Component, StigAssignment, System


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_assignment(**overrides) -> dict:
    """Minimal valid StigAssignment dict."""
    defaults = {
        "benchmark_id": "CISCO_IOS_XE_SW_NDM",
        "version": "V5R3",
    }
    defaults.update(overrides)
    return defaults


def _make_component(*, stig_assignments=None, **overrides) -> dict:
    """Minimal valid Component dict."""
    defaults = {
        "id": "edge-fw-01",
        "enclave": "dmz",
        "category": "firewall",
    }
    defaults.update(overrides)
    if stig_assignments is not None:
        defaults["stig_assignments"] = stig_assignments
    return defaults


def _make_system(*, components=None, enclaves=None, **overrides) -> dict:
    """Minimal valid System dict."""
    defaults = {
        "id": "SYS-001",
        "name": "Test System",
        "enclaves": enclaves or [{"name": "dmz", "classification": "CUI"}],
    }
    defaults.update(overrides)
    if components is not None:
        defaults["components"] = components
    return defaults


def _make_catalog(stigs=None) -> StigCatalog:
    """Build a small StigCatalog for resolver tests."""
    return StigCatalog(
        catalog_version="test",
        stigs=[
            Stig(
                benchmark_id=s["benchmark_id"],
                title=s.get("title", "Title"),
                version=s["version"],
                type=s.get("type", "stig"),
                source_file=s.get("source_file", "test.zip"),
            )
            for s in (stigs or [])
        ],
    )


# ---------------------------------------------------------------------------
# Req 10.2 — StigAssignment default status is not_assessed
# ---------------------------------------------------------------------------

class TestStigAssignmentDefaults:
    def test_default_status_is_not_assessed(self):
        """StigAssignment defaults status to 'not_assessed' when not provided."""
        a = StigAssignment(**_make_assignment())
        assert str(a.status) == "not_assessed"

    def test_explicit_status_accepted(self):
        """All valid statuses are accepted when explicitly set."""
        for status in ASSIGNMENT_STATUSES:
            a = StigAssignment(**_make_assignment(status=status))
            assert str(a.status) == status


# ---------------------------------------------------------------------------
# Req 10.6 — Status outside the closed set raises
# ---------------------------------------------------------------------------

class TestStigAssignmentStatusClosed:
    def test_invalid_status_rejected(self):
        """A status value outside the closed vocabulary raises ValidationError."""
        with pytest.raises(ValidationError):
            StigAssignment(**_make_assignment(status="passed"))

    def test_invalid_status_rejected_empty(self):
        """Empty string status raises ValidationError."""
        with pytest.raises(ValidationError):
            StigAssignment(**_make_assignment(status=""))


# ---------------------------------------------------------------------------
# Req 10.4 — Duplicate (benchmark_id, version) on one component raises
# ---------------------------------------------------------------------------

class TestComponentAssignmentUniqueness:
    def test_duplicate_benchmark_version_rejected(self):
        """Duplicate (benchmark_id, version) on one component raises ValidationError."""
        assignments = [
            _make_assignment(benchmark_id="X", version="V1"),
            _make_assignment(benchmark_id="X", version="V1"),
        ]
        with pytest.raises(ValidationError, match="duplicate"):
            Component(**_make_component(stig_assignments=assignments))

    def test_distinct_pairs_accepted(self):
        """Distinct (benchmark_id, version) pairs on one component are accepted."""
        assignments = [
            _make_assignment(benchmark_id="X", version="V1"),
            _make_assignment(benchmark_id="Y", version="V1"),
        ]
        c = Component(**_make_component(stig_assignments=assignments))
        assert len(c.stig_assignments) == 2


# ---------------------------------------------------------------------------
# Req 10.5, 14.6, 14.8 — Same benchmark_id at two different versions accepted
# ---------------------------------------------------------------------------

class TestSameBenchmarkDifferentVersions:
    def test_same_benchmark_different_versions_accepted(self):
        """Same benchmark_id at two different versions on one component is accepted.

        This is the relocated test_same_stig_different_versions_allowed from the
        device layer — at the component layer, version pinning distinguishes entries.
        """
        assignments = [
            _make_assignment(benchmark_id="CISCO_IOS_XE_SW_NDM", version="V5R2"),
            _make_assignment(benchmark_id="CISCO_IOS_XE_SW_NDM", version="V5R3"),
        ]
        c = Component(**_make_component(stig_assignments=assignments))
        assert len(c.stig_assignments) == 2
        assert c.stig_assignments[0].version == "V5R2"
        assert c.stig_assignments[1].version == "V5R3"

    def test_same_benchmark_same_version_rejected(self):
        """Same (benchmark_id, version) pair is rejected (the inverse case)."""
        assignments = [
            _make_assignment(benchmark_id="CISCO_IOS_XE_SW_NDM", version="V5R3"),
            _make_assignment(benchmark_id="CISCO_IOS_XE_SW_NDM", version="V5R3"),
        ]
        with pytest.raises(ValidationError, match="duplicate"):
            Component(**_make_component(stig_assignments=assignments))


# ---------------------------------------------------------------------------
# Req 11.1 — System validates standalone without a catalog
# ---------------------------------------------------------------------------

class TestSystemStandaloneValidation:
    def test_system_validates_without_catalog(self):
        """System constructs successfully without requiring a catalog (Req 11.1)."""
        components = [
            _make_component(
                stig_assignments=[
                    _make_assignment(benchmark_id="ANYTHING", version="V99"),
                ]
            ),
        ]
        sys = System(**_make_system(components=components))
        assert len(sys.components) == 1
        assert len(sys.components[0].stig_assignments) == 1


# ---------------------------------------------------------------------------
# Req 11.2, 11.3 — System.validate_stig_assignments (opt-in resolver)
# ---------------------------------------------------------------------------

class TestValidateStigAssignments:
    def test_passes_when_all_resolve(self):
        """validate_stig_assignments passes when all pins resolve (Req 11.2)."""
        components = [
            _make_component(
                stig_assignments=[
                    _make_assignment(benchmark_id="NDM", version="V1"),
                ]
            ),
        ]
        sys = System(**_make_system(components=components))
        catalog = _make_catalog([
            {"benchmark_id": "NDM", "version": "V1"},
        ])
        result = sys.validate_stig_assignments(catalog)
        assert result is sys  # returns self for chaining

    def test_raises_on_unresolved_pin(self):
        """validate_stig_assignments raises identifying unresolved pin (Req 11.3)."""
        components = [
            _make_component(
                stig_assignments=[
                    _make_assignment(benchmark_id="NDM", version="V1"),
                    _make_assignment(benchmark_id="MISSING", version="V2"),
                ]
            ),
        ]
        sys = System(**_make_system(components=components))
        catalog = _make_catalog([
            {"benchmark_id": "NDM", "version": "V1"},
        ])
        with pytest.raises(ValueError, match="MISSING"):
            sys.validate_stig_assignments(catalog)

    def test_raises_on_wrong_version(self):
        """Correct benchmark_id but wrong version also fails resolution."""
        components = [
            _make_component(
                stig_assignments=[
                    _make_assignment(benchmark_id="NDM", version="V99"),
                ]
            ),
        ]
        sys = System(**_make_system(components=components))
        catalog = _make_catalog([
            {"benchmark_id": "NDM", "version": "V1"},
        ])
        with pytest.raises(ValueError, match="NDM.*V99"):
            sys.validate_stig_assignments(catalog)

    def test_multiple_components_all_resolve(self):
        """Multiple components with multiple assignments all resolve successfully."""
        components = [
            _make_component(
                id="fw-01",
                stig_assignments=[
                    _make_assignment(benchmark_id="NDM", version="V1"),
                ],
            ),
            _make_component(
                id="sw-01",
                stig_assignments=[
                    _make_assignment(benchmark_id="L2S", version="V2"),
                ],
            ),
        ]
        sys = System(**_make_system(components=components))
        catalog = _make_catalog([
            {"benchmark_id": "NDM", "version": "V1"},
            {"benchmark_id": "L2S", "version": "V2"},
        ])
        result = sys.validate_stig_assignments(catalog)
        assert result is sys


# ---------------------------------------------------------------------------
# Req 11.4, 11.5 — System.stig_divergences (warn-only)
# ---------------------------------------------------------------------------

class TestStigDivergences:
    def _make_definition(self, slug, applicable_stigs):
        """Build a minimal DeviceDefinition for divergence tests."""
        return DeviceDefinition(
            manufacturer="Cisco",
            model="Test Device",
            slug=slug,
            category="switch",
            platform="cisco-ios-xe",
            interfaces=[{"name": "Gi0/1", "type": "1000base-t"}],
            applicable_stigs=[
                {"benchmark_id": bid} for bid in applicable_stigs
            ],
        )

    def test_empty_when_all_backed(self):
        """Returns empty list when every assignment is backed by definition (Req 11.5)."""
        defn = self._make_definition("test-switch", ["NDM", "L2S"])
        lib = DeviceDefinitionLibrary(definitions=[defn])

        components = [
            _make_component(
                id="sw-01",
                device_definition="test-switch",
                stig_assignments=[
                    _make_assignment(benchmark_id="NDM", version="V1"),
                    _make_assignment(benchmark_id="L2S", version="V2"),
                ],
            ),
        ]
        sys = System(**_make_system(components=components))
        divergences = sys.stig_divergences(lib)
        assert divergences == []

    def test_returns_undeclared_pairs(self):
        """Returns exactly the (component_id, benchmark_id) pairs not declared (Req 11.4)."""
        defn = self._make_definition("test-switch", ["NDM"])
        lib = DeviceDefinitionLibrary(definitions=[defn])

        components = [
            _make_component(
                id="sw-01",
                device_definition="test-switch",
                stig_assignments=[
                    _make_assignment(benchmark_id="NDM", version="V1"),
                    _make_assignment(benchmark_id="EXTRA", version="V1"),
                ],
            ),
        ]
        sys = System(**_make_system(components=components))
        divergences = sys.stig_divergences(lib)
        assert divergences == [("sw-01", "EXTRA")]

    def test_never_raises(self):
        """stig_divergences never raises, even with missing definitions (Req 11.5)."""
        # Component references a definition slug that doesn't exist in the library
        lib = DeviceDefinitionLibrary(definitions=[])
        components = [
            _make_component(
                id="orphan-01",
                device_definition="nonexistent-slug",
                stig_assignments=[
                    _make_assignment(benchmark_id="ANYTHING", version="V1"),
                ],
            ),
        ]
        sys = System(**_make_system(components=components))
        # Should not raise — reports everything as divergent
        divergences = sys.stig_divergences(lib)
        assert divergences == [("orphan-01", "ANYTHING")]

    def test_no_device_definition_reports_all_as_divergent(self):
        """Component with no device_definition reports all assignments as divergent."""
        lib = DeviceDefinitionLibrary(definitions=[])
        components = [
            _make_component(
                id="bare-01",
                device_definition=None,
                stig_assignments=[
                    _make_assignment(benchmark_id="X", version="V1"),
                ],
            ),
        ]
        sys = System(**_make_system(components=components))
        divergences = sys.stig_divergences(lib)
        assert divergences == [("bare-01", "X")]

    def test_multiple_components_divergence(self):
        """Divergence report works across multiple components."""
        defn_a = self._make_definition("switch-a", ["NDM"])
        defn_b = self._make_definition("switch-b", ["L2S", "RTR"])
        lib = DeviceDefinitionLibrary(definitions=[defn_a, defn_b])

        components = [
            _make_component(
                id="sw-a",
                device_definition="switch-a",
                stig_assignments=[
                    _make_assignment(benchmark_id="NDM", version="V1"),
                    _make_assignment(benchmark_id="EXTRA_A", version="V1"),
                ],
            ),
            _make_component(
                id="sw-b",
                device_definition="switch-b",
                stig_assignments=[
                    _make_assignment(benchmark_id="L2S", version="V1"),
                    _make_assignment(benchmark_id="EXTRA_B", version="V1"),
                ],
            ),
        ]
        sys = System(**_make_system(components=components))
        divergences = sys.stig_divergences(lib)
        assert ("sw-a", "EXTRA_A") in divergences
        assert ("sw-b", "EXTRA_B") in divergences
        assert len(divergences) == 2


# ---------------------------------------------------------------------------
# Extra: StigAssignment additional field tests
# ---------------------------------------------------------------------------

class TestStigAssignmentFields:
    def test_assessed_date_accepted(self):
        """assessed_date field is accepted and stored."""
        a = StigAssignment(**_make_assignment(assessed_date="2026-06-15"))
        assert a.assessed_date == date(2026, 6, 15)

    def test_notes_accepted(self):
        """notes field is accepted and stored."""
        a = StigAssignment(**_make_assignment(notes="Pending re-assessment"))
        assert a.notes == "Pending re-assessment"

    def test_extra_key_rejected(self):
        """Extra keys on StigAssignment raise (StrictModel)."""
        with pytest.raises(ValidationError):
            StigAssignment(**_make_assignment(unknown_field="oops"))

    def test_whitespace_stripped(self):
        """Whitespace is stripped from string fields."""
        a = StigAssignment(**_make_assignment(
            benchmark_id="  TRIMMED  ",
            version="  V1  ",
            notes="  note  ",
        ))
        assert a.benchmark_id == "TRIMMED"
        assert a.version == "V1"
        assert a.notes == "note"
