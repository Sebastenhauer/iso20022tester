"""XML-Generator: Baut pain.001.001.09 XML-Struktur mit lxml."""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from lxml import etree

from src.models.testcase import DebtorInfo, PaymentInstruction, Transaction
from src.xml_generator.namespace import NSMAP, PAIN001_NS


def _el(parent: etree._Element, tag: str, text: Optional[str] = None) -> etree._Element:
    """Erstellt ein Sub-Element mit Namespace."""
    elem = etree.SubElement(parent, f"{{{PAIN001_NS}}}{tag}")
    if text is not None:
        elem.text = str(text)
    return elem


def _build_postal_address(
    parent: etree._Element, address: Dict[str, str]
) -> None:
    """Baut ein PstlAdr-Element."""
    pstl_adr = _el(parent, "PstlAdr")
    if "StrtNm" in address:
        _el(pstl_adr, "StrtNm", address["StrtNm"])
    if "BldgNb" in address:
        _el(pstl_adr, "BldgNb", address["BldgNb"])
    if "PstCd" in address:
        _el(pstl_adr, "PstCd", address["PstCd"])
    if "TwnNm" in address:
        _el(pstl_adr, "TwnNm", address["TwnNm"])
    if "Ctry" in address:
        _el(pstl_adr, "Ctry", address["Ctry"])
    if "AdrLine" in address:
        for line in address["AdrLine"].split("|"):
            _el(pstl_adr, "AdrLine", line.strip())


def _build_debtor(parent: etree._Element, debtor: DebtorInfo) -> None:
    """Baut Debtor-Elemente (Dbtr, DbtrAcct, DbtrAgt)."""
    # Dbtr
    dbtr = _el(parent, "Dbtr")
    _el(dbtr, "Nm", debtor.name)
    if debtor.street or debtor.town:
        address = {}
        if debtor.street:
            address["StrtNm"] = debtor.street
        if debtor.building:
            address["BldgNb"] = debtor.building
        if debtor.postal_code:
            address["PstCd"] = debtor.postal_code
        if debtor.town:
            address["TwnNm"] = debtor.town
        address["Ctry"] = debtor.country
        _build_postal_address(dbtr, address)

    # DbtrAcct
    dbtr_acct = _el(parent, "DbtrAcct")
    dbtr_acct_id = _el(dbtr_acct, "Id")
    _el(dbtr_acct_id, "IBAN", debtor.iban.replace(" ", ""))

    # DbtrAgt
    dbtr_agt = _el(parent, "DbtrAgt")
    fin_instn_id = _el(dbtr_agt, "FinInstnId")
    if debtor.bic:
        _el(fin_instn_id, "BICFI", debtor.bic)
    else:
        _el(fin_instn_id, "Othr")
        othr = fin_instn_id.find(f"{{{PAIN001_NS}}}Othr")
        _el(othr, "Id", "NOTPROVIDED")


def _build_transaction(
    parent: etree._Element, tx: Transaction
) -> None:
    """Baut ein CdtTrfTxInf-Element (C-Level)."""
    cdt_trf = _el(parent, "CdtTrfTxInf")

    # PmtId
    pmt_id = _el(cdt_trf, "PmtId")
    _el(pmt_id, "EndToEndId", tx.end_to_end_id)

    # Amt
    amt = _el(cdt_trf, "Amt")
    instd_amt = _el(amt, "InstdAmt", str(tx.amount))
    instd_amt.set("Ccy", tx.currency)

    # CdtrAgt (optional)
    if tx.creditor_bic:
        cdtr_agt = _el(cdt_trf, "CdtrAgt")
        fin_instn = _el(cdtr_agt, "FinInstnId")
        _el(fin_instn, "BICFI", tx.creditor_bic)

    # Cdtr
    cdtr = _el(cdt_trf, "Cdtr")
    _el(cdtr, "Nm", tx.creditor_name)
    if tx.creditor_address:
        _build_postal_address(cdtr, tx.creditor_address)

    # CdtrAcct
    cdtr_acct = _el(cdt_trf, "CdtrAcct")
    cdtr_acct_id = _el(cdtr_acct, "Id")
    _el(cdtr_acct_id, "IBAN", tx.creditor_iban.replace(" ", ""))

    # RmtInf (optional)
    if tx.remittance_info:
        rmt_inf = _el(cdt_trf, "RmtInf")
        ref_type = tx.remittance_info.get("type", "")
        ref_value = tx.remittance_info.get("value", "")

        if ref_type == "QRR":
            # QRR wird als Prtry (Proprietary) abgebildet, nicht als Cd
            strd = _el(rmt_inf, "Strd")
            cdtr_ref_inf = _el(strd, "CdtrRefInf")
            tp = _el(cdtr_ref_inf, "Tp")
            cd_or_prtry = _el(tp, "CdOrPrtry")
            _el(cd_or_prtry, "Prtry", "QRR")
            _el(cdtr_ref_inf, "Ref", ref_value)
        elif ref_type == "SCOR":
            strd = _el(rmt_inf, "Strd")
            cdtr_ref_inf = _el(strd, "CdtrRefInf")
            tp = _el(cdtr_ref_inf, "Tp")
            cd_or_prtry = _el(tp, "CdOrPrtry")
            _el(cd_or_prtry, "Cd", "SCOR")
            _el(cdtr_ref_inf, "Ref", ref_value)
        elif ref_type == "USTRD" or (not ref_type and ref_value):
            _el(rmt_inf, "Ustrd", ref_value)


