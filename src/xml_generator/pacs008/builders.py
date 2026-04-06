"""Element-Builder fuer pacs.008.001.08 (CBPR+ Flavor SR2026).

Baut einzelne Document-Bloecke (GrpHdr, SttlmInf, Party, Agent,
Account, Charges, CdtTrfTxInf) im `urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08`
Namespace. Die Element-Reihenfolge ist strikt nach dem XSD sortiert,
da CBPR+ Instance-Validierung jede Abweichung ablehnt.

Die Funktionen schreiben per SubElement in einen uebergebenen
`parent`; sie liefern keinen Rueckgabewert (ausser dem neu erzeugten
Element fuer Verschachtelung).
"""

from decimal import Decimal
from typing import List, Optional

from lxml import etree

from src.models.pacs008 import (
    AccountInfo,
    AgentInfo,
    ChargesInfo,
    Pacs008Instruction,
    Pacs008Transaction,
    PartyInfo,
    PostalAddress,
    SettlementMethod,
)
from src.xml_generator.pacs008.namespaces import PACS008_NS


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _el(parent, tag: str, text: Optional[str] = None) -> etree._Element:
    """Erzeugt ein SubElement im pacs.008 Namespace."""
    elem = etree.SubElement(parent, f"{{{PACS008_NS}}}{tag}")
    if text is not None:
        elem.text = str(text)
    return elem


def _el_with_attr(parent, tag: str, text: str, attrs: dict) -> etree._Element:
    elem = etree.SubElement(parent, f"{{{PACS008_NS}}}{tag}")
    elem.text = text
    for k, v in attrs.items():
        elem.set(k, v)
    return elem


# ---------------------------------------------------------------------------
# PostalAddress24 (PstlAdr)
# ---------------------------------------------------------------------------

def build_postal_address(parent: etree._Element, addr: PostalAddress) -> etree._Element:
    """Baut ein PstlAdr-Element mit strukturierten Feldern.

    XSD-Reihenfolge (PostalAddress24 subset): StrtNm, BldgNb, PstCd, TwnNm, Ctry.
    """
    pst_adr = _el(parent, "PstlAdr")
    if addr.street_name:
        _el(pst_adr, "StrtNm", addr.street_name)
    if addr.building_number:
        _el(pst_adr, "BldgNb", addr.building_number)
    if addr.postal_code:
        _el(pst_adr, "PstCd", addr.postal_code)
    if addr.town_name:
        _el(pst_adr, "TwnNm", addr.town_name)
    if addr.country:
        _el(pst_adr, "Ctry", addr.country)
    return pst_adr


# ---------------------------------------------------------------------------
# BranchAndFinancialInstitutionIdentification6 (Agent)
# ---------------------------------------------------------------------------

def build_agent(parent: etree._Element, tag_name: str, agent: AgentInfo) -> etree._Element:
    """Baut ein Agent-Element (DbtrAgt, CdtrAgt, InstgAgt, InstdAgt, IntrmyAgt*).

    Struktur: <TagName><FinInstnId>...</FinInstnId></TagName>.
    FinInstnId enthaelt BICFI und/oder ClrSysMmbId (mindestens eines
    muss gesetzt sein, sonst ist der Agent ungueltig; die Validierung
    prueft das separat).

    XSD-Reihenfolge innerhalb FinInstnId:
    BICFI, ClrSysMmbId, Nm, PstlAdr, Othr.
    """
    agt = _el(parent, tag_name)
    fin_instn_id = _el(agt, "FinInstnId")

    if agent.bic:
        _el(fin_instn_id, "BICFI", agent.bic)

    if agent.clearing_member_id:
        clr_sys = _el(fin_instn_id, "ClrSysMmbId")
        # ClrSysId ist Pflicht in CBPR+ (XSD min=1). Wenn der User keinen
        # Code mitgibt, setzen wir einen Default, der haeufig fuer die
        # USA Fedwire verwendet wird.
        clr_sys_id = _el(clr_sys, "ClrSysId")
        _el(clr_sys_id, "Cd", agent.clearing_system_code or "USABA")
        _el(clr_sys, "MmbId", agent.clearing_member_id)

    if agent.name:
        _el(fin_instn_id, "Nm", agent.name)

    if agent.postal_address and not agent.postal_address.is_empty():
        build_postal_address(fin_instn_id, agent.postal_address)

    return agt


# ---------------------------------------------------------------------------
# PartyIdentification135 (Dbtr, Cdtr, UltmtDbtr, UltmtCdtr, InitgPty)
# ---------------------------------------------------------------------------

