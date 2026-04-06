"""Tests fuer XML-Generator: pain.001 Aufbau und XSD-Validierung."""

from decimal import Decimal

import pytest
from lxml import etree

from src.data_factory.generator import DataFactory
from src.models.testcase import (
    DebtorInfo,
    Pain001Document,
    PaymentInstruction,
    Transaction,
)
from src.xml_generator.namespace import PAIN001_NS
from src.xml_generator.pain001_builder import (
    build_pain001_document,
    build_pain001_xml,
    serialize_xml,
)
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
# Grundlegende XML-Struktur
# =========================================================================

class TestXmlStructure:
    def test_document_root_element(self):
        xml = build_pain001_xml(_instr())
        assert xml.tag == f"{{{PAIN001_NS}}}Document"

    def test_has_grp_hdr(self):
        xml = build_pain001_xml(_instr())
        grp_hdr = xml.find(f".//p:GrpHdr", NS)
        assert grp_hdr is not None

    def test_grp_hdr_msg_id(self):
        xml = build_pain001_xml(_instr(msg_id="MSG-abc123"))
        msg_id = xml.findtext(f".//p:GrpHdr/p:MsgId", namespaces=NS)
        assert msg_id == "MSG-abc123"

    def test_grp_hdr_nb_of_txs(self):
        xml = build_pain001_xml(_instr(transactions=[_tx(), _tx()]))
        nb = xml.findtext(f".//p:GrpHdr/p:NbOfTxs", namespaces=NS)
        assert nb == "2"

    def test_grp_hdr_ctrl_sum(self):
        xml = build_pain001_xml(_instr(transactions=[
            _tx(amount=Decimal("100.00")),
            _tx(amount=Decimal("250.50")),
        ]))
        ctrl_sum = xml.findtext(f".//p:GrpHdr/p:CtrlSum", namespaces=NS)
        assert ctrl_sum == "350.50"

    def test_has_pmt_inf(self):
        xml = build_pain001_xml(_instr())
        pmt_inf = xml.find(f".//p:PmtInf", NS)
        assert pmt_inf is not None

    def test_pmt_mtd_is_trf(self):
        xml = build_pain001_xml(_instr())
        pmt_mtd = xml.findtext(f".//p:PmtInf/p:PmtMtd", namespaces=NS)
        assert pmt_mtd == "TRF"

    def test_has_cdt_trf_tx_inf(self):
        xml = build_pain001_xml(_instr())
        cdt_trf = xml.find(f".//p:CdtTrfTxInf", NS)
        assert cdt_trf is not None

    def test_multiple_transactions(self):
        xml = build_pain001_xml(_instr(transactions=[_tx(), _tx(), _tx()]))
        cdt_trfs = xml.findall(f".//p:CdtTrfTxInf", NS)
        assert len(cdt_trfs) == 3


# =========================================================================
# Debtor-Elemente
# =========================================================================

class TestDebtorElements:
    def test_debtor_name(self):
        xml = build_pain001_xml(_instr())
        nm = xml.findtext(f".//p:PmtInf/p:Dbtr/p:Nm", namespaces=NS)
        assert nm == "Test AG"

    def test_debtor_iban(self):
        xml = build_pain001_xml(_instr())
        iban = xml.findtext(f".//p:PmtInf/p:DbtrAcct/p:Id/p:IBAN", namespaces=NS)
        assert iban == "CH9300762011623852957"

    def test_debtor_bic(self):
        xml = build_pain001_xml(_instr())
        bic = xml.findtext(f".//p:PmtInf/p:DbtrAgt/p:FinInstnId/p:BICFI", namespaces=NS)
        assert bic == "CRESCHZZ80A"


# =========================================================================
# Creditor-Elemente
# =========================================================================