def build_pain001_xml(payment_instruction: PaymentInstruction) -> etree._Element:
    """Baut ein komplettes pain.001.001.09 XML-Dokument.

    Args:
        payment_instruction: Die Zahlungsinstruktion mit allen Daten.

    Returns:
        lxml Element-Tree des Dokuments.
    """
    # Document root
    doc = etree.Element(f"{{{PAIN001_NS}}}Document", nsmap=NSMAP)
    cstmr = _el(doc, "CstmrCdtTrfInitn")

    # === A-Level: GrpHdr ===
    grp_hdr = _el(cstmr, "GrpHdr")
    _el(grp_hdr, "MsgId", payment_instruction.msg_id)
    _el(grp_hdr, "CreDtTm", payment_instruction.cre_dt_tm)
    nb_of_txs = str(len(payment_instruction.transactions))
    _el(grp_hdr, "NbOfTxs", nb_of_txs)
    ctrl_sum = sum(tx.amount for tx in payment_instruction.transactions)
    _el(grp_hdr, "CtrlSum", str(ctrl_sum))
    initg_pty = _el(grp_hdr, "InitgPty")
    _el(initg_pty, "Nm", payment_instruction.debtor.name)

    # === B-Level: PmtInf ===
    pmt_inf = _el(cstmr, "PmtInf")
    _el(pmt_inf, "PmtInfId", payment_instruction.pmt_inf_id)
    _el(pmt_inf, "PmtMtd", payment_instruction.pmt_mtd)
    _el(pmt_inf, "NbOfTxs", nb_of_txs)
    _el(pmt_inf, "CtrlSum", str(ctrl_sum))

    # PmtTpInf
    pmt_tp_inf = _el(pmt_inf, "PmtTpInf")
    if payment_instruction.service_level:
        svc_lvl = _el(pmt_tp_inf, "SvcLvl")
        _el(svc_lvl, "Cd", payment_instruction.service_level)
    if payment_instruction.local_instrument:
        lcl_instrm = _el(pmt_tp_inf, "LclInstrm")
        _el(lcl_instrm, "Cd", payment_instruction.local_instrument)
    if payment_instruction.category_purpose:
        ctgy_purp = _el(pmt_tp_inf, "CtgyPurp")
        _el(ctgy_purp, "Cd", payment_instruction.category_purpose)

    # ReqdExctnDt
    reqd_exctn_dt = _el(pmt_inf, "ReqdExctnDt")
    _el(reqd_exctn_dt, "Dt", payment_instruction.reqd_exctn_dt)

    # Debtor
    _build_debtor(pmt_inf, payment_instruction.debtor)

    # ChrgBr (B-Level)
    if payment_instruction.charge_bearer:
        _el(pmt_inf, "ChrgBr", payment_instruction.charge_bearer)

    # === C-Level: CdtTrfTxInf ===
    for tx in payment_instruction.transactions:
        _build_transaction(pmt_inf, tx)

    return doc


def serialize_xml(doc: etree._Element, pretty_print: bool = True) -> bytes:
    """Serialisiert ein XML-Element zu Bytes."""
    return etree.tostring(
        doc,
        pretty_print=pretty_print,
        xml_declaration=True,
        encoding="UTF-8",
    )
