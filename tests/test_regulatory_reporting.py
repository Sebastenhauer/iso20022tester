"""Tests fuer RgltryRptg (Regulatory Reporting) Feature.

Testet XML-Generierung, Business Rules, XSD-Validierung und
Pipeline-Integration fuer CGI-MP und CBPR+ Zahlungen.
"""

import os
from decimal import Decimal

import pytest
from lxml import etree
from openpyxl import Workbook

from src.models.testcase import (
    DebtorInfo,
    PaymentInstruction,
    Standard,
    Transaction,
)
from src.xml_generator.builders import build_regulatory_reporting, el
from src.xml_generator.namespace import PAIN001_NS
from src.xml_generator.pain001_builder import build_pain001_xml, serialize_xml
from src.validation.business_rules import validate_all_business_rules
from src.validation.xsd_validator import XsdValidator

NS = {"p": PAIN001_NS}
DEBTOR = DebtorInfo(name="Test AG", iban="CH9300762011623852957", bic="CRESCHZZ80A")


def _tx(**kwargs):
    defaults = dict(
        end_to_end_id="E2E-test001",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Teststr.", "TwnNm": "Bern", "Ctry": "CH"},
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def _instr(transactions=None, **kwargs):
    defaults = dict(
        msg_id="MSG-test001",
        pmt_inf_id="PMT-test001",
        cre_dt_tm="2026-03-28T10:00:00",
        reqd_exctn_dt="2026-03-30",
        debtor=DEBTOR,
    )
    defaults.update(kwargs)
    defaults["transactions"] = transactions or [_tx()]
    return PaymentInstruction(**defaults)


# =========================================================================
# XML Builder: build_regulatory_reporting
# =========================================================================

class TestBuildRegulatoryReporting:
    def test_full_regulatory_reporting(self):
        """Volle RgltryRptg-Struktur mit allen Feldern."""
        root = etree.Element(f"{{{PAIN001_NS}}}CdtTrfTxInf")
        reg_data = {
            "DbtCdtRptgInd": "CRED",
            "Authrty.Nm": "Bundesbank",
            "Authrty.Ctry": "DE",
            "Dtls.Tp": "BALANCE_OF_PAYMENTS",
            "Dtls.Ctry": "DE",
            "Dtls.Cd": "100",
            "Dtls.Inf": "Cross-border payment",
        }
        result = build_regulatory_reporting(root, reg_data)
        assert result is not None

        ind = root.findtext(f".//p:RgltryRptg/p:DbtCdtRptgInd", namespaces=NS)
        assert ind == "CRED"

        nm = root.findtext(f".//p:RgltryRptg/p:Authrty/p:Nm", namespaces=NS)
        assert nm == "Bundesbank"

        ctry = root.findtext(f".//p:RgltryRptg/p:Authrty/p:Ctry", namespaces=NS)
        assert ctry == "DE"

        tp = root.findtext(f".//p:RgltryRptg/p:Dtls/p:Tp", namespaces=NS)
        assert tp == "BALANCE_OF_PAYMENTS"

        dtls_ctry = root.findtext(f".//p:RgltryRptg/p:Dtls/p:Ctry", namespaces=NS)
        assert dtls_ctry == "DE"

        cd = root.findtext(f".//p:RgltryRptg/p:Dtls/p:Cd", namespaces=NS)
        assert cd == "100"

        inf = root.findtext(f".//p:RgltryRptg/p:Dtls/p:Inf", namespaces=NS)
        assert inf == "Cross-border payment"

    def test_dtls_element_order(self):
        """XSD-Reihenfolge in Dtls: Tp, Ctry, Cd, Inf."""
        root = etree.Element(f"{{{PAIN001_NS}}}CdtTrfTxInf")
        reg_data = {
            "DbtCdtRptgInd": "CRED",
            "Dtls.Tp": "BOP",
            "Dtls.Ctry": "CH",
            "Dtls.Cd": "100",
            "Dtls.Inf": "Info",
        }
        build_regulatory_reporting(root, reg_data)
        dtls = root.find(f".//p:RgltryRptg/p:Dtls", NS)
        tags = [child.tag.split("}")[-1] for child in dtls]
        assert tags == ["Tp", "Ctry", "Cd", "Inf"]

    def test_minimal_regulatory_reporting(self):
        """Minimale RgltryRptg-Struktur: nur DbtCdtRptgInd."""
        root = etree.Element(f"{{{PAIN001_NS}}}CdtTrfTxInf")
        reg_data = {"DbtCdtRptgInd": "DEBT"}
        result = build_regulatory_reporting(root, reg_data)
        assert result is not None

        ind = root.findtext(f".//p:RgltryRptg/p:DbtCdtRptgInd", namespaces=NS)
        assert ind == "DEBT"

        # Keine Authrty oder Dtls
        authrty = root.find(f".//p:RgltryRptg/p:Authrty", NS)
        assert authrty is None
        dtls = root.find(f".//p:RgltryRptg/p:Dtls", NS)
        assert dtls is None

    def test_returns_none_when_empty(self):
        """Leere Daten → None, kein Element erzeugt."""
        root = etree.Element(f"{{{PAIN001_NS}}}CdtTrfTxInf")
        result = build_regulatory_reporting(root, {})
        assert result is None

    def test_returns_none_when_none(self):
        root = etree.Element(f"{{{PAIN001_NS}}}CdtTrfTxInf")
        result = build_regulatory_reporting(root, None)
        assert result is None

    def test_dtls_only(self):
        """Nur Dtls ohne DbtCdtRptgInd."""
        root = etree.Element(f"{{{PAIN001_NS}}}CdtTrfTxInf")
        reg_data = {"Dtls.Tp": "TAX", "Dtls.Ctry": "CH", "Dtls.Cd": "TAX001"}
        build_regulatory_reporting(root, reg_data)

        tp = root.findtext(f".//p:RgltryRptg/p:Dtls/p:Tp", namespaces=NS)
        assert tp == "TAX"
        cd = root.findtext(f".//p:RgltryRptg/p:Dtls/p:Cd", namespaces=NS)
        assert cd == "TAX001"
        ctry = root.findtext(f".//p:RgltryRptg/p:Dtls/p:Ctry", namespaces=NS)
        assert ctry == "CH"


# =========================================================================
# pain.001 XML Generierung mit RgltryRptg
# =========================================================================

class TestPain001WithRegulatoryReporting:
    def test_rgltry_rptg_in_xml(self):
        """RgltryRptg wird korrekt in CdtTrfTxInf erzeugt."""
        tx = _tx(regulatory_reporting={
            "DbtCdtRptgInd": "CRED",
            "Dtls.Tp": "BALANCE_OF_PAYMENTS",
            "Dtls.Ctry": "CH",
            "Dtls.Cd": "100",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))

        ind = xml.findtext(
            f".//p:CdtTrfTxInf/p:RgltryRptg/p:DbtCdtRptgInd", namespaces=NS
        )
        assert ind == "CRED"

    def test_no_rgltry_rptg_when_none(self):
        """Ohne regulatory_reporting kein RgltryRptg-Element."""
        tx = _tx(regulatory_reporting=None)
        xml = build_pain001_xml(_instr(transactions=[tx]))
        rptg = xml.find(f".//p:RgltryRptg", NS)
        assert rptg is None

    def test_rgltry_rptg_element_order(self):
        """RgltryRptg muss nach Purp und vor RmtInf stehen (XSD-Reihenfolge)."""
        tx = _tx(
            purpose_code="SALA",
            regulatory_reporting={"DbtCdtRptgInd": "DEBT"},
            remittance_info={"type": "USTRD", "value": "Test"},
        )
        xml = build_pain001_xml(_instr(transactions=[tx]))
        cdt_trf = xml.find(f".//p:CdtTrfTxInf", NS)
        tags = [child.tag.split("}")[-1] for child in cdt_trf]

        purp_idx = tags.index("Purp")
        rptg_idx = tags.index("RgltryRptg")
        rmt_idx = tags.index("RmtInf")
        assert purp_idx < rptg_idx < rmt_idx


# =========================================================================
# XSD-Validierung
# =========================================================================

class TestRegulatoryReportingXsd:
    @pytest.fixture
    def xsd_validator(self):
        return XsdValidator("schemas/pain.001.001.09.ch.03.xsd")

    def test_full_rgltry_rptg_xsd_valid(self, xsd_validator):
        """Vollstaendige RgltryRptg-Struktur ist XSD-valide."""
        tx = _tx(regulatory_reporting={
            "DbtCdtRptgInd": "CRED",
            "Authrty.Nm": "Test Authority",
            "Authrty.Ctry": "CH",
            "Dtls.Tp": "BALANCE_OF_PAYMENTS",
            "Dtls.Ctry": "CH",
            "Dtls.Cd": "100",
            "Dtls.Inf": "Payment info",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"

    def test_minimal_rgltry_rptg_xsd_valid(self, xsd_validator):
        """Minimale RgltryRptg (nur Indicator) ist XSD-valide."""
        tx = _tx(regulatory_reporting={"DbtCdtRptgInd": "DEBT"})
        xml = build_pain001_xml(_instr(transactions=[tx]))
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"

    def test_rgltry_rptg_with_purpose_and_remittance_xsd_valid(self, xsd_validator):
        """RgltryRptg zusammen mit Purp und RmtInf ist XSD-valide."""
        tx = _tx(
            purpose_code="SALA",
            regulatory_reporting={"DbtCdtRptgInd": "BOTH", "Dtls.Ctry": "CH", "Dtls.Cd": "200"},
            remittance_info={"type": "USTRD", "value": "Lohnzahlung"},
        )
        xml = build_pain001_xml(_instr(transactions=[tx]))
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"

    def test_rgltry_rptg_with_creditor_bic_xsd_valid(self, xsd_validator):
        """RgltryRptg mit Creditor-BIC (CBPR+ Szenario) ist XSD-valide."""
        tx = _tx(
            creditor_bic="BNPAFRPP",
            regulatory_reporting={
                "DbtCdtRptgInd": "CRED",
                "Dtls.Tp": "CROSS_BORDER",
                "Dtls.Ctry": "FR",
                "Dtls.Cd": "500",
            },
        )
        xml = build_pain001_xml(_instr(transactions=[tx]))
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"


# =========================================================================
# Business Rules
# =========================================================================

class TestRegulatoryReportingBusinessRules:
    def _make_testcase(self, payment_type="CBPR+", standard="cbpr+2026"):
        from src.models.testcase import TestCase, ExpectedResult, PaymentType, Standard
        return TestCase(
            testcase_id="TC-RGRP",
            titel="RgltryRptg Test",
            ziel="Test",
            expected_result=ExpectedResult.OK,
            payment_type=PaymentType(payment_type),
            debtor=DEBTOR,
            standard=Standard(standard),
            amount=Decimal("1000.00"),
            currency="USD",
        )

    def test_valid_regulatory_reporting(self):
        """Gueltige RgltryRptg: alle Regeln passen."""
        tc = self._make_testcase()
        tx = _tx(
            creditor_bic="BNPAFRPP",
            currency="USD",
            regulatory_reporting={
                "DbtCdtRptgInd": "CRED",
                "Dtls.Tp": "BALANCE_OF_PAYMENTS",
                "Dtls.Ctry": "US",
                "Dtls.Cd": "100",
            },
        )
        instr = _instr(transactions=[tx], charge_bearer="SHAR")
        results = validate_all_business_rules(instr, tc)

        rgrp_rules = {r.rule_id: r for r in results
                      if r.rule_id.startswith("BR-CGI-") or r.rule_id.startswith("BR-CH21-")}
        for rule_id in ("BR-CGI-PURP-02", "BR-CGI-RGRP-01", "BR-CGI-RGRP-02", "BR-CH21-RGRP-CD-CTRY"):
            if rule_id in rgrp_rules:
                assert rgrp_rules[rule_id].passed, f"{rule_id} fehlgeschlagen: {rgrp_rules[rule_id].details}"

    def test_missing_indicator(self):
        """BR-CGI-PURP-02: DbtCdtRptgInd fehlt → Fehler."""
        tc = self._make_testcase()
        tx = _tx(
            creditor_bic="BNPAFRPP",
            currency="USD",
            regulatory_reporting={
                "Dtls.Tp": "BALANCE_OF_PAYMENTS",
                "Dtls.Ctry": "US",
                "Dtls.Cd": "100",
            },
        )
        instr = _instr(transactions=[tx], charge_bearer="SHAR")
        results = validate_all_business_rules(instr, tc)

        purp02 = [r for r in results if r.rule_id == "BR-CGI-PURP-02"]
        assert len(purp02) == 1
        assert purp02[0].passed is False

    def test_missing_type_with_details(self):
        """BR-CGI-RGRP-01: Dtls vorhanden aber Tp fehlt → Fehler."""
        tc = self._make_testcase()
        tx = _tx(
            creditor_bic="BNPAFRPP",
            currency="USD",
            regulatory_reporting={
                "DbtCdtRptgInd": "DEBT",
                "Dtls.Ctry": "US",
                "Dtls.Cd": "100",
            },
        )
        instr = _instr(transactions=[tx], charge_bearer="SHAR")
        results = validate_all_business_rules(instr, tc)

        rgrp01 = [r for r in results if r.rule_id == "BR-CGI-RGRP-01"]
        assert len(rgrp01) == 1
        assert rgrp01[0].passed is False

    def test_code_too_long(self):
        """BR-CGI-RGRP-02: Code > 10 Zeichen → Fehler."""
        tc = self._make_testcase()
        tx = _tx(
            creditor_bic="BNPAFRPP",
            currency="USD",
            regulatory_reporting={
                "DbtCdtRptgInd": "CRED",
                "Dtls.Tp": "BALANCE_OF_PAYMENTS",
                "Dtls.Ctry": "US",
                "Dtls.Cd": "12345678901",  # 11 Zeichen
            },
        )
        instr = _instr(transactions=[tx], charge_bearer="SHAR")
        results = validate_all_business_rules(instr, tc)

        rgrp02 = [r for r in results if r.rule_id == "BR-CGI-RGRP-02"]
        assert len(rgrp02) == 1
        assert rgrp02[0].passed is False

    def test_no_regulatory_reporting_no_rules_triggered(self):
        """Ohne RgltryRptg werden keine RgltryRptg-Regeln geprueft."""
        tc = self._make_testcase()
        tx = _tx(creditor_bic="BNPAFRPP", currency="USD")
        instr = _instr(transactions=[tx], charge_bearer="SHAR")
        results = validate_all_business_rules(instr, tc)

        rgrp_rules = [r for r in results if r.rule_id.startswith("BR-CGI-RGRP")]
        assert len(rgrp_rules) == 0

    def test_ch21_cd_without_ctry(self):
        """BR-CH21-RGRP-CD-CTRY: Cd ohne Ctry → Fehler."""
        tc = self._make_testcase()
        tx = _tx(
            creditor_bic="BNPAFRPP",
            currency="USD",
            regulatory_reporting={
                "DbtCdtRptgInd": "CRED",
                "Dtls.Tp": "BALANCE_OF_PAYMENTS",
                "Dtls.Cd": "100",
                # Dtls.Ctry fehlt absichtlich
            },
        )
        instr = _instr(transactions=[tx], charge_bearer="SHAR")
        results = validate_all_business_rules(instr, tc)

        ch21 = [r for r in results if r.rule_id == "BR-CH21-RGRP-CD-CTRY"]
        assert len(ch21) == 1
        assert ch21[0].passed is False

    def test_ch21_cd_with_ctry_valid(self):
        """BR-CH21-RGRP-CD-CTRY: Cd mit Ctry → OK."""
        tc = self._make_testcase()
        tx = _tx(
            creditor_bic="BNPAFRPP",
            currency="USD",
            regulatory_reporting={
                "DbtCdtRptgInd": "CRED",
                "Dtls.Tp": "BALANCE_OF_PAYMENTS",
                "Dtls.Ctry": "US",
                "Dtls.Cd": "100",
            },
        )
        instr = _instr(transactions=[tx], charge_bearer="SHAR")
        results = validate_all_business_rules(instr, tc)

        ch21 = [r for r in results if r.rule_id == "BR-CH21-RGRP-CD-CTRY"]
        assert len(ch21) == 1
        assert ch21[0].passed is True

    def test_both_indicator_valid(self):
        """DbtCdtRptgInd=BOTH ist gueltig."""
        tc = self._make_testcase()
        tx = _tx(
            creditor_bic="BNPAFRPP",
            currency="USD",
            regulatory_reporting={"DbtCdtRptgInd": "BOTH"},
        )
        instr = _instr(transactions=[tx], charge_bearer="SHAR")
        results = validate_all_business_rules(instr, tc)

        purp02 = [r for r in results if r.rule_id == "BR-CGI-PURP-02"]
        assert len(purp02) == 1
        assert purp02[0].passed is True


# =========================================================================
# Pipeline Integration (E2E via Overrides)
# =========================================================================

class TestRegulatoryReportingE2E:
    """Integration-Tests: Excel → Pipeline → XML mit RgltryRptg."""

    V2_HEADERS = [
        "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis", "Zahlungstyp",
        "Betrag", "Waehrung", "Debtor Name", "Debtor IBAN", "Debtor BIC",
        "Creditor Name", "Creditor IBAN", "Creditor BIC", "Verwendungszweck",
        "ViolateRule", "Weitere Testdaten", "Erwartete API-Antwort", "Bemerkungen",
    ]

    def _create_excel(self, rows, tmpdir):
        wb = Workbook()
        ws = wb.active
        ws.append(self.V2_HEADERS)
        for row in rows:
            ws.append(row)
        path = os.path.join(tmpdir, "test.xlsx")
        wb.save(path)
        return path

    def _config(self, tmpdir):
        from src.models.config import AppConfig
        return AppConfig(
            output_path=tmpdir,
            xsd_path="schemas/pain.001.001.09.ch.03.xsd",
            seed=42,
            report_format="txt",
        )

    def test_cbpr_with_regulatory_reporting(self, tmp_path):
        """CBPR+ Zahlung mit RgltryRptg via Overrides."""
        from src.main import run

        overrides = (
            "CdtrAgt.BICFI=BNPAFRPP; "
            "RgltryRptg.DbtCdtRptgInd=CRED; "
            "RgltryRptg.Dtls.Tp=BALANCE_OF_PAYMENTS; "
            "RgltryRptg.Dtls.Ctry=US; "
            "RgltryRptg.Dtls.Cd=100"
        )
        row = [
            "TC-RGRP1", "CBPR+ RgltryRptg", "Regulatory Reporting", "OK", "CBPR+",
            10000.00, "USD", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None, overrides, None, None,
        ]
        excel = self._create_excel([row], str(tmp_path))
        results = run(excel, self._config(str(tmp_path)), seed_override=42)
        assert len(results) == 1
        assert results[0].overall_pass is True
        assert results[0].xsd_valid is True

        # Verify XML contains RgltryRptg
        xml_path = results[0].xml_file_path
        assert xml_path is not None
        tree = etree.parse(xml_path)
        # XPath in BAH-wrapped document
        nsmap = {"p": PAIN001_NS}
        rptg = tree.xpath("//p:RgltryRptg", namespaces=nsmap)
        assert len(rptg) >= 1

    def test_cbpr_regulatory_reporting_nok_missing_indicator(self, tmp_path):
        """CBPR+ mit RgltryRptg ohne DbtCdtRptgInd → NOK."""
        from src.main import run

        overrides = (
            "CdtrAgt.BICFI=BNPAFRPP; "
            "RgltryRptg.Dtls.Tp=BALANCE_OF_PAYMENTS; "
            "RgltryRptg.Dtls.Ctry=US; "
            "RgltryRptg.Dtls.Cd=100"
        )
        row = [
            "TC-RGRP2", "CBPR+ RgltryRptg NOK", "Missing Indicator", "NOK", "CBPR+",
            10000.00, "USD", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None, overrides, None, None,
        ]
        excel = self._create_excel([row], str(tmp_path))
        results = run(excel, self._config(str(tmp_path)), seed_override=42)
        assert len(results) == 1
        assert results[0].overall_pass is True  # NOK erwartet und BR schlaegt fehl
        failed_ids = {r.rule_id for r in results[0].business_rule_results if not r.passed}
        assert "BR-CGI-PURP-02" in failed_ids