class TestCreditorElements:
    def test_creditor_name(self):
        xml = build_pain001_xml(_instr())
        nm = xml.findtext(f".//p:CdtTrfTxInf/p:Cdtr/p:Nm", namespaces=NS)
        assert nm == "Creditor AG"

    def test_creditor_iban(self):
        xml = build_pain001_xml(_instr())
        iban = xml.findtext(f".//p:CdtTrfTxInf/p:CdtrAcct/p:Id/p:IBAN", namespaces=NS)
        assert iban == "CH9300762011623852957"

    def test_creditor_bic(self):
        tx = _tx(creditor_bic="BNPAFRPP")
        xml = build_pain001_xml(_instr(transactions=[tx]))
        bic = xml.findtext(f".//p:CdtTrfTxInf/p:CdtrAgt/p:FinInstnId/p:BICFI", namespaces=NS)
        assert bic == "BNPAFRPP"

    def test_creditor_address(self):
        tx = _tx(creditor_address={"StrtNm": "Hauptstr.", "TwnNm": "Zuerich", "Ctry": "CH"})
        xml = build_pain001_xml(_instr(transactions=[tx]))
        town = xml.findtext(f".//p:CdtTrfTxInf/p:Cdtr/p:PstlAdr/p:TwnNm", namespaces=NS)
        assert town == "Zuerich"

    def test_creditor_non_iban_account(self):
        """Non-IBAN Konto: Othr/Id statt IBAN."""
        tx = _tx(
            creditor_iban=None,
            creditor_account_id="123456789012",
            creditor_bic="CHASUS33XXX",
        )
        xml = build_pain001_xml(_instr(transactions=[tx]))
        # Othr/Id muss gesetzt sein
        othr_id = xml.findtext(
            f".//p:CdtTrfTxInf/p:CdtrAcct/p:Id/p:Othr/p:Id", namespaces=NS
        )
        assert othr_id == "123456789012"
        # IBAN darf nicht vorhanden sein
        iban = xml.findtext(
            f".//p:CdtTrfTxInf/p:CdtrAcct/p:Id/p:IBAN", namespaces=NS
        )
        assert iban is None

    def test_creditor_iban_when_no_account_id(self):
        """Wenn kein account_id gesetzt, muss IBAN verwendet werden."""
        tx = _tx(creditor_iban="CH9300762011623852957", creditor_account_id=None)
        xml = build_pain001_xml(_instr(transactions=[tx]))
        iban = xml.findtext(
            f".//p:CdtTrfTxInf/p:CdtrAcct/p:Id/p:IBAN", namespaces=NS
        )
        assert iban == "CH9300762011623852957"
        othr = xml.find(
            f".//p:CdtTrfTxInf/p:CdtrAcct/p:Id/p:Othr", NS
        )
        assert othr is None


# =========================================================================
# Amount
# =========================================================================

class TestAmount:
    def test_amount_value(self):
        tx = _tx(amount=Decimal("1234.56"))
        xml = build_pain001_xml(_instr(transactions=[tx]))
        amt = xml.findtext(f".//p:CdtTrfTxInf/p:Amt/p:InstdAmt", namespaces=NS)
        assert amt == "1234.56"

    def test_amount_currency_attribute(self):
        tx = _tx(currency="EUR")
        xml = build_pain001_xml(_instr(transactions=[tx]))
        instd_amt = xml.find(f".//p:CdtTrfTxInf/p:Amt/p:InstdAmt", NS)
        assert instd_amt.get("Ccy") == "EUR"


# =========================================================================
# Remittance Info
# =========================================================================

class TestRemittanceInfo:
    def test_qrr_reference(self):
        tx = _tx(remittance_info={"type": "QRR", "value": "210000000003139471430009017"})
        xml = build_pain001_xml(_instr(transactions=[tx]))
        # QRR muss als Prtry abgebildet werden (nicht Cd)
        prtry = xml.findtext(
            f".//p:RmtInf/p:Strd/p:CdtrRefInf/p:Tp/p:CdOrPrtry/p:Prtry", namespaces=NS
        )
        assert prtry == "QRR"

    def test_scor_reference(self):
        tx = _tx(remittance_info={"type": "SCOR", "value": "RF18539007547034"})
        xml = build_pain001_xml(_instr(transactions=[tx]))
        cd = xml.findtext(
            f".//p:RmtInf/p:Strd/p:CdtrRefInf/p:Tp/p:CdOrPrtry/p:Cd", namespaces=NS
        )
        assert cd == "SCOR"

    def test_ustrd(self):
        tx = _tx(remittance_info={"type": "USTRD", "value": "Rechnung 2026-001"})
        xml = build_pain001_xml(_instr(transactions=[tx]))
        ustrd = xml.findtext(f".//p:RmtInf/p:Ustrd", namespaces=NS)
        assert ustrd == "Rechnung 2026-001"

    def test_no_remittance(self):
        tx = _tx(remittance_info=None)
        xml = build_pain001_xml(_instr(transactions=[tx]))
        rmt = xml.find(f".//p:RmtInf", NS)
        assert rmt is None


# =========================================================================
# Payment Type Info
# =========================================================================

# =========================================================================
# Purpose
# =========================================================================

class TestPurpose:
    def test_purpose_code_present(self):
        """Purp/Cd wird im XML gesetzt, wenn purpose_code gesetzt ist."""
        tx = _tx(purpose_code="SALA")
        xml = build_pain001_xml(_instr(transactions=[tx]))
        purp = xml.findtext(f".//p:CdtTrfTxInf/p:Purp/p:Cd", namespaces=NS)
        assert purp == "SALA"

    def test_purpose_code_omitted_when_none(self):
        """Purp-Element fehlt, wenn purpose_code nicht gesetzt ist."""
        tx = _tx(purpose_code=None)
        xml = build_pain001_xml(_instr(transactions=[tx]))
        purp = xml.find(f".//p:CdtTrfTxInf/p:Purp", NS)
        assert purp is None

    def test_purpose_code_various_codes(self):
        """Verschiedene Purpose Codes werden korrekt abgebildet."""
        for code in ("SALA", "PENS", "GOVT", "TRAD"):
            tx = _tx(purpose_code=code)
            xml = build_pain001_xml(_instr(transactions=[tx]))
            purp = xml.findtext(f".//p:CdtTrfTxInf/p:Purp/p:Cd", namespaces=NS)
            assert purp == code


