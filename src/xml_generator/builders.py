"""Wiederverwendbare XML-Element-Builder für pain.001.

Jeder Builder erzeugt einen isolierten XML-Teilbaum. Kann in verschiedenen
Kontexten verwendet werden (pain.001, pain.002, camt, etc.).
"""

from decimal import Decimal
from typing import Dict, List, Optional

from lxml import etree

from src.models.testcase import DebtorInfo, Transaction
from src.xml_generator.namespace import PAIN001_NS


def el(parent: etree._Element, tag: str, text: Optional[str] = None) -> etree._Element:
    """Erstellt ein Sub-Element mit pain.001 Namespace."""
    elem = etree.SubElement(parent, f"{{{PAIN001_NS}}}{tag}")
    if text is not None:
        elem.text = str(text)
    return elem


# ---------------------------------------------------------------------------
# Address Builder
# ---------------------------------------------------------------------------

def build_postal_address(
    parent: etree._Element, address: Dict[str, str]
) -> etree._Element:
    """Baut ein PstlAdr-Element aus einem Address-Dict.

    Unterstützte Keys: StrtNm, BldgNb, PstCd, TwnNm, Ctry, AdrLine.
    AdrLine kann mehrere Zeilen enthalten (getrennt mit '|').
    """
    pstl_adr = el(parent, "PstlAdr")
    for key in ("StrtNm", "BldgNb", "PstCd", "TwnNm", "Ctry"):
        if key in address:
            el(pstl_adr, key, address[key])
    if "AdrLine" in address:
        for line in address["AdrLine"].split("|"):
            el(pstl_adr, "AdrLine", line.strip())
    return pstl_adr


# ---------------------------------------------------------------------------
# Party Builders (Debtor / Creditor / InitiatingParty)
# ---------------------------------------------------------------------------

def build_debtor_elements(parent: etree._Element, debtor: DebtorInfo) -> None:
    """Baut die drei Debtor-Elemente: Dbtr, DbtrAcct, DbtrAgt.

    Wird im B-Level (PmtInf) verwendet.
    """
    # Dbtr
    dbtr = el(parent, "Dbtr")
    el(dbtr, "Nm", debtor.name)
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
        build_postal_address(dbtr, address)

    # DbtrAcct
    dbtr_acct = el(parent, "DbtrAcct")
    dbtr_acct_id = el(dbtr_acct, "Id")
    el(dbtr_acct_id, "IBAN", debtor.iban.replace(" ", ""))

    # DbtrAgt — FinInstnId darf nicht leer sein (SPS CH21)
    dbtr_agt = el(parent, "DbtrAgt")
    fin_instn_id = el(dbtr_agt, "FinInstnId")
    if debtor.bic:
        el(fin_instn_id, "BICFI", debtor.bic)
    else:
        # Kein BIC: IID aus CH/LI-IBAN ableiten (Stellen 5-9)
        iban_clean = debtor.iban.replace(" ", "")
        if len(iban_clean) >= 9 and iban_clean[:2] in ("CH", "LI"):
            iid = iban_clean[4:9]
            clr_sys = el(fin_instn_id, "ClrSysMmbId")
            el(clr_sys, "MmbId", iid)


def build_creditor_elements(
    parent: etree._Element, tx: Transaction
) -> None:
    """Baut die Creditor-Elemente: CdtrAgt (optional), Cdtr, CdtrAcct.

    Wird im C-Level (CdtTrfTxInf) verwendet.
    """
    # CdtrAgt (optional, z.B. bei CBPR+)
    if tx.creditor_bic:
        build_creditor_agent(parent, tx.creditor_bic)

    # Cdtr
    cdtr = el(parent, "Cdtr")
    el(cdtr, "Nm", tx.creditor_name)
    if tx.creditor_address:
        build_postal_address(cdtr, tx.creditor_address)

    # CdtrAcct
    cdtr_acct = el(parent, "CdtrAcct")
    cdtr_acct_id = el(cdtr_acct, "Id")
    el(cdtr_acct_id, "IBAN", tx.creditor_iban.replace(" ", ""))


