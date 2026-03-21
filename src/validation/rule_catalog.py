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

BR_GEN_006 = _r(
    "BR-GEN-006", "GEN",
    "Creditor-Name darf maximal 140 Zeichen lang sein (non-SEPA)",
    (PaymentType.DOMESTIC_QR, PaymentType.DOMESTIC_IBAN, PaymentType.CBPR_PLUS),
    "IG CT SPS 2025 v2.2 §4.3.7",
)

BR_GEN_007 = _r(
    "BR-GEN-007", "GEN",
    "Country-Code muss 2 Grossbuchstaben sein (ISO 3166-1)",
    None,
    "IG CT SPS 2025 §3.11, SwissQRBill",
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

# --- Remittance Information ---

BR_REM_002 = _r(
    "BR-REM-002", "REM",
    "Unstrukturierte Remittance Info darf maximal 140 Zeichen lang sein",
    None,
    "IG CT SPS 2025 §3.2.2",
    violatable=True,
)

# --- Currency ---

BR_CCY_001 = _r(
    "BR-CCY-001", "CCY",
    "Waehrungscode muss gueltig sein (ISO 4217, 3 Grossbuchstaben)",
    None,
    "IG CT SPS 2025, ISO 4217",
    violatable=True,
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
    "REM": "Remittance Information",
    "CCY": "Waehrung",
    "CBPR": "CBPR+-spezifisch (Typ X)",
}

_CATEGORY_ORDER = ["HDR", "GEN", "ADDR", "IBAN-V", "REF-V", "REM", "CCY", "SEPA", "QR", "IBAN", "CBPR"]


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