class TestPaymentTypeInfo:
    def test_service_level(self):
        xml = build_pain001_xml(_instr(service_level="SEPA"))
        svc = xml.findtext(f".//p:PmtTpInf/p:SvcLvl/p:Cd", namespaces=NS)
        assert svc == "SEPA"

    def test_no_pmt_tp_inf_when_empty(self):
        xml = build_pain001_xml(_instr())
        pmt_tp = xml.find(f".//p:PmtTpInf", NS)
        assert pmt_tp is None

    def test_charge_bearer(self):
        xml = build_pain001_xml(_instr(charge_bearer="SLEV"))
        chrg = xml.findtext(f".//p:PmtInf/p:ChrgBr", namespaces=NS)
        assert chrg == "SLEV"

    def test_category_purpose_present(self):
        """CtgyPurp/Cd wird im XML gesetzt, wenn category_purpose gesetzt ist."""
        xml = build_pain001_xml(_instr(category_purpose="SALA"))
        ctgy = xml.findtext(f".//p:PmtTpInf/p:CtgyPurp/p:Cd", namespaces=NS)
        assert ctgy == "SALA"

    def test_category_purpose_omitted_when_none(self):
        """CtgyPurp-Element fehlt, wenn category_purpose nicht gesetzt ist."""
        xml = build_pain001_xml(_instr())
        ctgy = xml.find(f".//p:PmtTpInf/p:CtgyPurp", NS)
        assert ctgy is None

    def test_category_purpose_various_codes(self):
        """Verschiedene Category Purpose Codes werden korrekt abgebildet."""
        for code in ("SALA", "SECU", "SUPP", "PENS"):
            xml = build_pain001_xml(_instr(category_purpose=code))
            ctgy = xml.findtext(f".//p:PmtTpInf/p:CtgyPurp/p:Cd", namespaces=NS)
            assert ctgy == code

    def test_category_purpose_with_service_level(self):
        """CtgyPurp und SvcLvl koexistieren in PmtTpInf."""
        xml = build_pain001_xml(_instr(service_level="SEPA", category_purpose="SALA"))
        svc = xml.findtext(f".//p:PmtTpInf/p:SvcLvl/p:Cd", namespaces=NS)
        ctgy = xml.findtext(f".//p:PmtTpInf/p:CtgyPurp/p:Cd", namespaces=NS)
        assert svc == "SEPA"
        assert ctgy == "SALA"


# =========================================================================
# Multi-Payment (Pain001Document)
# =========================================================================

class TestMultiPayment:
    def test_multiple_pmt_inf_blocks(self):
        doc = Pain001Document(
            msg_id="MSG-multi",
            cre_dt_tm="2026-03-28T10:00:00",
            initiating_party_name="Test AG",
            payment_instructions=[
                _instr(pmt_inf_id="PMT-A"),
                _instr(pmt_inf_id="PMT-B"),
            ],
        )
        xml = build_pain001_document(doc)
        pmt_infs = xml.findall(f".//p:PmtInf", NS)
        assert len(pmt_infs) == 2

    def test_aggregated_nb_of_txs(self):
        doc = Pain001Document(
            msg_id="MSG-multi",
            cre_dt_tm="2026-03-28T10:00:00",
            initiating_party_name="Test AG",
            payment_instructions=[
                _instr(transactions=[_tx(), _tx()]),
                _instr(transactions=[_tx()]),
            ],
        )
        xml = build_pain001_document(doc)
        nb = xml.findtext(f".//p:GrpHdr/p:NbOfTxs", namespaces=NS)
        assert nb == "3"


# =========================================================================
# Serialisierung
# =========================================================================

class TestSerialization:
    def test_serialize_returns_bytes(self):
        xml = build_pain001_xml(_instr())
        result = serialize_xml(xml)
        assert isinstance(result, bytes)
        assert b"<?xml" in result
        assert b"UTF-8" in result

    def test_serialize_contains_namespace(self):
        xml = build_pain001_xml(_instr())
        result = serialize_xml(xml)
        assert b"pain.001.001.09" in result


# =========================================================================
# XSD-Validierung (Integration)
# =========================================================================

