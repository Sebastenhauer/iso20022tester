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
