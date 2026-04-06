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
    if debtor.lei:
        build_org_id(dbtr, debtor.lei)

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
    Unterstützt IBAN-Konten und Non-IBAN-Konten (Othr) für CBPR+.
    """
    # CdtrAgt (optional, z.B. bei CBPR+)
    if tx.creditor_bic:
        build_creditor_agent(parent, tx.creditor_bic)

    # Cdtr
    cdtr = el(parent, "Cdtr")
    el(cdtr, "Nm", tx.creditor_name)
    if tx.creditor_address:
        build_postal_address(cdtr, tx.creditor_address)
    if tx.creditor_lei:
        build_org_id(cdtr, tx.creditor_lei)

    # CdtrAcct — IBAN oder Othr (Non-IBAN)
    cdtr_acct = el(parent, "CdtrAcct")
    cdtr_acct_id = el(cdtr_acct, "Id")

    if tx.creditor_account_id:
        # Non-IBAN: Othr/Id (SPS CH XSD erlaubt nur Id, kein SchmeNm)
        othr = el(cdtr_acct_id, "Othr")
        el(othr, "Id", tx.creditor_account_id)
    elif tx.creditor_iban:
        el(cdtr_acct_id, "IBAN", tx.creditor_iban.replace(" ", ""))


def build_ultimate_debtor(
    parent: etree._Element, data: Dict[str, str]
) -> Optional[etree._Element]:
    """Baut ein UltmtDbtr-Element (B-Level oder C-Level).

    Unterstützte Keys: Nm, StrtNm, TwnNm, Ctry.
    Gibt None zurück wenn keine Daten vorhanden.
    """
    if not data or not data.get("Nm"):
        return None

    ultmt_dbtr = el(parent, "UltmtDbtr")
    el(ultmt_dbtr, "Nm", data["Nm"])
    addr_keys = {k: v for k, v in data.items() if k != "Nm"}
    if addr_keys:
        build_postal_address(ultmt_dbtr, addr_keys)
    return ultmt_dbtr


def build_ultimate_creditor(
    parent: etree._Element, data: Dict[str, str]
) -> Optional[etree._Element]:
    """Baut ein UltmtCdtr-Element (C-Level).

    Unterstützte Keys: Nm, StrtNm, TwnNm, Ctry.
    Gibt None zurück wenn keine Daten vorhanden.
    """
    if not data or not data.get("Nm"):
        return None

    ultmt_cdtr = el(parent, "UltmtCdtr")
    el(ultmt_cdtr, "Nm", data["Nm"])
    addr_keys = {k: v for k, v in data.items() if k != "Nm"}
    if addr_keys:
        build_postal_address(ultmt_cdtr, addr_keys)
    return ultmt_cdtr


def build_creditor_agent(parent: etree._Element, bic: str) -> etree._Element:
    """Baut ein CdtrAgt-Element mit BICFI."""
    cdtr_agt = el(parent, "CdtrAgt")
    fin_instn = el(cdtr_agt, "FinInstnId")
    el(fin_instn, "BICFI", bic)
    return cdtr_agt


def build_org_id(parent: etree._Element, lei: str) -> etree._Element:
    """Baut ein Id/OrgId/LEI-Element für Party Identification (ISO 17442)."""
    party_id = el(parent, "Id")
    org_id = el(party_id, "OrgId")
    el(org_id, "LEI", lei)
    return party_id


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
# Regulatory Reporting Builder
# ---------------------------------------------------------------------------

def build_regulatory_reporting(
    parent: etree._Element,
    reg_data: Dict[str, str],
) -> Optional[etree._Element]:
    """Baut ein RgltryRptg-Element (C-Level).

    Unterstützte Keys:
    - DbtCdtRptgInd: DEBT oder CRED
    - Authrty.Nm: Name der Regulierungsbehörde
    - Authrty.Ctry: Land der Regulierungsbehörde
    - Dtls.Tp: Typ (z.B. BALANCE_OF_PAYMENTS)
    - Dtls.Cd: Code (max 10 Zeichen)
    - Dtls.Inf: Zusatzinformation

    Gibt None zurück wenn keine Daten vorhanden sind.
    """
    if not reg_data:
        return None

    rgltry_rptg = el(parent, "RgltryRptg")

    if "DbtCdtRptgInd" in reg_data:
        el(rgltry_rptg, "DbtCdtRptgInd", reg_data["DbtCdtRptgInd"])

    # Authrty (optional)
    authrty_nm = reg_data.get("Authrty.Nm")
    authrty_ctry = reg_data.get("Authrty.Ctry")
    if authrty_nm or authrty_ctry:
        authrty = el(rgltry_rptg, "Authrty")
        if authrty_nm:
            el(authrty, "Nm", authrty_nm)
        if authrty_ctry:
            el(authrty, "Ctry", authrty_ctry)

    # Dtls (optional)
    dtls_tp = reg_data.get("Dtls.Tp")
    dtls_cd = reg_data.get("Dtls.Cd")
    dtls_inf = reg_data.get("Dtls.Inf")
    if dtls_tp or dtls_cd or dtls_inf:
        dtls = el(rgltry_rptg, "Dtls")
        if dtls_tp:
            el(dtls, "Tp", dtls_tp)
        if dtls_cd:
            el(dtls, "Cd", dtls_cd)
        if dtls_inf:
            el(dtls, "Inf", dtls_inf)

    return rgltry_rptg


# ---------------------------------------------------------------------------
# Tax Remittance Builder
# ---------------------------------------------------------------------------

def build_tax_remittance(
    parent: etree._Element,
    tax_data: Dict[str, str],
) -> Optional[etree._Element]:
    """Baut ein TaxRmt-Element innerhalb von RmtInf/Strd (C-Level).

    Unterstützte Keys:
    - Cdtr.TaxId: Steuer-ID des Gläubigers (Steuerbehörde)
    - Cdtr.RegnId: Registrierungs-ID des Gläubigers
    - Cdtr.TaxTp: Steuertyp des Gläubigers
    - Dbtr.TaxId: Steuer-ID des Schuldners (Steuerzahler)
    - Dbtr.RegnId: Registrierungs-ID des Schuldners
    - Dbtr.TaxTp: Steuertyp des Schuldners
    - AdmstnZone: Verwaltungszone
    - RefNb: Steuer-Referenznummer
    - Mtd: Berechnungsmethode
    - TtlTaxAmt: Gesamtsteuerbetrag
    - TtlTaxAmt.Ccy: Währung des Steuerbetrags
    - Dt: Steuerdatum (ISODate)

    Gibt None zurück wenn keine Daten vorhanden sind.
    """
    if not tax_data:
        return None

    tax_rmt = el(parent, "TaxRmt")

    # Cdtr (TaxParty1: TaxId, RegnId, TaxTp)
    cdtr_tax_id = tax_data.get("Cdtr.TaxId")
    cdtr_regn_id = tax_data.get("Cdtr.RegnId")
    cdtr_tax_tp = tax_data.get("Cdtr.TaxTp")
    if cdtr_tax_id or cdtr_regn_id or cdtr_tax_tp:
        cdtr = el(tax_rmt, "Cdtr")
        if cdtr_tax_id:
            el(cdtr, "TaxId", cdtr_tax_id)
        if cdtr_regn_id:
            el(cdtr, "RegnId", cdtr_regn_id)
        if cdtr_tax_tp:
            el(cdtr, "TaxTp", cdtr_tax_tp)

    # Dbtr (TaxParty2: TaxId, RegnId, TaxTp)
    dbtr_tax_id = tax_data.get("Dbtr.TaxId")
    dbtr_regn_id = tax_data.get("Dbtr.RegnId")
    dbtr_tax_tp = tax_data.get("Dbtr.TaxTp")
    if dbtr_tax_id or dbtr_regn_id or dbtr_tax_tp:
        dbtr = el(tax_rmt, "Dbtr")
        if dbtr_tax_id:
            el(dbtr, "TaxId", dbtr_tax_id)
        if dbtr_regn_id:
            el(dbtr, "RegnId", dbtr_regn_id)
        if dbtr_tax_tp:
            el(dbtr, "TaxTp", dbtr_tax_tp)

    # AdmstnZone
    if "AdmstnZone" in tax_data:
        el(tax_rmt, "AdmstnZone", tax_data["AdmstnZone"])

    # RefNb
    if "RefNb" in tax_data:
        el(tax_rmt, "RefNb", tax_data["RefNb"])

    # Mtd
    if "Mtd" in tax_data:
        el(tax_rmt, "Mtd", tax_data["Mtd"])

    # TtlTaxAmt (ActiveOrHistoricCurrencyAndAmount)
    ttl_tax_amt = tax_data.get("TtlTaxAmt")
    if ttl_tax_amt:
        ttl_elem = el(tax_rmt, "TtlTaxAmt", ttl_tax_amt)
        ccy = tax_data.get("TtlTaxAmt.Ccy", "CHF")
        ttl_elem.set("Ccy", ccy)

    # Dt
    if "Dt" in tax_data:
        el(tax_rmt, "Dt", tax_data["Dt"])

    return tax_rmt


# ---------------------------------------------------------------------------
# Purpose Builder
# ---------------------------------------------------------------------------

def build_purpose(
    parent: etree._Element,
    purpose_code: Optional[str] = None,
) -> Optional[etree._Element]:
    """Baut ein Purp/Cd-Element (C-Level).

    Gibt None zurück wenn kein Purpose Code gesetzt ist.
    """
    if not purpose_code:
        return None

    purp = el(parent, "Purp")
    el(purp, "Cd", purpose_code)
    return purp


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