class TestXsdValidation:
    @pytest.fixture
    def xsd_validator(self):
        return XsdValidator("schemas/pain.001.001.09.ch.03.xsd")

    def test_simple_valid_xml(self, xsd_validator):
        xml = build_pain001_xml(_instr())
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"XSD errors: {errors}"

    def test_sepa_with_service_level(self, xsd_validator):
        tx = _tx(currency="EUR", creditor_iban="DE89370400440532013000",
                 creditor_address={"StrtNm": "Str.", "TwnNm": "Berlin", "Ctry": "DE"})
        instr = _instr(service_level="SEPA", charge_bearer="SLEV", transactions=[tx])
        xml = build_pain001_xml(instr)
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"XSD errors: {errors}"

    def test_qrr_as_prtry(self, xsd_validator):
        tx = _tx(remittance_info={"type": "QRR", "value": "210000000003139471430009017"})
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"QRR as Prtry should be XSD-valid: {errors}"

    def test_scor_as_cd(self, xsd_validator):
        tx = _tx(remittance_info={"type": "SCOR", "value": "RF18539007547034"})
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"SCOR as Cd should be XSD-valid: {errors}"

    def test_multi_payment_valid(self, xsd_validator):
        doc = Pain001Document(
            msg_id="MSG-multi",
            cre_dt_tm="2026-03-28T10:00:00",
            initiating_party_name="Test AG",
            payment_instructions=[_instr(pmt_inf_id="PMT-A"), _instr(pmt_inf_id="PMT-B")],
        )
        xml = build_pain001_document(doc)
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"Multi-payment XSD errors: {errors}"

    def test_with_creditor_bic(self, xsd_validator):
        tx = _tx(creditor_bic="BNPAFRPP")
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"XSD errors: {errors}"

    def test_with_uetr(self, xsd_validator):
        tx = _tx(uetr="550e8400-e29b-41d4-a716-446655440000")
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"XSD errors with UETR: {errors}"

    def test_purpose_code_xsd_valid(self, xsd_validator):
        """Purpose/Cd muss XSD-valide sein."""
        tx = _tx(purpose_code="SALA")
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"Purpose Code XSD errors: {errors}"

    def test_category_purpose_xsd_valid(self, xsd_validator):
        """CtgyPurp/Cd muss XSD-valide sein."""
        xml = build_pain001_xml(_instr(category_purpose="SALA"))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"Category Purpose XSD errors: {errors}"

    def test_category_purpose_with_service_level_xsd_valid(self, xsd_validator):
        """PmtTpInf mit SvcLvl und CtgyPurp muss XSD-valide sein."""
        xml = build_pain001_xml(_instr(service_level="SEPA", category_purpose="SUPP"))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"SvcLvl+CtgyPurp XSD errors: {errors}"

    def test_non_iban_account_xsd_valid(self, xsd_validator):
        """Non-IBAN Account (Othr/Id) muss XSD-valide sein."""
        tx = _tx(
            creditor_iban=None,
            creditor_account_id="123456789012",
            creditor_bic="CHASUS33XXX",
        )
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"Non-IBAN XSD errors: {errors}"

    def test_creditor_lei_xsd_valid(self, xsd_validator):
        """Creditor LEI (OrgId/LEI) muss XSD-valide sein."""
        tx = _tx(creditor_lei="5493001KJTIIGC8Y1R12")
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"Creditor LEI XSD errors: {errors}"

    def test_debtor_lei_xsd_valid(self, xsd_validator):
        """Debtor LEI (OrgId/LEI) muss XSD-valide sein."""
        debtor = DebtorInfo(
            name="Test AG", iban="CH9300762011623852957",
            bic="CRESCHZZ80A", lei="5493001KJTIIGC8Y1R12",
        )
        xml = build_pain001_xml(_instr(debtor=debtor))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"Debtor LEI XSD errors: {errors}"


# =========================================================================
# LEI (Legal Entity Identifier) Elemente
# =========================================================================

class TestLeiElements:
    def test_creditor_lei_in_xml(self):
        """Creditor LEI wird als Cdtr/Id/OrgId/LEI abgebildet."""
        tx = _tx(creditor_lei="5493001KJTIIGC8Y1R12")
        xml = build_pain001_xml(_instr(transactions=[tx]))
        lei = xml.findtext(
            f".//p:CdtTrfTxInf/p:Cdtr/p:Id/p:OrgId/p:LEI", namespaces=NS
        )
        assert lei == "5493001KJTIIGC8Y1R12"

    def test_creditor_no_lei_element_when_none(self):
        """Kein Id/OrgId-Element wenn kein LEI gesetzt."""
        tx = _tx(creditor_lei=None)
        xml = build_pain001_xml(_instr(transactions=[tx]))
        org_id = xml.find(f".//p:CdtTrfTxInf/p:Cdtr/p:Id", NS)
        assert org_id is None

    def test_debtor_lei_in_xml(self):
        """Debtor LEI wird als Dbtr/Id/OrgId/LEI abgebildet."""
        debtor = DebtorInfo(
            name="Test AG", iban="CH9300762011623852957",
            bic="CRESCHZZ80A", lei="5493001KJTIIGC8Y1R12",
        )
        xml = build_pain001_xml(_instr(debtor=debtor))
        lei = xml.findtext(
            f".//p:PmtInf/p:Dbtr/p:Id/p:OrgId/p:LEI", namespaces=NS
        )
        assert lei == "5493001KJTIIGC8Y1R12"

    def test_debtor_no_lei_element_when_none(self):
        """Kein Id/OrgId-Element beim Debtor wenn kein LEI gesetzt."""
        xml = build_pain001_xml(_instr())
        org_id = xml.find(f".//p:PmtInf/p:Dbtr/p:Id", NS)
        assert org_id is None


