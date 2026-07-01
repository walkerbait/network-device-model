"""Tests for the opt-in ingestion layer (network_models.io).

Exercises the XCCDF-result parser and the DISA CCI-list loader. These run on the
stdlib XML fallback, so no defusedxml install is required.
"""

from __future__ import annotations

from network_models import System
from network_models.io import parse_cci_list, parse_xccdf_results

XCCDF = b"""<?xml version="1.0"?>
<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.2" id="Cisco_NDM">
  <Group id="V-220518"><Rule id="SV-220518r991589_rule" severity="high"/></Group>
  <TestResult version="V2R9" end-time="2026-05-01T12:00:00">
    <title>Scan of edge-fw-01</title>
    <benchmark id="Cisco_NDM"/>
    <rule-result idref="SV-220518r991589_rule" severity="high">
      <result>fail</result>
      <ident system="http://cyber.mil/cci">CCI-000213</ident>
    </rule-result>
    <rule-result idref="SV-pass_rule"><result>pass</result></rule-result>
    <rule-result idref="SV-na_rule"><result>notapplicable</result></rule-result>
    <rule-result idref="SV-nc_rule"><result>notchecked</result></rule-result>
    <rule-result idref="SV-garbage_rule"><result>bananas</result></rule-result>
  </TestResult>
</Benchmark>"""


def test_parse_xccdf_status_mapping():
    cl = parse_xccdf_results(XCCDF, component="edge-fw-01")
    by_rule = {r.rule_id: r for r in cl.results}
    assert str(by_rule["SV-220518r991589_rule"].status) == "Open"
    assert str(by_rule["SV-pass_rule"].status) == "NotAFinding"
    assert str(by_rule["SV-na_rule"].status) == "Not_Applicable"
    assert str(by_rule["SV-nc_rule"].status) == "Not_Reviewed"
    # unmapped/garbage result falls back conservatively
    assert str(by_rule["SV-garbage_rule"].status) == "Not_Reviewed"


def test_parse_xccdf_metadata_and_ccis():
    cl = parse_xccdf_results(XCCDF, component="edge-fw-01")
    assert cl.benchmark_id == "Cisco_NDM"
    assert cl.version == "V2R9"
    assert cl.source == "SCAP"
    assert cl.evaluated_at.isoformat() == "2026-05-01T12:00:00"
    fail = next(r for r in cl.results if r.rule_id == "SV-220518r991589_rule")
    # group_id resolves from the embedded <Group>, CCIs from the disa ident
    assert fail.group_id == "V-220518"
    assert fail.ccis == ["CCI-000213"]


def test_group_id_none_when_group_absent():
    cl = parse_xccdf_results(XCCDF)
    pass_rule = next(r for r in cl.results if r.rule_id == "SV-pass_rule")
    assert pass_rule.group_id is None


def test_parsed_checklist_binds_into_system():
    cl = parse_xccdf_results(XCCDF, component="edge-fw-01")
    sysm = System(
        id="SYS-1",
        name="Edge",
        enclaves=[{"name": "dmz", "classification": "CUI"}],
        components=[{"id": "edge-fw-01", "enclave": "dmz", "category": "firewall"}],
        authorization={"checklists": [cl.model_dump()]},
    )
    assert sysm.authorization.cat_open_counts == {"CAT I": 1}
    # round-trips through JSON despite computed score fields
    System.model_validate(sysm.model_dump(mode="json"))


CCI_LIST = b"""<cci_list xmlns="http://iase.disa.mil/cci"><cci_items>
  <cci_item id="CCI-000213"><references>
    <reference title="NIST SP 800-53 Revision 4" index="AC-3"/>
    <reference title="NIST SP 800-53 Revision 5" index="AC-3 (1)"/>
  </references></cci_item>
  <cci_item id="CCI-000015"><references>
    <reference title="NIST SP 800-53" index="AC-2 (1) (a)"/>
  </references></cci_item>
</cci_items></cci_list>"""


def test_parse_cci_list():
    m = parse_cci_list(CCI_LIST)
    assert m["CCI-000213"] == ["AC-3", "AC-3(1)"]
    assert m["CCI-000015"] == ["AC-2(1)"]