def build_party(parent: etree._Element, tag_name: str, party: PartyInfo) -> etree._Element:
    """Baut ein Party-Element (Dbtr, Cdtr, UltmtDbtr, UltmtCdtr).

    XSD-Reihenfolge: Nm, PstlAdr, Id, CtryOfRes, CtctDtls.
    Id wird bei LEI als Id/OrgId/Othr/Id+SchmeNm/Cd=LEI abgebildet
    (SPS CH21-konform, wie beim pain.001 Builder).
    """
    pty = _el(parent, tag_name)
    _el(pty, "Nm", party.name)

    if party.postal_address and not party.postal_address.is_empty():
        build_postal_address(pty, party.postal_address)

    # Id/OrgId fuer LEI (ISO 17442 via Othr/SchmeNm/Cd=LEI)
    if party.lei or party.organisation_other_id:
        party_id = _el(pty, "Id")
        org_id = _el(party_id, "OrgId")
        othr = _el(org_id, "Othr")
        id_val = party.lei or party.organisation_other_id
        _el(othr, "Id", id_val)
        schme_nm = _el(othr, "SchmeNm")
        scheme_code = party.organisation_other_scheme or ("LEI" if party.lei else None)
        if scheme_code:
            _el(schme_nm, "Cd", scheme_code)

    if party.country_of_residence:
        _el(pty, "CtryOfRes", party.country_of_residence)

    return pty


# ---------------------------------------------------------------------------
# CashAccount38 (DbtrAcct, CdtrAcct, SttlmAcct, IntrmyAgt1Acct, ...)
# ---------------------------------------------------------------------------

def build_cash_account(
    parent: etree._Element, tag_name: str, account: AccountInfo
) -> etree._Element:
    """Baut ein CashAccount38-Element.

    XSD-Reihenfolge innerhalb CashAccount38: Id, Tp, Ccy, Nm, Prxy.
    Innerhalb Id wird IBAN oder Othr (mit SchmeNm) verwendet.
    """
    acct = _el(parent, tag_name)
    id_el = _el(acct, "Id")
    if account.iban:
        _el(id_el, "IBAN", account.iban)
    elif account.other_id:
        othr = _el(id_el, "Othr")
        _el(othr, "Id", account.other_id)
        if account.other_scheme_code:
            schme_nm = _el(othr, "SchmeNm")
            _el(schme_nm, "Cd", account.other_scheme_code)
    if account.currency:
        _el(acct, "Ccy", account.currency)
    return acct


# ---------------------------------------------------------------------------
# Charges7 (ChrgsInf)
# ---------------------------------------------------------------------------

def build_charges_info(
    parent: etree._Element, charges: ChargesInfo
) -> etree._Element:
    """Baut ein ChrgsInf-Element (Charges7).

    XSD-Reihenfolge: Amt, Agt.
    """
    ci = _el(parent, "ChrgsInf")
    _el_with_attr(
        ci, "Amt",
        _fmt_amount(charges.amount, charges.currency),
        {"Ccy": charges.currency},
    )
    build_agent(ci, "Agt", charges.agent)
    return ci


# ---------------------------------------------------------------------------
# Remittance Information
# ---------------------------------------------------------------------------

def build_remittance_info(
    parent: etree._Element, remittance: dict
) -> Optional[etree._Element]:
    """Baut ein RmtInf-Element.

    Erwartete Keys:
    - {"type": "USTRD", "value": "..."}  -> unstructured Ustrd
    """
    if not remittance:
        return None
    rmt_inf = _el(parent, "RmtInf")
    if remittance.get("type") == "USTRD" and remittance.get("value"):
        _el(rmt_inf, "Ustrd", remittance["value"])
    return rmt_inf


# ---------------------------------------------------------------------------
# PmtId (PaymentIdentification7)
# ---------------------------------------------------------------------------

def build_payment_id(
    parent: etree._Element,
    instruction_id: Optional[str],
    end_to_end_id: str,
    tx_id: Optional[str],
    uetr: str,
) -> etree._Element:
    """Baut PmtId. Reihenfolge: InstrId, EndToEndId, TxId, UETR, ClrSysRef.

    InstrId ist in CBPR+ Pflicht (min=1). Wenn der Caller keinen
    InstrId liefert, wird der EndToEndId als Fallback verwendet.
    """
    pmt_id = _el(parent, "PmtId")
    _el(pmt_id, "InstrId", instruction_id or end_to_end_id)
    _el(pmt_id, "EndToEndId", end_to_end_id)
    if tx_id:
        _el(pmt_id, "TxId", tx_id)
    _el(pmt_id, "UETR", uetr)
    return pmt_id


# ---------------------------------------------------------------------------
# Settlement Info (GrpHdr/SttlmInf)
# ---------------------------------------------------------------------------