# =========================================================================
# Tax Remittance (TaxRmt)
# =========================================================================

class TestTaxRemittance:
    def test_tax_remittance_basic(self):
        """TaxRmt mit Cdtr, Dbtr, RefNb wird korrekt in RmtInf/Strd abgebildet."""
        tx = _tx(tax_remittance={
            "Cdtr.TaxId": "TAX-AUTH-001",
            "Dbtr.TaxId": "TAXPAYER-123",
            "RefNb": "TAX-REF-2026-001",
            "Mtd": "NORM",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        # Cdtr TaxId
        cdtr_tax_id = xml.findtext(
            ".//p:RmtInf/p:Strd/p:TaxRmt/p:Cdtr/p:TaxId", namespaces=NS
        )
        assert cdtr_tax_id == "TAX-AUTH-001"
        # Dbtr TaxId
        dbtr_tax_id = xml.findtext(
            ".//p:RmtInf/p:Strd/p:TaxRmt/p:Dbtr/p:TaxId", namespaces=NS
        )
        assert dbtr_tax_id == "TAXPAYER-123"
        # RefNb
        ref_nb = xml.findtext(
            ".//p:RmtInf/p:Strd/p:TaxRmt/p:RefNb", namespaces=NS
        )
        assert ref_nb == "TAX-REF-2026-001"
        # Mtd
        mtd = xml.findtext(
            ".//p:RmtInf/p:Strd/p:TaxRmt/p:Mtd", namespaces=NS
        )
        assert mtd == "NORM"

    def test_tax_remittance_with_amount_and_date(self):
        """TaxRmt mit TtlTaxAmt und Dt."""
        tx = _tx(tax_remittance={
            "Cdtr.TaxId": "TAX-001",
            "TtlTaxAmt": "1500.00",
            "TtlTaxAmt.Ccy": "CHF",
            "Dt": "2026-01-15",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        ttl = xml.find(".//p:RmtInf/p:Strd/p:TaxRmt/p:TtlTaxAmt", NS)
        assert ttl is not None
        assert ttl.text == "1500.00"
        assert ttl.get("Ccy") == "CHF"
        dt = xml.findtext(".//p:RmtInf/p:Strd/p:TaxRmt/p:Dt", namespaces=NS)
        assert dt == "2026-01-15"

    def test_tax_remittance_with_admin_zone(self):
        """TaxRmt mit AdmstnZone."""
        tx = _tx(tax_remittance={
            "Cdtr.TaxId": "TAX-001",
            "AdmstnZone": "ZH",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        zone = xml.findtext(
            ".//p:RmtInf/p:Strd/p:TaxRmt/p:AdmstnZone", namespaces=NS
        )
        assert zone == "ZH"

    def test_no_tax_remittance_when_none(self):
        """Kein TaxRmt-Element wenn tax_remittance nicht gesetzt."""
        tx = _tx(tax_remittance=None)
        xml = build_pain001_xml(_instr(transactions=[tx]))
        tax_rmt = xml.find(".//p:TaxRmt", NS)
        assert tax_rmt is None

    def test_tax_remittance_coexists_with_scor_reference(self):
        """TaxRmt und SCOR-Referenz koexistieren im gleichen Strd-Block."""
        tx = _tx(
            remittance_info={"type": "SCOR", "value": "RF18539007547034"},
            tax_remittance={
                "Cdtr.TaxId": "TAX-001",
                "RefNb": "TAX-REF-001",
            },
        )
        xml = build_pain001_xml(_instr(transactions=[tx]))
        # SCOR-Referenz
        cd = xml.findtext(
            ".//p:RmtInf/p:Strd/p:CdtrRefInf/p:Tp/p:CdOrPrtry/p:Cd", namespaces=NS
        )
        assert cd == "SCOR"
        # TaxRmt im gleichen Strd
        ref_nb = xml.findtext(
            ".//p:RmtInf/p:Strd/p:TaxRmt/p:RefNb", namespaces=NS
        )
        assert ref_nb == "TAX-REF-001"

    def test_tax_remittance_without_other_remittance(self):
        """TaxRmt allein (ohne SCOR/QRR/USTRD) erzeugt RmtInf/Strd/TaxRmt."""
        tx = _tx(
            remittance_info=None,
            tax_remittance={"Cdtr.TaxId": "TAX-001", "RefNb": "REF-001"},
        )
        xml = build_pain001_xml(_instr(transactions=[tx]))
        strd = xml.find(".//p:RmtInf/p:Strd", NS)
        assert strd is not None
        ref_nb = xml.findtext(
            ".//p:RmtInf/p:Strd/p:TaxRmt/p:RefNb", namespaces=NS
        )
        assert ref_nb == "REF-001"

    def test_tax_remittance_cdtr_all_fields(self):
        """TaxRmt Cdtr mit TaxId, RegnId und TaxTp."""
        tx = _tx(tax_remittance={
            "Cdtr.TaxId": "TAX-ID-001",
            "Cdtr.RegnId": "REG-001",
            "Cdtr.TaxTp": "VAT",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        cdtr = xml.find(".//p:RmtInf/p:Strd/p:TaxRmt/p:Cdtr", NS)
        assert cdtr is not None
        assert xml.findtext(".//p:RmtInf/p:Strd/p:TaxRmt/p:Cdtr/p:TaxId", namespaces=NS) == "TAX-ID-001"
        assert xml.findtext(".//p:RmtInf/p:Strd/p:TaxRmt/p:Cdtr/p:RegnId", namespaces=NS) == "REG-001"
        assert xml.findtext(".//p:RmtInf/p:Strd/p:TaxRmt/p:Cdtr/p:TaxTp", namespaces=NS) == "VAT"

    def test_tax_remittance_dbtr_all_fields(self):
        """TaxRmt Dbtr mit TaxId, RegnId und TaxTp."""
        tx = _tx(tax_remittance={
            "Dbtr.TaxId": "DBTR-TAX-001",
            "Dbtr.RegnId": "DBTR-REG-001",
            "Dbtr.TaxTp": "INCOME",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        dbtr = xml.find(".//p:RmtInf/p:Strd/p:TaxRmt/p:Dbtr", NS)
        assert dbtr is not None
        assert xml.findtext(".//p:RmtInf/p:Strd/p:TaxRmt/p:Dbtr/p:TaxId", namespaces=NS) == "DBTR-TAX-001"
        assert xml.findtext(".//p:RmtInf/p:Strd/p:TaxRmt/p:Dbtr/p:RegnId", namespaces=NS) == "DBTR-REG-001"
        assert xml.findtext(".//p:RmtInf/p:Strd/p:TaxRmt/p:Dbtr/p:TaxTp", namespaces=NS) == "INCOME"


class TestTaxRemittanceXsdValidation:
    @pytest.fixture
    def xsd_validator(self):
        return XsdValidator("schemas/pain.001.001.09.ch.03.xsd")

    def test_tax_remittance_xsd_valid(self, xsd_validator):
        """TaxRmt-Block muss XSD-valide sein."""
        tx = _tx(tax_remittance={
            "Cdtr.TaxId": "TAX-AUTH-001",
            "Dbtr.TaxId": "TAXPAYER-123",
            "RefNb": "TAX-REF-2026-001",
            "Mtd": "NORM",
            "TtlTaxAmt": "1500.00",
            "TtlTaxAmt.Ccy": "CHF",
            "Dt": "2026-01-15",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"TaxRmt XSD errors: {errors}"

    def test_tax_remittance_with_scor_xsd_valid(self, xsd_validator):
        """TaxRmt + SCOR-Referenz im gleichen Strd muss XSD-valide sein."""
        tx = _tx(
            remittance_info={"type": "SCOR", "value": "RF18539007547034"},
            tax_remittance={
                "Cdtr.TaxId": "TAX-001",
                "Dbtr.TaxId": "PAYER-001",
                "RefNb": "TAX-REF-001",
                "Mtd": "NORM",
            },
        )
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"TaxRmt+SCOR XSD errors: {errors}"

    def test_tax_remittance_minimal_xsd_valid(self, xsd_validator):
        """Minimaler TaxRmt (nur Cdtr.TaxId) muss XSD-valide sein."""
        tx = _tx(tax_remittance={"Cdtr.TaxId": "TAX-001"})
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"Minimal TaxRmt XSD errors: {errors}"

    def test_tax_remittance_with_admin_zone_xsd_valid(self, xsd_validator):
        """TaxRmt mit AdmstnZone muss XSD-valide sein."""
        tx = _tx(tax_remittance={
            "Cdtr.TaxId": "TAX-001",
            "AdmstnZone": "ZH",
            "Dt": "2026-03-01",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"TaxRmt with AdmstnZone XSD errors: {errors}"


# =========================================================================
# Ultimate Debtor / Ultimate Creditor
# =========================================================================

class TestUltimateDebtor:
    def test_b_level_ultmt_dbtr_name(self):
        """UltmtDbtr auf B-Level (PmtInf) mit Name."""
        instr = _instr(ultimate_debtor={"Nm": "Treuhand Meier GmbH"})
        xml = build_pain001_xml(instr)
        nm = xml.findtext(".//p:PmtInf/p:UltmtDbtr/p:Nm", namespaces=NS)
        assert nm == "Treuhand Meier GmbH"

    def test_b_level_ultmt_dbtr_with_address(self):
        """UltmtDbtr auf B-Level mit Name und Adresse."""
        instr = _instr(ultimate_debtor={
            "Nm": "Holding SA",
            "TwnNm": "Zuerich",
            "Ctry": "CH",
        })
        xml = build_pain001_xml(instr)
        nm = xml.findtext(".//p:PmtInf/p:UltmtDbtr/p:Nm", namespaces=NS)
        assert nm == "Holding SA"
        town = xml.findtext(
            ".//p:PmtInf/p:UltmtDbtr/p:PstlAdr/p:TwnNm", namespaces=NS
        )
        assert town == "Zuerich"
        ctry = xml.findtext(
            ".//p:PmtInf/p:UltmtDbtr/p:PstlAdr/p:Ctry", namespaces=NS
        )
        assert ctry == "CH"

    def test_b_level_no_ultmt_dbtr_when_none(self):
        """Kein UltmtDbtr auf B-Level wenn nicht gesetzt."""
        xml = build_pain001_xml(_instr())
        ultmt = xml.find(".//p:PmtInf/p:UltmtDbtr", NS)
        assert ultmt is None

    def test_c_level_ultmt_dbtr_name(self):
        """UltmtDbtr auf C-Level (CdtTrfTxInf) mit Name."""
        tx = _tx(ultimate_debtor={"Nm": "C-Level Auftraggeber"})
        xml = build_pain001_xml(_instr(transactions=[tx]))
        nm = xml.findtext(
            ".//p:CdtTrfTxInf/p:UltmtDbtr/p:Nm", namespaces=NS
        )
        assert nm == "C-Level Auftraggeber"

    def test_c_level_no_ultmt_dbtr_when_none(self):
        """Kein UltmtDbtr auf C-Level wenn nicht gesetzt."""
        tx = _tx(ultimate_debtor=None)
        xml = build_pain001_xml(_instr(transactions=[tx]))
        ultmt = xml.find(".//p:CdtTrfTxInf/p:UltmtDbtr", NS)
        assert ultmt is None


class TestUltimateCreditor:
    def test_ultmt_cdtr_name(self):
        """UltmtCdtr auf C-Level mit Name."""
        tx = _tx(ultimate_creditor={"Nm": "Endbeguenstigter Verein"})
        xml = build_pain001_xml(_instr(transactions=[tx]))
        nm = xml.findtext(
            ".//p:CdtTrfTxInf/p:UltmtCdtr/p:Nm", namespaces=NS
        )
        assert nm == "Endbeguenstigter Verein"

    def test_ultmt_cdtr_with_address(self):
        """UltmtCdtr auf C-Level mit Name und Adresse."""
        tx = _tx(ultimate_creditor={
            "Nm": "Stiftung Kinderhilfe",
            "TwnNm": "Wien",
            "Ctry": "AT",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        nm = xml.findtext(
            ".//p:CdtTrfTxInf/p:UltmtCdtr/p:Nm", namespaces=NS
        )
        assert nm == "Stiftung Kinderhilfe"
        town = xml.findtext(
            ".//p:CdtTrfTxInf/p:UltmtCdtr/p:PstlAdr/p:TwnNm", namespaces=NS
        )
        assert town == "Wien"

    def test_no_ultmt_cdtr_when_none(self):
        """Kein UltmtCdtr wenn nicht gesetzt."""
        tx = _tx(ultimate_creditor=None)
        xml = build_pain001_xml(_instr(transactions=[tx]))
        ultmt = xml.find(".//p:CdtTrfTxInf/p:UltmtCdtr", NS)
        assert ultmt is None

    def test_both_ultmt_dbtr_and_cdtr(self):
        """UltmtDbtr (B-Level) und UltmtCdtr (C-Level) gleichzeitig."""
        tx = _tx(ultimate_creditor={"Nm": "Ultimate Cdtr"})
        instr = _instr(
            ultimate_debtor={"Nm": "Ultimate Dbtr"},
            transactions=[tx],
        )
        xml = build_pain001_xml(instr)
        dbtr_nm = xml.findtext(".//p:PmtInf/p:UltmtDbtr/p:Nm", namespaces=NS)
        assert dbtr_nm == "Ultimate Dbtr"
        cdtr_nm = xml.findtext(
            ".//p:CdtTrfTxInf/p:UltmtCdtr/p:Nm", namespaces=NS
        )
        assert cdtr_nm == "Ultimate Cdtr"


class TestUltimatePartiesXsdValidation:
    @pytest.fixture
    def xsd_validator(self):
        return XsdValidator("schemas/pain.001.001.09.ch.03.xsd")

    def test_b_level_ultmt_dbtr_xsd_valid(self, xsd_validator):
        """UltmtDbtr auf B-Level muss XSD-valide sein."""
        instr = _instr(ultimate_debtor={
            "Nm": "Treuhand Meier GmbH",
            "TwnNm": "Zuerich",
            "Ctry": "CH",
        })
        xml = build_pain001_xml(instr)
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"B-Level UltmtDbtr XSD errors: {errors}"

    def test_c_level_ultmt_dbtr_xsd_valid(self, xsd_validator):
        """UltmtDbtr auf C-Level muss XSD-valide sein."""
        tx = _tx(ultimate_debtor={
            "Nm": "C-Level Auftraggeber",
            "TwnNm": "Bern",
            "Ctry": "CH",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"C-Level UltmtDbtr XSD errors: {errors}"

    def test_ultmt_cdtr_xsd_valid(self, xsd_validator):
        """UltmtCdtr auf C-Level muss XSD-valide sein."""
        tx = _tx(ultimate_creditor={
            "Nm": "Endbeguenstigter",
            "TwnNm": "Berlin",
            "Ctry": "DE",
        })
        xml = build_pain001_xml(_instr(transactions=[tx]))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"UltmtCdtr XSD errors: {errors}"

    def test_both_ultmt_parties_xsd_valid(self, xsd_validator):
        """UltmtDbtr (B-Level) + UltmtCdtr (C-Level) zusammen XSD-valide."""
        tx = _tx(ultimate_creditor={
            "Nm": "Stiftung Alpha",
            "TwnNm": "Wien",
            "Ctry": "AT",
        })
        instr = _instr(
            ultimate_debtor={
                "Nm": "Holding International SA",
                "TwnNm": "Basel",
                "Ctry": "CH",
            },
            transactions=[tx],
        )
        xml = build_pain001_xml(instr)
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"Both UltmtDbtr+UltmtCdtr XSD errors: {errors}"

    def test_ultmt_dbtr_name_only_xsd_valid(self, xsd_validator):
        """UltmtDbtr nur mit Name (ohne Adresse) muss XSD-valide sein."""
        instr = _instr(ultimate_debtor={"Nm": "Einfacher Name"})
        xml = build_pain001_xml(instr)
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"UltmtDbtr name-only XSD errors: {errors}"


# =========================================================================
# Batch Booking (BtchBookg)
# =========================================================================

class TestBatchBooking:
    def test_batch_booking_true(self):
        """BtchBookg=true wird im XML gesetzt."""
        xml = build_pain001_xml(_instr(batch_booking=True))
        btch = xml.findtext(f".//p:PmtInf/p:BtchBookg", namespaces=NS)
        assert btch == "true"

    def test_batch_booking_false(self):
        """BtchBookg=false wird im XML gesetzt."""
        xml = build_pain001_xml(_instr(batch_booking=False))
        btch = xml.findtext(f".//p:PmtInf/p:BtchBookg", namespaces=NS)
        assert btch == "false"

    def test_batch_booking_none_omitted(self):
        """BtchBookg-Element fehlt wenn None (nicht gesetzt)."""
        xml = build_pain001_xml(_instr(batch_booking=None))
        btch = xml.find(f".//p:PmtInf/p:BtchBookg", NS)
        assert btch is None

    def test_batch_booking_position_after_pmt_mtd(self):
        """BtchBookg muss nach PmtMtd und vor NbOfTxs stehen (XSD-Reihenfolge)."""
        xml = build_pain001_xml(_instr(batch_booking=True))
        pmt_inf = xml.find(f".//p:PmtInf", NS)
        children = [child.tag.split("}")[-1] for child in pmt_inf]
        btch_idx = children.index("BtchBookg")
        pmt_mtd_idx = children.index("PmtMtd")
        assert btch_idx > pmt_mtd_idx, "BtchBookg muss nach PmtMtd stehen"
        # NbOfTxs ist optional, aber wenn vorhanden, muss BtchBookg davor sein
        if "NbOfTxs" in children:
            nb_idx = children.index("NbOfTxs")
            assert btch_idx < nb_idx, "BtchBookg muss vor NbOfTxs stehen"


class TestBatchBookingXsdValidation:
    @pytest.fixture
    def xsd_validator(self):
        return XsdValidator("schemas/pain.001.001.09.ch.03.xsd")

    def test_batch_booking_true_xsd_valid(self, xsd_validator):
        """BtchBookg=true muss XSD-valide sein."""
        xml = build_pain001_xml(_instr(batch_booking=True))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"BtchBookg=true XSD errors: {errors}"

    def test_batch_booking_false_xsd_valid(self, xsd_validator):
        """BtchBookg=false muss XSD-valide sein."""
        xml = build_pain001_xml(_instr(batch_booking=False))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"BtchBookg=false XSD errors: {errors}"

    def test_batch_booking_omitted_xsd_valid(self, xsd_validator):
        """Ohne BtchBookg muss XSD-valide sein."""
        xml = build_pain001_xml(_instr(batch_booking=None))
        is_valid, errors = xsd_validator.validate(xml)
        assert is_valid, f"BtchBookg omitted XSD errors: {errors}"