def build_creditor_agent(parent: etree._Element, bic: str) -> etree._Element:
    """Baut ein CdtrAgt-Element mit BICFI."""
    cdtr_agt = el(parent, "CdtrAgt")
    fin_instn = el(cdtr_agt, "FinInstnId")
    el(fin_instn, "BICFI", bic)
    return cdtr_agt


def build_initiating_party(parent: etree._Element, name: str) -> etree._Element:
    """Baut ein InitgPty-Element (A-Level GrpHdr)."""
    initg_pty = el(parent, "InitgPty")
    el(initg_pty, "Nm", name)
    return initg_pty


# ---------------------------------------------------------------------------
# Amount Builder
# ---------------------------------------------------------------------------

def build_amount(parent: etree._Element, amount: Decimal, currency: str) -> etree._Element:
    """Baut ein Amt/InstdAmt-Element mit Währungsattribut."""
    amt = el(parent, "Amt")
    instd_amt = el(amt, "InstdAmt", str(amount))
    instd_amt.set("Ccy", currency)
    return amt


# ---------------------------------------------------------------------------
# Remittance Info Builder
# ---------------------------------------------------------------------------

def build_remittance_info(
    parent: etree._Element,
    remittance_info: Dict[str, str],
) -> Optional[etree._Element]:
    """Baut ein RmtInf-Element.

    Unterstützte Typen:
    - QRR: Structured mit Prtry (XSD erlaubt nur SCOR als Cd)
    - SCOR: Structured mit Cd
    - USTRD: Unstructured
    """
    ref_type = remittance_info.get("type", "")
    ref_value = remittance_info.get("value", "")

    if not ref_type and not ref_value:
        return None

    rmt_inf = el(parent, "RmtInf")

    if ref_type == "QRR":
        _build_structured_ref(rmt_inf, "Prtry", "QRR", ref_value)
    elif ref_type == "SCOR":
        _build_structured_ref(rmt_inf, "Cd", "SCOR", ref_value)
    elif ref_type == "USTRD" or (not ref_type and ref_value):
        el(rmt_inf, "Ustrd", ref_value)

    return rmt_inf


def _build_structured_ref(
    rmt_inf: etree._Element,
    code_tag: str,
    code_value: str,
    ref_value: str,
) -> None:
    """Baut eine strukturierte Referenz (CdtrRefInf) innerhalb von RmtInf."""
    strd = el(rmt_inf, "Strd")
    cdtr_ref_inf = el(strd, "CdtrRefInf")
    tp = el(cdtr_ref_inf, "Tp")
    cd_or_prtry = el(tp, "CdOrPrtry")
    el(cd_or_prtry, code_tag, code_value)
    el(cdtr_ref_inf, "Ref", ref_value)


# ---------------------------------------------------------------------------
# Payment Type Info Builder
# ---------------------------------------------------------------------------

def build_payment_type_info(
    parent: etree._Element,
    service_level: Optional[str] = None,
    local_instrument: Optional[str] = None,
    category_purpose: Optional[str] = None,
) -> Optional[etree._Element]:
    """Baut ein PmtTpInf-Element (B-Level).

    Gibt None zurück wenn keine der Felder gesetzt ist.
    """
    if not any([service_level, local_instrument, category_purpose]):
        return None

    pmt_tp_inf = el(parent, "PmtTpInf")
    if service_level:
        svc_lvl = el(pmt_tp_inf, "SvcLvl")
        el(svc_lvl, "Cd", service_level)
    if local_instrument:
        lcl_instrm = el(pmt_tp_inf, "LclInstrm")
        el(lcl_instrm, "Cd", local_instrument)
    if category_purpose:
        ctgy_purp = el(pmt_tp_inf, "CtgyPurp")
        el(ctgy_purp, "Cd", category_purpose)
    return pmt_tp_inf
