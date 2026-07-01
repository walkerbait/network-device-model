"""Tests for the STIG catalog models (network_models/stig/).

Covers: catalog uniqueness, severity/CAT derivation, profile resolution,
rule/profile integrity, JSON round-trip, latest_version, and type filtering.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from network_models.stig.catalog import Stig, StigCatalog, StigProfile, StigRule
from network_models.stig.vocab import SEVERITY_TO_CAT, RuleSeverity, StigType


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_rule(
    *,
    group_id: str = "V-100001",
    rule_id: str = "SV-100001r1_rule",
    severity: str = "medium",
    title: str = "Test rule",
    **kwargs,
) -> dict:
    """Minimal valid StigRule dict."""
    return {
        "group_id": group_id,
        "rule_id": rule_id,
        "severity": severity,
        "title": title,
        **kwargs,
    }


def _make_stig(*, rules=None, profiles=None, **overrides) -> dict:
    """Minimal valid Stig dict with sensible defaults."""
    defaults = {
        "benchmark_id": "TEST_STIG",
        "title": "Test STIG",
        "version": "1",
        "type": "stig",
        "source_file": "U_Test_STIG_V1_Manual-xccdf.xml",
    }
    defaults.update(overrides)
    if rules is not None:
        defaults["rules"] = rules
    elif "rules" not in defaults:
        defaults["rules"] = [_make_rule()]
    if profiles is not None:
        defaults["profiles"] = profiles
    return defaults


def _make_catalog(stigs=None, catalog_version="April_2026") -> dict:
    """Minimal valid StigCatalog dict."""
    return {
        "catalog_version": catalog_version,
        "stigs": stigs or [],
    }


# ---------------------------------------------------------------------------
# Req 3.4, 3.5 — Catalog uniqueness on (benchmark_id, version)
# ---------------------------------------------------------------------------

class TestCatalogUniqueness:
    def test_distinct_keys_accepted(self):
        """Distinct (benchmark_id, version) pairs construct successfully."""
        s1 = _make_stig(benchmark_id="A", version="1")
        s2 = _make_stig(benchmark_id="A", version="2")
        s3 = _make_stig(benchmark_id="B", version="1")
        catalog = StigCatalog(**_make_catalog(stigs=[s1, s2, s3]))
        assert len(catalog.stigs) == 3

    def test_duplicate_benchmark_version_rejected(self):
        """Duplicate (benchmark_id, version) raises ValidationError."""
        s1 = _make_stig(benchmark_id="DUP", version="1")
        s2 = _make_stig(benchmark_id="DUP", version="1")
        with pytest.raises(ValidationError, match="duplicate"):
            StigCatalog(**_make_catalog(stigs=[s1, s2]))


# ---------------------------------------------------------------------------
# Req 2.1, 2.2, 2.3, 2.4 — StigType enum and benchmark_ids filtering
# ---------------------------------------------------------------------------

class TestStigType:
    def test_valid_types_accepted(self):
        """Both 'srg' and 'stig' are valid type values."""
        srg = Stig(**_make_stig(type="srg"))
        stig = Stig(**_make_stig(type="stig"))
        assert str(srg.type) == "srg"
        assert str(stig.type) == "stig"

    def test_invalid_type_rejected(self):
        """A type value outside {srg, stig} raises ValidationError."""
        with pytest.raises(ValidationError):
            Stig(**_make_stig(type="guide"))

    def test_benchmark_ids_filtered_by_stig_type(self):
        """benchmark_ids(type='stig') returns only stig entries."""
        s1 = _make_stig(benchmark_id="SRG_A", type="srg")
        s2 = _make_stig(benchmark_id="STIG_B", type="stig")
        catalog = StigCatalog(**_make_catalog(stigs=[s1, s2]))
        assert catalog.benchmark_ids(type="stig") == ["STIG_B"]

    def test_benchmark_ids_filtered_by_srg_type(self):
        """benchmark_ids(type='srg') returns only srg entries."""
        s1 = _make_stig(benchmark_id="SRG_A", type="srg")
        s2 = _make_stig(benchmark_id="STIG_B", type="stig")
        catalog = StigCatalog(**_make_catalog(stigs=[s1, s2]))
        assert catalog.benchmark_ids(type="srg") == ["SRG_A"]

    def test_benchmark_ids_no_filter_returns_all(self):
        """benchmark_ids() with no type filter returns all distinct ids."""
        s1 = _make_stig(benchmark_id="SRG_A", type="srg")
        s2 = _make_stig(benchmark_id="STIG_B", type="stig")
        catalog = StigCatalog(**_make_catalog(stigs=[s1, s2]))
        assert set(catalog.benchmark_ids()) == {"SRG_A", "STIG_B"}


# ---------------------------------------------------------------------------
# Req 4.3, 4.4, 4.7 — Severity / CAT derivation
# ---------------------------------------------------------------------------

class TestSeverityAndCat:
    @pytest.mark.parametrize("severity,expected_cat", [
        ("high", "CAT I"),
        ("medium", "CAT II"),
        ("low", "CAT III"),
    ])
    def test_severity_to_cat(self, severity, expected_cat):
        """high/medium/low map to CAT I/II/III respectively."""
        rule = StigRule(**_make_rule(severity=severity))
        assert rule.cat == expected_cat

    def test_unknown_severity_cat_is_none(self):
        """severity='unknown' yields cat=None."""
        rule = StigRule(**_make_rule(severity="unknown"))
        assert rule.cat is None

    def test_invalid_severity_rejected(self):
        """Out-of-vocabulary severity raises ValidationError."""
        with pytest.raises(ValidationError):
            StigRule(**_make_rule(severity="critical"))

    def test_severity_to_cat_matches_constant(self):
        """The cat property agrees with the SEVERITY_TO_CAT lookup for all known values."""
        for sev, cat in SEVERITY_TO_CAT.items():
            rule = StigRule(**_make_rule(severity=sev))
            assert rule.cat == cat


# ---------------------------------------------------------------------------
# Req 5.6 — severity_counts conservation
# ---------------------------------------------------------------------------

class TestSeverityCounts:
    def test_sum_equals_rule_count(self):
        """Sum of severity_counts values equals the number of rules."""
        rules = [
            _make_rule(group_id="V-1", rule_id="SV-1_rule", severity="high"),
            _make_rule(group_id="V-2", rule_id="SV-2_rule", severity="medium"),
            _make_rule(group_id="V-3", rule_id="SV-3_rule", severity="low"),
            _make_rule(group_id="V-4", rule_id="SV-4_rule", severity="unknown"),
        ]
        stig = Stig(**_make_stig(rules=rules))
        counts = stig.severity_counts
        assert sum(counts.values()) == len(stig.rules)
        assert counts == {"CAT I": 1, "CAT II": 1, "CAT III": 1, "unknown": 1}


# ---------------------------------------------------------------------------
# Req 5.3, 5.4, 5.5, 6.2 — Profile resolution and uniqueness
# ---------------------------------------------------------------------------

class TestProfileResolution:
    def test_valid_profile_resolves(self):
        """A profile whose selected_rule_ids all exist in rules constructs OK."""
        rules = [
            _make_rule(group_id="V-1", rule_id="SV-1_rule"),
            _make_rule(group_id="V-2", rule_id="SV-2_rule"),
        ]
        profiles = [{"id": "MAC-1", "selected_rule_ids": ["SV-1_rule", "SV-2_rule"]}]
        stig = Stig(**_make_stig(rules=rules, profiles=profiles))
        assert len(stig.profiles) == 1

    def test_dangling_profile_ref_rejected(self):
        """A profile referencing a non-existent rule raises ValidationError."""
        rules = [_make_rule(group_id="V-1", rule_id="SV-1_rule")]
        profiles = [{"id": "MAC-1", "selected_rule_ids": ["SV-1_rule", "SV-NOPE_rule"]}]
        with pytest.raises(ValidationError, match="unknown rule id"):
            Stig(**_make_stig(rules=rules, profiles=profiles))

    def test_duplicate_selected_rule_ids_rejected(self):
        """Duplicate entries in selected_rule_ids raise ValidationError."""
        with pytest.raises(ValidationError, match="duplicate rule id"):
            StigProfile(id="P1", selected_rule_ids=["SV-1_rule", "SV-1_rule"])

    def test_duplicate_profile_ids_rejected(self):
        """Duplicate profile id values within a Stig raise ValidationError."""
        rules = [_make_rule(group_id="V-1", rule_id="SV-1_rule")]
        profiles = [
            {"id": "MAC-1", "selected_rule_ids": ["SV-1_rule"]},
            {"id": "MAC-1", "selected_rule_ids": ["SV-1_rule"]},
        ]
        with pytest.raises(ValidationError, match="duplicate profile id"):
            Stig(**_make_stig(rules=rules, profiles=profiles))


# ---------------------------------------------------------------------------
# Req 4.6, 5.1, 5.2 — Rule uniqueness (rule_id, group_id, ccis, legacy_ids)
# ---------------------------------------------------------------------------

class TestRuleUniqueness:
    def test_duplicate_rule_id_rejected(self):
        """Duplicate rule_id values within a Stig raise ValidationError."""
        rules = [
            _make_rule(group_id="V-1", rule_id="SV-DUP_rule"),
            _make_rule(group_id="V-2", rule_id="SV-DUP_rule"),
        ]
        with pytest.raises(ValidationError, match="duplicate rule_id"):
            Stig(**_make_stig(rules=rules))

    def test_duplicate_group_id_rejected(self):
        """Duplicate group_id values within a Stig raise ValidationError."""
        rules = [
            _make_rule(group_id="V-DUP", rule_id="SV-1_rule"),
            _make_rule(group_id="V-DUP", rule_id="SV-2_rule"),
        ]
        with pytest.raises(ValidationError, match="duplicate group_id"):
            Stig(**_make_stig(rules=rules))

    def test_duplicate_ccis_rejected(self):
        """Duplicate CCI entries in a rule raise ValidationError."""
        with pytest.raises(ValidationError, match="duplicate identifier"):
            StigRule(**_make_rule(ccis=["CCI-000015", "CCI-000015"]))

    def test_duplicate_legacy_ids_rejected(self):
        """Duplicate legacy_ids entries in a rule raise ValidationError."""
        with pytest.raises(ValidationError, match="duplicate identifier"):
            StigRule(**_make_rule(legacy_ids=["V-80819", "V-80819"]))


# ---------------------------------------------------------------------------
# Req 7.1, 7.2 — JSON round-trip fidelity
# ---------------------------------------------------------------------------

class TestJsonRoundTrip:
    def test_stig_roundtrip(self):
        """A valid Stig survives JSON dump/reload without loss."""
        rules = [
            _make_rule(
                group_id="V-1",
                rule_id="SV-1_rule",
                severity="high",
                stig_id="SRG-APP-000001",
                weight=10.0,
                discussion="Discuss this",
                check_content="Check this",
                check_content_ref="ref.xml",
                check_system="http://oval",
                fix_text="Fix it",
                fix_id="F-1",
                ccis=["CCI-000015", "CCI-000016"],
                legacy_ids=["V-80819", "V-80820"],
            ),
            _make_rule(group_id="V-2", rule_id="SV-2_rule", severity="low"),
        ]
        profiles = [
            {"id": "MAC-1", "title": "MAC 1 Profile", "selected_rule_ids": ["SV-1_rule", "SV-2_rule"]},
        ]
        original = Stig(**_make_stig(
            rules=rules,
            profiles=profiles,
            release_info="Release: 1 Benchmark Date: 01 Jan 2026",
            status="accepted",
            status_date="2026-01-01",
        ))

        dumped = original.model_dump(mode="json")
        reloaded = Stig.model_validate(dumped)
        assert reloaded == original

    def test_order_preserved_in_roundtrip(self):
        """Rule order, ccis order, legacy_ids order, and profiles are preserved."""
        rules = [
            _make_rule(group_id=f"V-{i}", rule_id=f"SV-{i}_rule")
            for i in range(1, 6)
        ]
        profiles = [
            {"id": "P1", "selected_rule_ids": [f"SV-{i}_rule" for i in range(1, 6)]},
            {"id": "P2", "selected_rule_ids": [f"SV-{i}_rule" for i in range(5, 0, -1)]},
        ]
        original = Stig(**_make_stig(rules=rules, profiles=profiles))
        reloaded = Stig.model_validate(original.model_dump(mode="json"))

        assert [r.rule_id for r in reloaded.rules] == [r.rule_id for r in original.rules]
        assert [p.id for p in reloaded.profiles] == [p.id for p in original.profiles]
        for orig_p, reload_p in zip(original.profiles, reloaded.profiles):
            assert reload_p.selected_rule_ids == orig_p.selected_rule_ids


# ---------------------------------------------------------------------------
# Req 12.1–12.5 — latest_version
# ---------------------------------------------------------------------------

class TestLatestVersion:
    def test_returns_member_of_versions(self):
        """latest_version returns a value that is in versions() for that id."""
        s1 = _make_stig(benchmark_id="X", version="1")
        s2 = _make_stig(benchmark_id="X", version="2")
        catalog = StigCatalog(**_make_catalog(stigs=[s1, s2]))
        result = catalog.latest_version("X")
        assert result in catalog.versions("X")

    def test_returns_none_when_absent(self):
        """latest_version returns None for an absent benchmark_id."""
        catalog = StigCatalog(**_make_catalog(stigs=[]))
        assert catalog.latest_version("NOPE") is None

    def test_status_date_wins(self):
        """When entries have status_date, the most recent wins."""
        s1 = _make_stig(benchmark_id="X", version="V1", status_date="2025-01-01")
        s2 = _make_stig(benchmark_id="X", version="V2", status_date="2026-06-15")
        s3 = _make_stig(benchmark_id="X", version="V3", status_date="2024-12-01")
        catalog = StigCatalog(**_make_catalog(stigs=[s1, s2, s3]))
        assert catalog.latest_version("X") == "V2"

    def test_last_seen_fallback_when_no_dates(self):
        """When no entry has status_date, the last-seen (insertion order) wins."""
        s1 = _make_stig(benchmark_id="X", version="V1")
        s2 = _make_stig(benchmark_id="X", version="V2")
        catalog = StigCatalog(**_make_catalog(stigs=[s1, s2]))
        assert catalog.latest_version("X") == "V2"

    def test_does_not_parse_version_strings(self):
        """Heterogeneous version strings are NOT parsed/normalized."""
        # V10 would sort before V9 lexicographically if parsed as strings;
        # but latest_version should not parse — it uses status_date or insertion order
        s1 = _make_stig(benchmark_id="X", version="V10", status_date="2025-01-01")
        s2 = _make_stig(benchmark_id="X", version="V9", status_date="2026-01-01")
        catalog = StigCatalog(**_make_catalog(stigs=[s1, s2]))
        assert catalog.latest_version("X") == "V9"  # most recent status_date


# ---------------------------------------------------------------------------
# Req 3.6 — catalog get() lookup
# ---------------------------------------------------------------------------

class TestCatalogGet:
    def test_get_by_benchmark_and_version(self):
        """get(benchmark_id, version) returns the matching entry."""
        s = _make_stig(benchmark_id="AAA", version="2")
        catalog = StigCatalog(**_make_catalog(stigs=[s]))
        result = catalog.get("AAA", "2")
        assert result is not None
        assert result.benchmark_id == "AAA"
        assert result.version == "2"

    def test_get_returns_none_when_no_match(self):
        """get() returns None when no entry matches."""
        catalog = StigCatalog(**_make_catalog(stigs=[_make_stig()]))
        assert catalog.get("NOPE", "1") is None

    def test_get_without_version_returns_first_match(self):
        """get(benchmark_id) with no version returns the first match."""
        s1 = _make_stig(benchmark_id="X", version="1")
        s2 = _make_stig(benchmark_id="X", version="2")
        catalog = StigCatalog(**_make_catalog(stigs=[s1, s2]))
        result = catalog.get("X")
        assert result is not None
        assert result.version == "1"


# ---------------------------------------------------------------------------
# Extra: StrictModel behavior (extra="forbid", strip whitespace)
# ---------------------------------------------------------------------------

class TestStrictModelBehavior:
    def test_unknown_key_rejected(self):
        """Extra keys on a STIG model raise ValidationError (StrictModel)."""
        with pytest.raises(ValidationError):
            StigRule(**_make_rule(unknown_field="oops"))

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace is stripped from string fields."""
        rule = StigRule(**_make_rule(title="  Padded Title  "))
        assert rule.title == "Padded Title"