def build_settlement_info(
    parent: etree._Element,
    settlement_method: SettlementMethod,
    settlement_account: Optional[AccountInfo] = None,
) -> etree._Element:
    """Baut SttlmInf (SettlementInstruction7).

    XSD-Reihenfolge: SttlmMtd, SttlmAcct, InstgRmbrsmntAgt, InstgRmbrsmntAgtAcct, ...
    V1 unterstuetzt nur SttlmMtd + optional SttlmAcct.
    """
    sttlm_inf = _el(parent, "SttlmInf")
    _el(sttlm_inf, "SttlmMtd", settlement_method.value)
    if settlement_account and settlement_account.has_id:
        build_cash_account(sttlm_inf, "SttlmAcct", settlement_account)
    return sttlm_inf


# ---------------------------------------------------------------------------
# Group Header
# ---------------------------------------------------------------------------

def build_group_header(
    parent: etree._Element, instruction: Pacs008Instruction
) -> etree._Element:
    """Baut GroupHeader93 (CBPR+: MsgId, CreDtTm, NbOfTxs, SttlmInf).

    XSD-Reihenfolge: MsgId, CreDtTm, NbOfTxs, (CtrlSum,) SttlmInf.
    In CBPR+ ist CtrlSum NICHT Bestandteil des GrpHdr (siehe XSD:
    GroupHeader93__1 enthaelt nur die vier obigen Felder).
    """
    grp_hdr = _el(parent, "GrpHdr")
    _el(grp_hdr, "MsgId", instruction.msg_id)
    _el(grp_hdr, "CreDtTm", instruction.cre_dt_tm)
    _el(grp_hdr, "NbOfTxs", str(instruction.number_of_transactions))
    build_settlement_info(grp_hdr, instruction.settlement_method, instruction.settlement_account)
    return grp_hdr


# ---------------------------------------------------------------------------
# Credit Transfer Transaction Information (C-Level)
# ---------------------------------------------------------------------------

