"""Zentraler Katalog aller Business Rules.

Alle Rule-Metadaten (ID, Kategorie, Beschreibung, Spec-Referenz,
anwendbare Zahlungstypen) sind hier definiert. Validierungs- und
Violation-Logik referenziert diesen Katalog.

Export als Markdown via `rules_to_markdown()`.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.models.testcase import PaymentType


@dataclass(frozen=True)
class BusinessRule:
    """Definition einer einzelnen Business Rule."""

    rule_id: str
    category: str
    description: str
    applies_to: Optional[Tuple[PaymentType, ...]]  # None = alle Zahlungstypen
    spec_reference: str
    violatable: bool = False


# ---------------------------------------------------------------------------
# Regel-Definitionen
# ---------------------------------------------------------------------------

_ALL_RULES: List[BusinessRule] = []


def _r(
    rule_id: str,
    category: str,
    description: str,
    applies_to: Optional[Tuple[PaymentType, ...]],
    spec_reference: str,
    violatable: bool = False,
) -> BusinessRule:
    rule = BusinessRule(
        rule_id=rule_id,
        category=category,
        description=description,
        applies_to=applies_to,
        spec_reference=spec_reference,
        violatable=violatable,
    )
    _ALL_RULES.append(rule)
    return rule


# --- Header-Regeln (A-Level) ---

BR_HDR_002 = _r(
    "BR-HDR-002", "HDR",
    "NbOfTxs im GrpHdr muss der Summe aller Transaktionen entsprechen",
    None,
    "IG CT SPS 2025 §4.1.4",
)

BR_HDR_003 = _r(
    "BR-HDR-003", "HDR",
    "CtrlSum im GrpHdr muss der Summe aller Beträge entsprechen",
    None,
    "IG CT SPS 2025 §4.1.5",
)

BR_HDR_004 = _r(
    "BR-HDR-004", "HDR",
    "InitgPty/Nm muss gesetzt sein",
    None,
    "IG CT SPS 2025 §4.1.6",
)

# --- Übergreifende Regeln ---

BR_GEN_001 = _r(
    "BR-GEN-001", "GEN",
    "Betrag darf maximal 2 Dezimalstellen haben",
    None,
    "Business Rules SPS 2025 §2.5",
)

BR_GEN_002 = _r(
    "BR-GEN-002", "GEN",
    "BIC muss 8 oder 11 alphanumerische Zeichen haben",
    None,
    "IG CT SPS 2025 §3.12",
)

BR_GEN_005 = _r(
    "BR-GEN-005", "GEN",
    "ReqdExctnDt muss ein Bankarbeitstag sein (TARGET2 für SEPA, CH für Inland/CBPR+)",
    None,
    "Business Rules SPS 2025 §2.3",
)

BR_GEN_009 = _r(
    "BR-GEN-009", "GEN",
    "Referenzfelder: kein '/' am Anfang/Ende, kein '//' innerhalb",
    None,
    "IG CT SPS 2025 §3.2",
)

BR_GEN_010 = _r(
    "BR-GEN-010", "GEN",
    "Betrag muss grösser als 0 sein",
    None,
    "Business Rules SPS 2025 §2.5",
)

BR_GEN_012 = _r(
    "BR-GEN-012", "GEN",
    "Textfelder müssen dem SPS-Zeichensatz (Latin-1 Subset) entsprechen",
    None,
    "IG CT SPS 2025 §3.1",
)

BR_GEN_013 = _r(
    "BR-GEN-013", "GEN",
    "LEI muss 20 Zeichen lang sein: 18 alphanumerisch + 2 Prüfziffern (ISO 17442)",
    None,
    "ISO 17442, pain.001.001.09 Schema",
)

# --- Purpose ---

BR_PURP_001 = _r(
    "BR-PURP-001", "PURP",
    "Purpose/Cd muss ein gültiger ExternalPurpose1Code sein (1–4 Zeichen)",
    None,
    "ISO 20022 External Code Lists, pain.001.001.09 Schema",
)

# --- Category Purpose ---

BR_CTGP_001 = _r(
    "BR-CTGP-001", "CTGP",
    "CtgyPurp/Cd muss ein gültiger ExternalCategoryPurpose1Code sein (1–4 Zeichen)",
    None,
    "ISO 20022 External Code Lists, pain.001.001.09 Schema",
)

# --- Adress-Regeln ---

BR_ADDR_001 = _r(
    "BR-ADDR-001", "ADDR",
    "Strukturierte Adresse: TwnNm und Ctry muessen gesetzt sein",
    None,
    "IG CT SPS 2025 §3.1, §3.11",
)

BR_ADDR_002 = _r(
    "BR-ADDR-002", "ADDR",
    "Creditor-Adresse muss strukturiert sein (StrtNm, TwnNm, Ctry Pflicht, kein AdrLine allein)",
    None,
    "IG CT SPS 2026 §3.1.2, ab Nov 2026 Pflicht",
    violatable=True,
)

BR_ADDR_003 = _r(
    "BR-ADDR-003", "ADDR",
    "Debtor-Adresse: wenn vorhanden, muessen TwnNm und Ctry gesetzt sein",
    None,
    "IG CT SPS 2025 §4.2.6",
)

BR_ADDR_010 = _r(
    "BR-ADDR-010", "ADDR",
    "PLZ muss dem laenderspezifischen Format entsprechen",
    None,
    "IG CT SPS 2025 §3.11, ISO 20022 PstlAdr",
)

BR_ADDR_011 = _r(
    "BR-ADDR-011", "ADDR",
    "Adressfelder duerfen maximale Feldlaenge nicht ueberschreiten",
    None,
    "IG CT SPS 2025 §3.11, pain.001.001.09 Schema",
)

BR_ADDR_012 = _r(
    "BR-ADDR-012", "ADDR",
    "PLZ ist Pflicht fuer Laender mit PLZ-System",
    None,
    "IG CT SPS 2025 §3.11",
)

BR_GEN_006 = _r(
    "BR-GEN-006", "GEN",
    "Creditor-Name darf maximal 140 Zeichen lang sein (non-SEPA)",
    (PaymentType.DOMESTIC_QR, PaymentType.DOMESTIC_IBAN, PaymentType.CBPR_PLUS),
    "IG CT SPS 2025 v2.2 §4.3.7",
)

BR_GEN_007 = _r(
    "BR-GEN-007", "GEN",
    "Country-Code muss 2 Großbuchstaben sein (ISO 3166-1)",
    None,
    "IG CT SPS 2025 §3.11, SwissQRBill",
)

BR_BIC_001 = _r(
    "BR-BIC-001", "BIC",
    "BIC muss im SWIFT BIC Directory existieren und aktiv sein",
    None,
    "SWIFT BIC Directory, ISO 9362",
)

# --- IBAN-Validierung ---

BR_IBAN_V01 = _r(
    "BR-IBAN-V01", "IBAN-V",
    "IBAN-Prüfziffer muss Mod-97 valide sein",
    None,
    "ISO 13616",
)

BR_IBAN_V02 = _r(
    "BR-IBAN-V02", "IBAN-V",
    "IBAN-Länge muss dem Länderschlüssel entsprechen",
    None,
    "ISO 13616",
)

# --- Referenz-Validierung ---

BR_REF_V01 = _r(
    "BR-REF-V01", "REF-V",
    "SCOR-Referenz: muss mit RF beginnen, max 25 Zeichen, Mod-97 Prüfziffer",
    None,
    "ISO 11649, SwissQRBill",
)

# --- SEPA-spezifisch (Typ S) ---

_SEPA = (PaymentType.SEPA,)

BR_SEPA_001 = _r(
    "BR-SEPA-001", "SEPA",
    "Währung muss EUR sein",
    _SEPA,
    "Business Rules SPS 2025 Tabelle 3, Typ S",
    violatable=True,
)

BR_SEPA_003 = _r(
    "BR-SEPA-003", "SEPA",
    "ChrgBr muss SLEV sein",
    _SEPA,
    "Business Rules SPS 2025 Tabelle 3, Typ S",
    violatable=True,
)

BR_SEPA_004 = _r(
    "BR-SEPA-004", "SEPA",
    "Creditor-Name darf maximal 70 Zeichen lang sein",
    _SEPA,
    "IG CT SPS 2025 §4.3.7",
    violatable=True,
)

BR_SEPA_005 = _r(
    "BR-SEPA-005", "SEPA",
    "Creditor muss eine gültige IBAN haben",
    _SEPA,
    "IG CT SPS 2025 §4.3.9",
)

BR_SEPA_006 = _r(
    "BR-SEPA-006", "SEPA",
    "Betrag muss zwischen 0.01 und 999'999'999.99 liegen",
    _SEPA,
    "Business Rules SPS 2025 §2.5",
)

# --- QR-IBAN-spezifisch (Typ D mit QR-IBAN) ---

_QR = (PaymentType.DOMESTIC_QR,)

BR_QR_001 = _r(
    "BR-QR-001", "QR",
    "Creditor muss eine QR-IBAN haben (IID 30000–31999)",
    _QR,
    "Business Rules SPS 2025 Tabelle 3, Typ D/QR",
)

BR_QR_002 = _r(
    "BR-QR-002", "QR",
    "Bei QR-IBAN muss eine QR-Referenz (QRR) vorhanden sein",
    _QR,
    "Business Rules SPS 2025 §3.2",
    violatable=True,
)

BR_QR_003 = _r(
    "BR-QR-003", "QR",
    "SCOR-Referenz ist bei QR-IBAN nicht zulässig",
    _QR,
    "Business Rules SPS 2025 §3.2",
    violatable=True,
)

BR_QR_004 = _r(
    "BR-QR-004", "QR",
    "Währung muss CHF oder EUR sein",
    _QR,
    "Business Rules SPS 2025 Tabelle 3, Typ D",
    violatable=True,
)

BR_QR_005 = _r(
    "BR-QR-005", "QR",
    "SvcLvl darf nicht 'SEPA' sein",
    _QR,
    "Business Rules SPS 2025 Tabelle 3, Typ D",
)

BR_QR_006 = _r(
    "BR-QR-006", "QR",
    "QRR muss 27 Stellen numerisch sein mit Mod-10-Prüfziffer",
    _QR,
    "Business Rules SPS 2025 §3.2",
)

BR_QR_007 = _r(
    "BR-QR-007", "QR",
    "QR-IBAN muss eine Schweizer (CH) oder Liechtensteiner (LI) IBAN sein",
    _QR,
    "Business Rules SPS 2025 Tabelle 3, SwissQRBill",
)

# --- Domestic-IBAN-spezifisch (Typ D mit regulärer IBAN) ---

_IBAN = (PaymentType.DOMESTIC_IBAN,)

BR_IBAN_001 = _r(
    "BR-IBAN-001", "IBAN",
    "Creditor darf keine QR-IBAN haben",
    _IBAN,
    "Business Rules SPS 2025 Tabelle 3, Typ D/IBAN",
    violatable=True,
)

BR_IBAN_002 = _r(
    "BR-IBAN-002", "IBAN",
    "QR-Referenz (QRR) ist bei regulärer IBAN nicht zulässig",
    _IBAN,
    "Business Rules SPS 2025 §3.2",
    violatable=True,
)

BR_IBAN_003 = _r(
    "BR-IBAN-003", "IBAN",
    "SCOR-Referenz muss formal valide sein (RF + Mod-97)",
    _IBAN,
    "ISO 11649",
)

BR_IBAN_004 = _r(
    "BR-IBAN-004", "IBAN",
    "Währung muss CHF sein",
    _IBAN,
    "Business Rules SPS 2025 Tabelle 3, Typ D/IBAN",
    violatable=True,
)

BR_IBAN_005 = _r(
    "BR-IBAN-005", "IBAN",
    "SvcLvl darf nicht 'SEPA' sein",
    _IBAN,
    "Business Rules SPS 2025 Tabelle 3, Typ D",
)

BR_IBAN_006 = _r(
    "BR-IBAN-006", "IBAN",
    "Domestic-IBAN muss eine Schweizer (CH) oder Liechtensteiner (LI) IBAN sein",
    _IBAN,
    "Business Rules SPS 2025 Tabelle 3, SwissQRBill",
)

_DOM = (PaymentType.DOMESTIC_QR, PaymentType.DOMESTIC_IBAN)

BR_DOM_001 = _r(
    "BR-DOM-001", "DOM",
    "ChrgBr darf bei Domestic-Zahlungen (Typ D) nicht gesetzt sein",
    _DOM,
    "Business Rules SPS 2025 Tabelle 3, Typ D",
    violatable=True,
)

# --- CBPR+-spezifisch (Typ X) ---

_CBPR = (PaymentType.CBPR_PLUS,)

BR_CBPR_001 = _r(
    "BR-CBPR-001", "CBPR",
    "Währung muss explizit angegeben sein",
    _CBPR,
    "Business Rules SPS 2025 Tabelle 3, Typ X",
    violatable=False,  # Input-Level-Prüfung, nicht via XML verletzbar (Ccy ist XSD-Pflichtattribut)
)

BR_CBPR_002 = _r(
    "BR-CBPR-002", "CBPR",
    "SvcLvl darf nicht 'SEPA' sein",
    _CBPR,
    "Business Rules SPS 2025 Tabelle 3, Typ X",
)

BR_CBPR_003 = _r(
    "BR-CBPR-003", "CBPR",
    "ChrgBr darf nicht SLEV sein (CBPR+ erlaubt nur DEBT, CRED, SHAR)",
    _CBPR,
    "CBPR+ SR2025 Usage Guideline p.203-204",
    violatable=True,
)

BR_CBPR_005 = _r(
    "BR-CBPR-005", "CBPR",
    "Creditor-Agent (BIC) muss angegeben werden",
    _CBPR,
    "IG CT SPS 2025 §4.3.6",
    violatable=True,
)

BR_CBPR_006 = _r(
    "BR-CBPR-006", "CBPR",
    "UETR (UUIDv4) ist Pflicht für CBPR+-Zahlungen",
    _CBPR,
    "CBPR+ SR2025 Usage Guideline p.133",
)

BR_CBPR_007 = _r(
    "BR-CBPR-007", "CBPR",
    "Creditor muss entweder IBAN oder Kontonummer (Othr/Id) haben",
    _CBPR,
    "pain.001.001.09 Schema, CdtrAcct/Id Choice",
)

# --- SIC5 Instant-spezifisch ---

_INSTANT = (PaymentType.DOMESTIC_IBAN,)

BR_SIC5_001 = _r(
    "BR-SIC5-001", "SIC5",
    "Instant-Zahlung: Währung muss CHF sein",
    _INSTANT,
    "SPS 2025 SIC5 Instant Payment",
    violatable=True,
)

BR_SIC5_002 = _r(
    "BR-SIC5-002", "SIC5",
    "Instant-Zahlung: Creditor-IBAN muss CH oder LI sein",
    _INSTANT,
    "SPS 2025 SIC5 Instant Payment",
    violatable=True,
)

BR_SIC5_003 = _r(
    "BR-SIC5-003", "SIC5",
    "Instant-Zahlung: ServiceLevel muss 'INST' sein",
    _INSTANT,
    "SPS 2025 SIC5 Instant Payment",
)

BR_SIC5_004 = _r(
    "BR-SIC5-004", "SIC5",
    "Instant-Zahlung: LocalInstrument muss 'INST' sein",
    _INSTANT,
    "SPS 2025 SIC5 Instant Payment",
)

# --- SCT Inst (SEPA Instant Credit Transfer) ---

_SCT_INST = (PaymentType.SEPA,)

BR_SCT_INST_001 = _r(
    "BR-SCT-INST-001", "SCT-INST",
    "SCT Inst: Währung muss EUR sein",
    _SCT_INST,
    "EPC SCT Inst Rulebook",
    violatable=True,
)

BR_SCT_INST_002 = _r(
    "BR-SCT-INST-002", "SCT-INST",
    "SCT Inst: Betrag darf maximal 100'000 EUR betragen",
    _SCT_INST,
    "EPC SCT Inst Rulebook, RT1/TIPS Limit",
    violatable=True,
)

BR_SCT_INST_003 = _r(
    "BR-SCT-INST-003", "SCT-INST",
    "SCT Inst: ServiceLevel muss 'INST' sein",
    _SCT_INST,
    "EPC SCT Inst Rulebook",
)

BR_SCT_INST_004 = _r(
    "BR-SCT-INST-004", "SCT-INST",
    "SCT Inst: LocalInstrument muss 'INST' sein",
    _SCT_INST,
    "EPC SCT Inst Rulebook",
)

BR_SCT_INST_005 = _r(
    "BR-SCT-INST-005", "SCT-INST",
    "SCT Inst: ChrgBr muss SLEV sein",
    _SCT_INST,
    "EPC SCT Inst Rulebook",
)

# --- Remittance Information ---

BR_REM_002 = _r(
    "BR-REM-002", "REM",
    "Unstrukturierte Remittance Info darf maximal 140 Zeichen lang sein",
    None,
    "IG CT SPS 2025 §3.2.2",
    violatable=False,  # XSD-geschuetzt: maxLength=140 auf Ustrd-Element
)

# --- Currency ---

BR_CCY_001 = _r(
    "BR-CCY-001", "CCY",
    "Währungscode muss gültig sein (ISO 4217, 3 Großbuchstaben)",
    None,
    "IG CT SPS 2025, ISO 4217",
    violatable=True,
)

# --- CGI-MP-spezifisch ---

BR_CGI_ADDR_01 = _r(
    "BR-CGI-ADDR-01", "CGI",
    "Adresse: Country Pflicht, TownName empfohlen (Pflicht ab Nov 2025 fuer int./urgent)",
    None,
    "CGI-MP Handbook Slide 11",
)

BR_CGI_ADDR_02 = _r(
    "BR-CGI-ADDR-02", "CGI",
    "Unstructured Adresse verboten fuer UltmtDbtr, UltmtCdtr, InitgPty",
    None,
    "CGI-MP Handbook Slide 8",
)

BR_CGI_ADDR_03 = _r(
    "BR-CGI-ADDR-03", "CGI",
    "CGI-MP: Adresse muss strukturiert sein (StrtNm + BldgNb + PstCd + TwnNm + Ctry, kein AdrLine)",
    None,
    "CGI-MP Handbook Slide 11",
    violatable=True,
)

BR_CGI_RMT_01 = _r(
    "BR-CGI-RMT-01", "CGI",
    "Structured und Unstructured Remittance gegenseitig exklusiv",
    None,
    "CGI-MP Handbook Slide 24",
)

BR_CGI_RMT_02 = _r(
    "BR-CGI-RMT-02", "CGI",
    "Structured Remittance max 9000 Zeichen (exkl. Tag-Namen)",
    None,
    "CGI-MP Handbook Slide 24",
)

BR_CGI_RMT_03 = _r(
    "BR-CGI-RMT-03", "CGI",
    "RfrdDocInf: Wenn Number vorhanden, Type Pflicht",
    None,
    "CGI-MP Handbook Slide 26",
)

BR_CGI_PURP_01 = _r(
    "BR-CGI-PURP-01", "CGI",
    "Regulatory purpose unter RgltryRptg, NICHT unter Purp",
    None,
    "CGI-MP Handbook Slide 13",
)

BR_CGI_PURP_02 = _r(
    "BR-CGI-PURP-02", "CGI",
    "Wenn RgltryRptg verwendet, DbtCdtRptgInd (DEBT/CRED) Pflicht",
    None,
    "CGI-MP Handbook Slide 15",
)

BR_CGI_CHAR_01 = _r(
    "BR-CGI-CHAR-01", "CGI",
    "Leere XML-Tags (ohne Wert oder nur Blanks) verboten",
    None,
    "CGI-MP Handbook Slide 4",
)

BR_CGI_TAX_01 = _r(
    "BR-CGI-TAX-01", "CGI",
    "Wenn CtgyPurp=WHLD, Tax-Element erwartet",
    None,
    "CGI-MP Handbook Slide 42",
)

BR_CGI_TAX_02 = _r(
    "BR-CGI-TAX-02", "CGI",
    "Tax: Creditor und Debtor TaxId Pflicht wenn Tax vorhanden",
    None,
    "CGI-MP Handbook Slide 44",
)

BR_CGI_TAX_03 = _r(
    "BR-CGI-TAX-03", "CGI",
    "Tax: Method Pflicht wenn Tax vorhanden",
    None,
    "CGI-MP Handbook Slide 44",
)

BR_CGI_RGRP_01 = _r(
    "BR-CGI-RGRP-01", "CGI",
    "RgltryRptg: Wenn Details vorhanden, Type (Tp) Pflicht",
    None,
    "CGI-MP Handbook Slide 17",
)

BR_CGI_RGRP_02 = _r(
    "BR-CGI-RGRP-02", "CGI",
    "RgltryRptg: Code max 10 Zeichen",
    None,
    "CGI-MP Handbook Slide 17",
)

BR_CH21_RGRP_CD_CTRY = _r(
    "BR-CH21-RGRP-CD-CTRY", "SPS",
    "CH21: RgltryRptg/Dtls/Cd darf nur zusammen mit Dtls/Ctry verwendet werden",
    None,
    "GEFEG CH21 / SPS 2025",
)

BR_CGI_PMTMTD_01 = _r(
    "BR-CGI-PMTMTD-01", "CGI",
    "CGI-MP: PmtMtd muss 'TRF' sein (Non-Cheque)",
    None,
    "xmldation.com/cgi-mp /pmtmtd",
)

BR_CGI_ORG_01 = _r(
    "BR-CGI-ORG-01", "CGI",
    "CGI-MP: OrgId/Othr/SchmeNm nur per Cd (nicht Prtry); LEI muss ISO 17442 (20 alphanum.) entsprechen",
    None,
    "xmldation.com/cgi-mp /schmenm_in_orgid",
)

BR_CGI_PTI_01 = _r(
    "BR-CGI-PTI-01", "CGI",
    "CGI-MP: PmtTpInf Pflicht inkl. SvcLvl (entweder B- oder C-Level, nicht beides)",
    None,
    "xmldation.com/cgi-mp /pmttpinf",
)

BR_CGI_SEPA_SVC_01 = _r(
    "BR-CGI-SEPA-SVC-01", "CGI",
    "CGI-MP SEPA: SvcLvl/Cd muss 'SEPA' sein (strenger als EPC)",
    None,
    "xmldation.com/cgi-mp /sepa_-_svclvl",
)

# ---------------------------------------------------------------------------
# CBPR+ pacs.008.001.08 Rules (Kategorie CBPR-PACS)
# Quellen: SWIFT CBPR+ Usage Guidelines SR2026, Schema constraints aus
# CBPRPlus_..._pacs_008_001_08_FIToFICustomerCreditTransfer_..._iso15enriched.xsd
# ---------------------------------------------------------------------------

BR_CBPR_PACS_001 = _r(
    "BR-CBPR-PACS-001", "CBPR-PACS",
    "CBPR+ pacs.008: UETR (ISO 17442) ist Pflicht auf PmtId-Ebene",
    None,
    "CBPR+ Usage Guidelines SR2026",
    violatable=True,
)

BR_CBPR_PACS_002 = _r(
    "BR-CBPR-PACS-002", "CBPR-PACS",
    "CBPR+ pacs.008: InstgAgt muss identifiziert sein (BICFI oder ClrSysMmbId)",
    None,
    "CBPR+ Usage Guidelines SR2026",
    violatable=True,
)

BR_CBPR_PACS_003 = _r(
    "BR-CBPR-PACS-003", "CBPR-PACS",
    "CBPR+ pacs.008: InstdAgt muss identifiziert sein (BICFI oder ClrSysMmbId)",
    None,
    "CBPR+ Usage Guidelines SR2026",
    violatable=True,
)

BR_CBPR_PACS_004 = _r(
    "BR-CBPR-PACS-004", "CBPR-PACS",
    "CBPR+ pacs.008: SttlmMtd muss INDA oder INGA sein "
    "(XSD erlaubt auch COVE, in V1 out of scope; CLRG nicht in CBPR+ erlaubt)",
    None,
    "CBPR+ Usage Guidelines SR2026 Schema enumeration",
    violatable=True,
)

BR_CBPR_PACS_005 = _r(
    "BR-CBPR-PACS-005", "CBPR-PACS",
    "CBPR+ pacs.008: Creditor-Adresse muss strukturiert sein (Nm, Ctry mindestens)",
    None,
    "CBPR+ Usage Guidelines SR2026",
)

BR_CBPR_PACS_006 = _r(
    "BR-CBPR-PACS-006", "CBPR-PACS",
    "CBPR+ pacs.008: Debtor-Adresse muss strukturiert sein (Nm, Ctry mindestens)",
    None,
    "CBPR+ Usage Guidelines SR2026",
)

BR_CBPR_PACS_007 = _r(
    "BR-CBPR-PACS-007", "CBPR-PACS",
    "CBPR+ BAH: MsgDefIdr muss 'pacs.008.001.08' sein",
    None,
    "CBPR+ BAH Usage Guidelines",
    violatable=True,
)

BR_CBPR_PACS_008 = _r(
    "BR-CBPR-PACS-008", "CBPR-PACS",
    "CBPR+ BAH: BizSvc muss 'swift.cbprplus.04' sein",
    None,
    "CBPR+ BAH Usage Guidelines",
    violatable=True,
)

BR_CBPR_PACS_009 = _r(
    "BR-CBPR-PACS-009", "CBPR-PACS",
    "CBPR+ pacs.008: IntrBkSttlmDt muss ein gueltiger Banktag sein (Format YYYY-MM-DD)",
    None,
    "CBPR+ Usage Guidelines SR2026",
)

BR_CBPR_PACS_010 = _r(
    "BR-CBPR-PACS-010", "CBPR-PACS",
    "CBPR+ pacs.008: ChrgBr muss DEBT, CRED oder SHAR sein",
    None,
    "CBPR+ Usage Guidelines SR2026",
    violatable=True,
)

BR_CBPR_PACS_011 = _r(
    "BR-CBPR-PACS-011", "CBPR-PACS",
    "CBPR+ pacs.008: Waehrungscode muss gueltig sein (ISO 4217, 3 Grossbuchstaben)",
    None,
    "ISO 4217",
    violatable=True,
)

BR_CBPR_PACS_012 = _r(
    "BR-CBPR-PACS-012", "CBPR-PACS",
    "CBPR+ pacs.008: Wenn ChrgsInf vorhanden, muss jede Instanz Amt+Agt enthalten",
    None,
    "CBPR+ Usage Guidelines SR2026",
)

BR_CBPR_PACS_013 = _r(
    "BR-CBPR-PACS-013", "CBPR-PACS",
    "CBPR+ pacs.008: NbOfTxs im GrpHdr muss der Anzahl CdtTrfTxInf entsprechen",
    None,
    "CBPR+ Usage Guidelines SR2026",
)

BR_CBPR_PACS_014 = _r(
    "BR-CBPR-PACS-014", "CBPR-PACS",
    "CBPR+ pacs.008: CtrlSum muss der Summe aller IntrBkSttlmAmt entsprechen",
    None,
    "CBPR+ Usage Guidelines SR2026",
)

BR_CBPR_PACS_015 = _r(
    "BR-CBPR-PACS-015", "CBPR-PACS",
    "CBPR+ pacs.008: UETR muss UUIDv4-Format haben",
    None,
    "ISO 17442 / CBPR+ Rulebook",
    violatable=True,
)

BR_CBPR_PACS_016 = _r(
    "BR-CBPR-PACS-016", "CBPR-PACS",
    "CBPR+ pacs.008: Bei ChrgBr=CRED muss mindestens eine ChrgsInf-Instanz vorhanden sein "
    "(auch mit Betrag 0 wenn keine Gebuehren anfallen)",
    None,
    "CBPR+ Usage Guidelines SR2026 — Charge Bearer / Charges Information",
    violatable=True,
)

# --- Batch Booking ---

BR_BTCH_001 = _r(
    "BR-BTCH-001", "GEN",
    "BtchBookg=true ist nur sinnvoll bei NbOfTxs > 1 (Sammelauftrag mit nur einer Transaktion)",
    None,
    "Business Rules SPS 2025 §2.1.8",
)


# ---------------------------------------------------------------------------
# Katalog-Zugriff
# ---------------------------------------------------------------------------

RULE_CATALOG: Dict[str, BusinessRule] = {r.rule_id: r for r in _ALL_RULES}


def check_rule(rule_id: str, passed: bool, details: str = None):
    """Erstellt ein ValidationResult mit Beschreibung aus dem Katalog.

    Zentrale Hilfsfunktion — wird von business_rules.py und
    allen Payment-Handlern verwendet.
    """
    from src.models.testcase import ValidationResult
    rule = RULE_CATALOG[rule_id]
    return ValidationResult(
        rule_id=rule.rule_id,
        rule_description=rule.description,
        passed=passed,
        details=details,
    )


def get_rule(rule_id: str) -> BusinessRule:
    """Gibt eine Rule anhand ihrer ID zurück."""
    if rule_id not in RULE_CATALOG:
        raise KeyError(f"Unbekannte Business Rule: {rule_id}")
    return RULE_CATALOG[rule_id]


def get_rules_by_category(category: str) -> List[BusinessRule]:
    """Gibt alle Rules einer Kategorie zurück."""
    return [r for r in _ALL_RULES if r.category == category]


def get_rules_for_payment_type(payment_type: PaymentType) -> List[BusinessRule]:
    """Gibt alle Rules zurück, die für einen Zahlungstyp gelten."""
    return [
        r for r in _ALL_RULES
        if r.applies_to is None or payment_type in r.applies_to
    ]


def get_violatable_rules() -> List[BusinessRule]:
    """Gibt alle Rules zurück, die für Negative Testing verletzt werden können."""
    return [r for r in _ALL_RULES if r.violatable]


# ---------------------------------------------------------------------------
# Markdown-Export
# ---------------------------------------------------------------------------

_CATEGORY_NAMES = {
    "HDR": "Header-Regeln (A-Level)",
    "GEN": "Übergreifende Regeln",
    "ADDR": "Adress-Regeln",
    "IBAN-V": "IBAN-Validierung",
    "REF-V": "Referenz-Validierung",
    "SEPA": "SEPA-spezifisch (Typ S)",
    "QR": "QR-IBAN-spezifisch (Typ D/QR)",
    "IBAN": "Domestic-IBAN-spezifisch (Typ D/IBAN)",
    "DOM": "Domestic-übergreifend (Typ D)",
    "PURP": "Purpose (Verwendungszweck-Code)",
    "CTGP": "Category Purpose (Kategorie-Zweck)",
    "REM": "Remittance Information",
    "CCY": "Währung",
    "SIC5": "SIC5 Instant-spezifisch (CHF Sofortzahlung)",
    "SCT-INST": "SCT Inst-spezifisch (SEPA Instant Credit Transfer)",
    "CBPR": "CBPR+-spezifisch (Typ X)",
    "CGI": "CGI-MP-spezifisch (C2B global)",
    "CBPR-PACS": "CBPR+ pacs.008 (FI-to-FI Credit Transfer, SR2026)",
    "BIC": "BIC-Verzeichnis-Validierung",
}

_CATEGORY_ORDER = ["HDR", "GEN", "ADDR", "IBAN-V", "REF-V", "PURP", "CTGP", "REM", "CCY", "BIC", "SEPA", "QR", "IBAN", "DOM", "SIC5", "SCT-INST", "CBPR", "CGI", "CBPR-PACS"]


def rules_to_markdown() -> str:
    """Exportiert den gesamten Regelkatalog als Markdown-Tabelle."""
    lines = ["# Business Rules — SPS 2025", ""]

    for cat in _CATEGORY_ORDER:
        rules = get_rules_by_category(cat)
        if not rules:
            continue

        cat_name = _CATEGORY_NAMES.get(cat, cat)
        lines.append(f"## {cat_name}")
        lines.append("")
        lines.append("| Rule-ID | Beschreibung | Zahlungstypen | Spec-Referenz | Verletzbar |")
        lines.append("|---------|-------------|---------------|---------------|------------|")

        for r in rules:
            types = "Alle" if r.applies_to is None else ", ".join(pt.value for pt in r.applies_to)
            violatable = "Ja" if r.violatable else "—"
            lines.append(f"| {r.rule_id} | {r.description} | {types} | {r.spec_reference} | {violatable} |")

        lines.append("")

    lines.append(f"*{len(_ALL_RULES)} Regeln total.*")
    return "\n".join(lines)
