"""Tests fuer pacs.008 XML Builders + XSD Validation."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from lxml import etree

from src.models.pacs008 import (
    AccountInfo,
    AgentInfo,
    ChargesInfo,
    Pacs008BusinessMessage,
    Pacs008Instruction,
    Pacs008Transaction,
    PartyInfo,
    PostalAddress,
    SettlementMethod,
)
from src.xml_generator.pacs008.builders import (
    _fmt_amount,
    build_agent,
    build_cash_account,
    build_cdt_trf_tx_inf,
    build_charges_info,
    build_group_header,
    build_party,
    build_postal_address,
    build_settlement_info,
)
from src.xml_generator.pacs008.message_builder import (
    build_bah,
    build_business_message,
    build_document,
    serialize,
    serialize_document_only,
)
from src.xml_generator.pacs008.namespaces import HEAD_NS, PACS008_NS

NS = {"p": PACS008_NS, "h": HEAD_NS}

PACS008_XSD = "schemas/pacs.008/CBPRPlus_SR2026_(Combined)_CBPRPlus-pacs_008_001_08_FIToFICustomerCreditTransfer_20260319_1152_iso15enriched.xsd"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _swiss_address():
    return PostalAddress(
        street_name="Bahnhofstrasse",
        building_number="42",
        postal_code="8001",
        town_name="Zurich",
        country="CH",
    )


def _german_address():
    return PostalAddress(
        street_name="Unter den Linden",
        building_number="7",
        postal_code="10117",
        town_name="Berlin",
        country="DE",
    )


def _minimal_instruction() -> Pacs008Instruction:
    ubs = AgentInfo(bic="UBSWCHZH80A")
    deut = AgentInfo(bic="DEUTDEFFXXX")
    dbtr = PartyInfo(name="Muster AG", postal_address=_swiss_address())
    cdtr = PartyInfo(name="Empfaenger GmbH", postal_address=_german_address())
    tx = Pacs008Transaction(
        end_to_end_id="E2E-TEST-001",
        uetr="8a562c67-ca16-48ba-b074-65581be6f001",
        instructed_amount=Decimal("1000.00"),
        instructed_currency="EUR",
        charge_bearer="SHAR",
        debtor=dbtr,
        debtor_account=AccountInfo(iban="CH5604835012345678009"),
        debtor_agent=ubs,
        creditor=cdtr,
        creditor_account=AccountInfo(iban="DE89370400440532013000"),
        creditor_agent=deut,
    )
    return Pacs008Instruction(
        msg_id="MSG-TEST-001",
        cre_dt_tm="2026-04-06T14:30:00+00:00",
        number_of_transactions=1,
        control_sum=Decimal("1000.00"),
        interbank_settlement_date="2026-04-08",
        instructing_agent=ubs,
        instructed_agent=deut,
        transactions=[tx],
    )


def _business_message(instruction=None) -> Pacs008BusinessMessage:
    instruction = instruction or _minimal_instruction()
    return Pacs008BusinessMessage(
        bah_from_bic="UBSWCHZH80A",
        bah_to_bic="DEUTDEFFXXX",
        bah_biz_msg_idr=instruction.msg_id,
        bah_cre_dt="2026-04-06T14:30:00+00:00",
        instruction=instruction,
    )


# ---------------------------------------------------------------------------
# Element-level Builders
# ---------------------------------------------------------------------------

class TestElementBuilders:
    def test_postal_address_ordering(self):
        root = etree.Element(f"{{{PACS008_NS}}}X")
        build_postal_address(root, _swiss_address())
        children = [c.tag.split("}")[-1] for c in root[0]]
        assert children == ["StrtNm", "BldgNb", "PstCd", "TwnNm", "Ctry"]

    def test_agent_bic_only(self):
        root = etree.Element(f"{{{PACS008_NS}}}X")
        build_agent(root, "DbtrAgt", AgentInfo(bic="UBSWCHZH80A"))
        bic = root.findtext(".//p:DbtrAgt/p:FinInstnId/p:BICFI", namespaces=NS)
        assert bic == "UBSWCHZH80A"

    def test_agent_with_clr_sys(self):
        root = etree.Element(f"{{{PACS008_NS}}}X")
        agent = AgentInfo(
            clearing_system_code="USABA", clearing_member_id="021000021"
        )
        build_agent(root, "CdtrAgt", agent)
        mmb = root.findtext(".//p:CdtrAgt/p:FinInstnId/p:ClrSysMmbId/p:MmbId", namespaces=NS)
        cd = root.findtext(
            ".//p:CdtrAgt/p:FinInstnId/p:ClrSysMmbId/p:ClrSysId/p:Cd", namespaces=NS
        )
        assert mmb == "021000021"
        assert cd == "USABA"

    def test_party_with_lei(self):
        root = etree.Element(f"{{{PACS008_NS}}}X")
        party = PartyInfo(
            name="Test AG",
            postal_address=_swiss_address(),
            lei="506700GE1G29325QX363",
        )
        build_party(root, "Dbtr", party)
        lei_id = root.findtext(
            ".//p:Dbtr/p:Id/p:OrgId/p:Othr/p:Id", namespaces=NS
        )
        scheme = root.findtext(
            ".//p:Dbtr/p:Id/p:OrgId/p:Othr/p:SchmeNm/p:Cd", namespaces=NS
        )
        assert lei_id == "506700GE1G29325QX363"
        assert scheme == "LEI"

    def test_cash_account_iban(self):
        root = etree.Element(f"{{{PACS008_NS}}}X")
        build_cash_account(
            root, "DbtrAcct", AccountInfo(iban="CH5604835012345678009")
        )
        iban = root.findtext(".//p:DbtrAcct/p:Id/p:IBAN", namespaces=NS)
        assert iban == "CH5604835012345678009"

    def test_cash_account_other(self):
        root = etree.Element(f"{{{PACS008_NS}}}X")
        build_cash_account(
            root, "CdtrAcct",
            AccountInfo(other_id="12345", other_scheme_code="BBAN"),
        )
        oid = root.findtext(".//p:CdtrAcct/p:Id/p:Othr/p:Id", namespaces=NS)
        cd = root.findtext(
            ".//p:CdtrAcct/p:Id/p:Othr/p:SchmeNm/p:Cd", namespaces=NS
        )
        assert oid == "12345"
        assert cd == "BBAN"

    def test_charges_info(self):
        root = etree.Element(f"{{{PACS008_NS}}}X")
        ci = ChargesInfo(
            amount=Decimal("10.00"), currency="EUR",
            agent=AgentInfo(bic="DEUTDEFFXXX"),
        )
        build_charges_info(root, ci)
        amt = root.find(".//p:ChrgsInf/p:Amt", NS)
        assert amt.text == "10.00"
        assert amt.get("Ccy") == "EUR"
        agt_bic = root.findtext(
            ".//p:ChrgsInf/p:Agt/p:FinInstnId/p:BICFI", namespaces=NS
        )
        assert agt_bic == "DEUTDEFFXXX"

    def test_settlement_info(self):
        root = etree.Element(f"{{{PACS008_NS}}}X")
        build_settlement_info(root, SettlementMethod.INDA)
        mtd = root.findtext(".//p:SttlmInf/p:SttlmMtd", namespaces=NS)
        assert mtd == "INDA"


# ---------------------------------------------------------------------------
# Message-Level Builders
# ---------------------------------------------------------------------------

class TestDocumentBuilder:
    def test_document_root_namespace(self):
        instr = _minimal_instruction()
        doc = build_document(instr)
        assert doc.tag == f"{{{PACS008_NS}}}Document"
        assert len(doc) == 1  # one FIToFICstmrCdtTrf

    def test_group_header_fields(self):
        instr = _minimal_instruction()
        doc = build_document(instr)
        msg_id = doc.findtext(".//p:GrpHdr/p:MsgId", namespaces=NS)
        nb = doc.findtext(".//p:GrpHdr/p:NbOfTxs", namespaces=NS)
        mtd = doc.findtext(".//p:GrpHdr/p:SttlmInf/p:SttlmMtd", namespaces=NS)
        assert msg_id == "MSG-TEST-001"
        assert nb == "1"
        assert mtd == "INDA"

    def test_cdt_trf_tx_inf_fields(self):
        instr = _minimal_instruction()
        doc = build_document(instr)
        e2e = doc.findtext(".//p:CdtTrfTxInf/p:PmtId/p:EndToEndId", namespaces=NS)
        uetr = doc.findtext(".//p:CdtTrfTxInf/p:PmtId/p:UETR", namespaces=NS)
        amt = doc.find(".//p:CdtTrfTxInf/p:IntrBkSttlmAmt", NS)
        chrg_br = doc.findtext(".//p:CdtTrfTxInf/p:ChrgBr", namespaces=NS)
        dbtr = doc.findtext(".//p:CdtTrfTxInf/p:Dbtr/p:Nm", namespaces=NS)
        cdtr = doc.findtext(".//p:CdtTrfTxInf/p:Cdtr/p:Nm", namespaces=NS)
        assert e2e == "E2E-TEST-001"
        assert uetr == "8a562c67-ca16-48ba-b074-65581be6f001"
        assert amt.text == "1000.00"
        assert amt.get("Ccy") == "EUR"
        assert chrg_br == "SHAR"
        assert dbtr == "Muster AG"
        assert cdtr == "Empfaenger GmbH"

    def test_settlement_date_propagated(self):
        instr = _minimal_instruction()
        doc = build_document(instr)
        sttlm_dt = doc.findtext(".//p:CdtTrfTxInf/p:IntrBkSttlmDt", namespaces=NS)
        assert sttlm_dt == "2026-04-08"

    def test_instg_and_instd_on_c_level(self):
        instr = _minimal_instruction()
        doc = build_document(instr)
        instg = doc.findtext(
            ".//p:CdtTrfTxInf/p:InstgAgt/p:FinInstnId/p:BICFI", namespaces=NS
        )
        instd = doc.findtext(
            ".//p:CdtTrfTxInf/p:InstdAgt/p:FinInstnId/p:BICFI", namespaces=NS
        )
        assert instg == "UBSWCHZH80A"
        assert instd == "DEUTDEFFXXX"


class TestBAHBuilder:
    def test_bah_fields(self):
        bah = build_bah(
            from_bic="UBSWCHZH80A",
            to_bic="DEUTDEFFXXX",
            biz_msg_idr="MSG-TEST-001",
            cre_dt="2026-04-06T14:30:00+00:00",
        )
        assert bah.tag == f"{{{HEAD_NS}}}AppHdr"
        from_bic = bah.findtext(".//h:Fr/h:FIId/h:FinInstnId/h:BICFI", namespaces=NS)
        to_bic = bah.findtext(".//h:To/h:FIId/h:FinInstnId/h:BICFI", namespaces=NS)
        biz_msg = bah.findtext("h:BizMsgIdr", namespaces=NS)
        msg_def = bah.findtext("h:MsgDefIdr", namespaces=NS)
        biz_svc = bah.findtext("h:BizSvc", namespaces=NS)
        assert from_bic == "UBSWCHZH80A"
        assert to_bic == "DEUTDEFFXXX"
        assert biz_msg == "MSG-TEST-001"
        assert msg_def == "pacs.008.001.08"
        assert biz_svc == "swift.cbprplus.02"


class TestBusinessMessageAssembly:
    def test_wrapper_has_apphdr_and_document(self):
        bm = _business_message()
        wrapper = build_business_message(bm)
        assert wrapper.tag == "BusinessMessage"
        children = [c.tag for c in wrapper]
        assert children[0] == f"{{{HEAD_NS}}}AppHdr"
        assert children[1] == f"{{{PACS008_NS}}}Document"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_document_only_is_parseable(self):
        instr = _minimal_instruction()
        xml_bytes = serialize_document_only(instr)
        parsed = etree.fromstring(xml_bytes)
        assert parsed.tag == f"{{{PACS008_NS}}}Document"

    def test_business_message_is_parseable(self):
        bm = _business_message()
        wrapper = build_business_message(bm)
        xml_bytes = serialize(wrapper)
        parsed = etree.fromstring(xml_bytes)
        assert parsed.tag == "BusinessMessage"
        assert len(parsed) == 2

    def test_has_xml_declaration(self):
        bm = _business_message()
        xml_bytes = serialize(build_business_message(bm))
        assert xml_bytes.startswith(b"<?xml")


# ---------------------------------------------------------------------------
# XSD Validation
# ---------------------------------------------------------------------------

class TestXsdValidation:
    def test_minimal_document_is_xsd_valid(self):
        import os
        if not os.path.exists(PACS008_XSD):
            pytest.skip("pacs.008 CBPR+ XSD not present (gitignored)")
        xsd_doc = etree.parse(PACS008_XSD)
        xsd = etree.XMLSchema(xsd_doc)
        instr = _minimal_instruction()
        doc = build_document(instr)
        is_valid = xsd.validate(doc)
        errors = [str(e) for e in xsd.error_log]
        assert is_valid, f"XSD validation failed:\n" + "\n".join(errors[:15])