def build_cdt_trf_tx_inf(
    parent: etree._Element, tx: Pacs008Transaction
) -> etree._Element:
    """Baut ein CdtTrfTxInf-Element (CreditTransferTransaction39 in CBPR+).

    Strikte XSD-Reihenfolge gemaess SR2026 enriched schema:
    PmtId, PmtTpInf, IntrBkSttlmAmt, IntrBkSttlmDt, SttlmPrty,
    SttlmTmIndctn, SttlmTmReq, InstdAmt, XchgRate, ChrgBr, ChrgsInf*,
    PrvsInstgAgt1/2/3(+Acct), InstgAgt, InstdAgt,
    IntrmyAgt1/2/3(+Acct), UltmtDbtr, InitgPty, Dbtr, DbtrAcct,
    DbtrAgt, DbtrAgtAcct, CdtrAgt, CdtrAgtAcct, Cdtr, CdtrAcct,
    UltmtCdtr, InstrForCdtrAgt, InstrForNxtAgt, Purp, RgltryRptg*,
    RltdRmtInf, RmtInf.
    """
    cdt_tx = _el(parent, "CdtTrfTxInf")

    # PmtId
    build_payment_id(
        cdt_tx,
        instruction_id=tx.instruction_id,
        end_to_end_id=tx.end_to_end_id,
        tx_id=tx.tx_id,
        uetr=tx.uetr,
    )

    # PmtTpInf (optional, nur wenn eines der Felder gesetzt ist)
    if tx.service_level or tx.local_instrument or tx.category_purpose:
        pmt_tp_inf = _el(cdt_tx, "PmtTpInf")
        if tx.service_level:
            svc = _el(pmt_tp_inf, "SvcLvl")
            _el(svc, "Cd", tx.service_level)
        if tx.local_instrument:
            lcl = _el(pmt_tp_inf, "LclInstrm")
            _el(lcl, "Cd", tx.local_instrument)
        if tx.category_purpose:
            cat = _el(pmt_tp_inf, "CtgyPurp")
            _el(cat, "Cd", tx.category_purpose)

    # IntrBkSttlmAmt
    sttlm_amt = tx.interbank_settlement_amount or tx.instructed_amount
    sttlm_ccy = tx.interbank_settlement_currency or tx.instructed_currency
    _el_with_attr(
        cdt_tx, "IntrBkSttlmAmt",
        _fmt_amount(sttlm_amt, sttlm_ccy),
        {"Ccy": sttlm_ccy},
    )

    # IntrBkSttlmDt wird auf Instruction-Ebene gehalten und vom Message-
    # Builder vorher in die Transaction gespiegelt. Hier direkt setzen
    # waere falsch, deswegen pruefen wir, ob der Caller die Info
    # anders weitergibt. Wir injizieren sie aus der Instruction durch
    # build_pacs008_document.

    # Platzhalter: der Caller (build_pacs008_document) setzt den Wert
    # direkt nach diesem Element, indem er tx.interbank_settlement_date
    # verwendet. Da wir hier kein Zugriff haben, muss die Info in tx
    # stehen. Wir verwenden ein transientes Attribut auf tx falls nicht
    # explizit gesetzt:
    settlement_date = getattr(tx, "_settlement_date_iso", None)
    if settlement_date:
        _el(cdt_tx, "IntrBkSttlmDt", settlement_date)

    # InstdAmt
    _el_with_attr(
        cdt_tx, "InstdAmt",
        _fmt_amount(tx.instructed_amount, tx.instructed_currency),
        {"Ccy": tx.instructed_currency},
    )

    # ChrgBr (Pflicht)
    _el(cdt_tx, "ChrgBr", tx.charge_bearer or "SHAR")

    # ChrgsInf (0..unbounded)
    for ci in tx.charges_info:
        build_charges_info(cdt_tx, ci)

    # PrvsInstgAgt1/2/3
    for i, prev in enumerate(tx.previous_instructing_agents[:3], start=1):
        build_agent(cdt_tx, f"PrvsInstgAgt{i}", prev)

    # InstgAgt (Pflicht; kommt auch auf C-Level in CBPR+)
    if hasattr(tx, "_instructing_agent") and tx._instructing_agent:
        build_agent(cdt_tx, "InstgAgt", tx._instructing_agent)

    # InstdAgt (Pflicht)
    if hasattr(tx, "_instructed_agent") and tx._instructed_agent:
        build_agent(cdt_tx, "InstdAgt", tx._instructed_agent)

    # Intermediary-Agenten
    for i, imy in enumerate(tx.intermediary_agents[:3], start=1):
        build_agent(cdt_tx, f"IntrmyAgt{i}", imy)

    # UltmtDbtr (optional)
    if tx.ultimate_debtor:
        build_party(cdt_tx, "UltmtDbtr", tx.ultimate_debtor)

    # Dbtr (Pflicht)
    build_party(cdt_tx, "Dbtr", tx.debtor)

    # DbtrAcct (optional)
    if tx.debtor_account and tx.debtor_account.has_id:
        build_cash_account(cdt_tx, "DbtrAcct", tx.debtor_account)

    # DbtrAgt (Pflicht)
    build_agent(cdt_tx, "DbtrAgt", tx.debtor_agent)

    # CdtrAgt (Pflicht)
    build_agent(cdt_tx, "CdtrAgt", tx.creditor_agent)

    # Cdtr (Pflicht)
    build_party(cdt_tx, "Cdtr", tx.creditor)

    # CdtrAcct (optional)
    if tx.creditor_account and tx.creditor_account.has_id:
        build_cash_account(cdt_tx, "CdtrAcct", tx.creditor_account)

    # UltmtCdtr (optional)
    if tx.ultimate_creditor:
        build_party(cdt_tx, "UltmtCdtr", tx.ultimate_creditor)

    # Purp (optional)
    if tx.purpose_code:
        purp = _el(cdt_tx, "Purp")
        _el(purp, "Cd", tx.purpose_code)

    # RmtInf (optional)
    if tx.remittance_info:
        build_remittance_info(cdt_tx, tx.remittance_info)

    return cdt_tx


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _fmt_amount(amt: Decimal, currency: Optional[str] = None) -> str:
    """Formatiert einen Decimal-Betrag entsprechend der ISO 4217 Dezimalstellen.

    Die meisten Waehrungen haben 2 Dezimalstellen. Zero-Decimal-Waehrungen
    (JPY, KRW, ISK, ...) muessen ohne Dezimalstellen serialisiert werden,
    sonst schlaegt die CBPR+-Validation mit 'too many decimal digits' fehl.
    Drei-Dezimal-Waehrungen (BHD, JOD, KWD, OMR, TND, LYD) verwenden 3.
    """
    decimals = _decimals_for_currency(currency)
    quantizer = Decimal("1") if decimals == 0 else Decimal("0." + "0" * decimals)
    return str(amt.quantize(quantizer))


_ZERO_DECIMAL_CURRENCIES = {
    "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW",
    "PYG", "RWF", "UGX", "UYI", "VND", "VUV", "XAF", "XOF", "XPF",
}
_THREE_DECIMAL_CURRENCIES = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}


def _decimals_for_currency(currency: Optional[str]) -> int:
    """Liefert die Anzahl Dezimalstellen fuer eine ISO 4217 Waehrung."""
    if not currency:
        return 2
    ccy = currency.upper()
    if ccy in _ZERO_DECIMAL_CURRENCIES:
        return 0
    if ccy in _THREE_DECIMAL_CURRENCIES:
        return 3
    return 2
