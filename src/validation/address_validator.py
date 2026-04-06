"""Adress-Validierung und -Anreicherung (länderspezifisch).

Validiert strukturierte Postadressen (StrtNm, BldgNb, PstCd, TwnNm, Ctry)
gegen länderspezifische Formatregeln. Meldet nicht-konforme Adressen
mit Korrekturvorschlägen auf Deutsch.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Länderspezifische Adressformat-Datenbank
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CountryAddressFormat:
    """Formatregeln für Postadressen eines Landes."""

    country_code: str
    country_name_de: str
    postal_code_regex: str  # Regex für PLZ-Validierung
    postal_code_example: str  # Beispiel-PLZ für Fehlermeldungen
    postal_code_label: str  # Bezeichnung (z.B. "PLZ", "Postcode")
    requires_street: bool = True
    requires_building_nb: bool = False
    requires_postal_code: bool = True
    requires_town: bool = True
    max_street_length: int = 70
    max_town_length: int = 35
    max_postal_code_length: int = 16
    max_building_nb_length: int = 16


# Länderdatenbank: Häufigste Zielländer im Schweizer Zahlungsverkehr
COUNTRY_FORMATS: Dict[str, CountryAddressFormat] = {}


def _cf(
    cc: str,
    name_de: str,
    plz_regex: str,
    plz_example: str,
    plz_label: str = "PLZ",
    requires_street: bool = True,
    requires_building_nb: bool = False,
    requires_postal_code: bool = True,
    requires_town: bool = True,
    max_street_length: int = 70,
    max_town_length: int = 35,
    max_postal_code_length: int = 16,
    max_building_nb_length: int = 16,
) -> CountryAddressFormat:
    fmt = CountryAddressFormat(
        country_code=cc,
        country_name_de=name_de,
        postal_code_regex=plz_regex,
        postal_code_example=plz_example,
        postal_code_label=plz_label,
        requires_street=requires_street,
        requires_building_nb=requires_building_nb,
        requires_postal_code=requires_postal_code,
        requires_town=requires_town,
        max_street_length=max_street_length,
        max_town_length=max_town_length,
        max_postal_code_length=max_postal_code_length,
        max_building_nb_length=max_building_nb_length,
    )
    COUNTRY_FORMATS[cc] = fmt
    return fmt


# --- Europa ---
_cf("CH", "Schweiz", r"^\d{4}$", "8001", "PLZ")
_cf("LI", "Liechtenstein", r"^\d{4}$", "9490", "PLZ")
_cf("DE", "Deutschland", r"^\d{5}$", "10115", "PLZ")
_cf("AT", "Oesterreich", r"^\d{4}$", "1010", "PLZ")
_cf("FR", "Frankreich", r"^\d{5}$", "75001", "Code Postal")
_cf("IT", "Italien", r"^\d{5}$", "00100", "CAP")
_cf("ES", "Spanien", r"^\d{5}$", "28001", "Codigo Postal")
_cf("PT", "Portugal", r"^\d{4}(-\d{3})?$", "1000-001", "Codigo Postal")
_cf("NL", "Niederlande", r"^\d{4}\s?[A-Z]{2}$", "1011 AB", "Postcode")
_cf("BE", "Belgien", r"^\d{4}$", "1000", "Code Postal")
_cf("LU", "Luxemburg", r"^\d{4}$", "1009", "Code Postal")
_cf("GB", "Grossbritannien", r"^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$", "SW1A 1AA", "Postcode")
_cf("IE", "Irland", r"^[A-Z]\d{2}\s?[A-Z\d]{4}$", "D02 AF30", "Eircode",
    requires_postal_code=False)  # Eircode ist relativ neu, nicht immer vorhanden
_cf("DK", "Daenemark", r"^\d{4}$", "1000", "Postnummer")
_cf("SE", "Schweden", r"^\d{3}\s?\d{2}$", "111 22", "Postnummer")
_cf("NO", "Norwegen", r"^\d{4}$", "0001", "Postnummer")
_cf("FI", "Finnland", r"^\d{5}$", "00100", "Postinumero")
_cf("PL", "Polen", r"^\d{2}-\d{3}$", "00-001", "Kod pocztowy")
_cf("CZ", "Tschechien", r"^\d{3}\s?\d{2}$", "100 00", "PSC")
_cf("SK", "Slowakei", r"^\d{3}\s?\d{2}$", "811 01", "PSC")
_cf("HU", "Ungarn", r"^\d{4}$", "1011", "Iranyitoszam")
_cf("GR", "Griechenland", r"^\d{3}\s?\d{2}$", "105 57", "TK")
_cf("RO", "Rumaenien", r"^\d{6}$", "010001", "Cod postal")
_cf("BG", "Bulgarien", r"^\d{4}$", "1000", "Postenski kod")
_cf("HR", "Kroatien", r"^\d{5}$", "10000", "Postanski broj")
_cf("SI", "Slowenien", r"^\d{4}$", "1000", "Postna stevilka")
_cf("EE", "Estland", r"^\d{5}$", "10111", "Postiindeks")
_cf("LV", "Lettland", r"^LV-\d{4}$", "LV-1001", "Pasta indekss")
_cf("LT", "Litauen", r"^LT-\d{5}$", "LT-01001", "Pasto kodas")
_cf("MT", "Malta", r"^[A-Z]{3}\s?\d{4}$", "VLT 1000", "Postcode")
_cf("CY", "Zypern", r"^\d{4}$", "1000", "Postal Code")

# --- Ausserhalb Europa (häufig im CBPR+-Verkehr) ---
_cf("US", "USA", r"^\d{5}(-\d{4})?$", "10001", "ZIP Code",
    max_street_length=70, max_town_length=35)
_cf("CA", "Kanada", r"^[A-Z]\d[A-Z]\s?\d[A-Z]\d$", "K1A 0B1", "Postal Code")
_cf("JP", "Japan", r"^\d{3}-\d{4}$", "100-0001", "Yubin Bango")
_cf("SG", "Singapur", r"^\d{6}$", "018956", "Postal Code")
_cf("HK", "Hongkong", r"^$", "", "Postal Code",
    requires_postal_code=False)  # Hongkong hat keine PLZ
_cf("AU", "Australien", r"^\d{4}$", "2000", "Postcode")
_cf("NZ", "Neuseeland", r"^\d{4}$", "6011", "Postcode")
_cf("AE", "VAE", r"^$", "", "Postal Code",
    requires_postal_code=False)  # UAE hat keine nationale PLZ
_cf("SA", "Saudi-Arabien", r"^\d{5}(-\d{4})?$", "11564", "Postal Code")
_cf("IN", "Indien", r"^\d{6}$", "110001", "PIN Code")
_cf("CN", "China", r"^\d{6}$", "100000", "Postal Code")
_cf("BR", "Brasilien", r"^\d{5}-?\d{3}$", "01001-000", "CEP")
_cf("MX", "Mexiko", r"^\d{5}$", "06600", "Codigo Postal")
_cf("ZA", "Suedafrika", r"^\d{4}$", "2000", "Postal Code")
_cf("IL", "Israel", r"^\d{7}$", "6100000", "Mikud")
_cf("TR", "Tuerkei", r"^\d{5}$", "06100", "Posta Kodu")


# ---------------------------------------------------------------------------
# Adress-Validierungsergebnisse
# ---------------------------------------------------------------------------

@dataclass
class AddressValidationIssue:
    """Ein einzelnes Validierungsproblem einer Adresse."""

    field: str  # z.B. "PstCd", "StrtNm", "TwnNm"
    issue_type: str  # "missing", "format", "length"
    message: str  # Deutsche Fehlermeldung
    suggestion: Optional[str] = None  # Korrekturvorschlag


@dataclass
class AddressValidationResult:
    """Gesamtergebnis der Adress-Validierung."""

    valid: bool
    country_code: str
    issues: List[AddressValidationIssue] = field(default_factory=list)
    enriched_address: Optional[Dict[str, str]] = None


# ---------------------------------------------------------------------------
# Validierungslogik
# ---------------------------------------------------------------------------

def validate_address(
    address: Dict[str, str],
    role: str = "Creditor",
) -> AddressValidationResult:
    """Validiert eine strukturierte Adresse gegen länderspezifische Regeln.

    Args:
        address: Dict mit Keys StrtNm, BldgNb, PstCd, TwnNm, Ctry
        role: "Creditor" oder "Debtor" (für Fehlermeldungen)

    Returns:
        AddressValidationResult mit Issues und optionaler Anreicherung
    """
    issues: List[AddressValidationIssue] = []

    ctry = address.get("Ctry", "")
    if not ctry:
        issues.append(AddressValidationIssue(
            field="Ctry",
            issue_type="missing",
            message=f"{role}-Adresse: Ländercode (Ctry) fehlt",
        ))
        return AddressValidationResult(valid=False, country_code="", issues=issues)

    fmt = COUNTRY_FORMATS.get(ctry)
    if not fmt:
        # Unbekanntes Land — nur generische Prüfungen
        return _validate_generic(address, role, ctry)

    # Pflichtfelder prüfen
    if fmt.requires_street and not address.get("StrtNm"):
        issues.append(AddressValidationIssue(
            field="StrtNm",
            issue_type="missing",
            message=f"{role}-Adresse ({fmt.country_name_de}): Strassenname (StrtNm) fehlt",
            suggestion="Strassenname ist Pflicht fuer strukturierte Adressen",
        ))

    if not address.get("TwnNm"):
        issues.append(AddressValidationIssue(
            field="TwnNm",
            issue_type="missing",
            message=f"{role}-Adresse ({fmt.country_name_de}): Ortsname (TwnNm) fehlt",
        ))

    # PLZ-Validierung
    pst_cd = address.get("PstCd", "")
    if fmt.requires_postal_code:
        if not pst_cd:
            issues.append(AddressValidationIssue(
                field="PstCd",
                issue_type="missing",
                message=f"{role}-Adresse ({fmt.country_name_de}): "
                        f"{fmt.postal_code_label} (PstCd) fehlt",
                suggestion=f"Beispiel: {fmt.postal_code_example}",
            ))
        elif not re.match(fmt.postal_code_regex, pst_cd):
            issues.append(AddressValidationIssue(
                field="PstCd",
                issue_type="format",
                message=f"{role}-Adresse ({fmt.country_name_de}): "
                        f"{fmt.postal_code_label} '{pst_cd}' hat ungültiges Format",
                suggestion=f"Erwartetes Format: {fmt.postal_code_example}",
            ))
    elif pst_cd and fmt.postal_code_regex and not re.match(fmt.postal_code_regex, pst_cd):
        # PLZ ist optional, aber wenn vorhanden, Format prüfen
        issues.append(AddressValidationIssue(
            field="PstCd",
            issue_type="format",
            message=f"{role}-Adresse ({fmt.country_name_de}): "
                    f"{fmt.postal_code_label} '{pst_cd}' hat ungültiges Format",
            suggestion=f"Erwartetes Format: {fmt.postal_code_example}",
        ))

    # Feldlängen prüfen
    _check_field_length(address, "StrtNm", fmt.max_street_length,
                        "Strassenname", role, fmt.country_name_de, issues)
    _check_field_length(address, "TwnNm", fmt.max_town_length,
                        "Ortsname", role, fmt.country_name_de, issues)
    _check_field_length(address, "PstCd", fmt.max_postal_code_length,
                        fmt.postal_code_label, role, fmt.country_name_de, issues)
    _check_field_length(address, "BldgNb", fmt.max_building_nb_length,
                        "Hausnummer", role, fmt.country_name_de, issues)

    return AddressValidationResult(
        valid=len(issues) == 0,
        country_code=ctry,
        issues=issues,
    )


def _validate_generic(
    address: Dict[str, str],
    role: str,
    ctry: str,
) -> AddressValidationResult:
    """Generische Validierung für Länder ohne spezifische Formatregeln."""
    issues: List[AddressValidationIssue] = []

    if not address.get("TwnNm"):
        issues.append(AddressValidationIssue(
            field="TwnNm",
            issue_type="missing",
            message=f"{role}-Adresse (Land {ctry}): Ortsname (TwnNm) fehlt",
        ))

    # Generische Feldlängenprüfung (ISO 20022 Limits)
    _check_field_length(address, "StrtNm", 70, "Strassenname", role, ctry, issues)
    _check_field_length(address, "TwnNm", 35, "Ortsname", role, ctry, issues)
    _check_field_length(address, "PstCd", 16, "PLZ", role, ctry, issues)
    _check_field_length(address, "BldgNb", 16, "Hausnummer", role, ctry, issues)

    return AddressValidationResult(
        valid=len(issues) == 0,
        country_code=ctry,
        issues=issues,
    )


def _check_field_length(
    address: Dict[str, str],
    field: str,
    max_length: int,
    field_label: str,
    role: str,
    country_label: str,
    issues: List[AddressValidationIssue],
) -> None:
    """Prüft die Feldlänge und fügt ggf. ein Issue hinzu."""
    value = address.get(field, "")
    if value and len(value) > max_length:
        issues.append(AddressValidationIssue(
            field=field,
            issue_type="length",
            message=f"{role}-Adresse ({country_label}): "
                    f"{field_label} hat {len(value)} Zeichen (max {max_length})",
            suggestion=f"Bitte auf {max_length} Zeichen kürzen",
        ))


# ---------------------------------------------------------------------------
# Adress-Anreicherung
# ---------------------------------------------------------------------------

def enrich_address(
    address: Dict[str, str],
) -> Tuple[Dict[str, str], List[str]]:
    """Reichert eine minimale Adresse an (Defaults setzen, Normalisierung).

    Returns:
        Tuple aus (angereicherter Adresse, Liste von Anreicherungs-Hinweisen)
    """
    enriched = dict(address)
    hints: List[str] = []

    ctry = enriched.get("Ctry", "")
    fmt = COUNTRY_FORMATS.get(ctry) if ctry else None

    # PLZ-Normalisierung: Leerzeichen bei bestimmten Ländern
    pst_cd = enriched.get("PstCd", "")
    if pst_cd and fmt:
        normalized = _normalize_postal_code(pst_cd, ctry)
        if normalized != pst_cd:
            enriched["PstCd"] = normalized
            hints.append(
                f"{fmt.postal_code_label} normalisiert: '{pst_cd}' -> '{normalized}'"
            )

    return enriched, hints


def convert_unstructured_to_structured(
    address: Dict[str, str],
) -> Tuple[Dict[str, str], bool]:
    """Konvertiert eine unstrukturierte Adresse (AdrLine) in strukturierte Felder.

    Versucht AdrLine-Zeilen in StrtNm, BldgNb, PstCd, TwnNm aufzuteilen.
    Behält vorhandene strukturierte Felder bei (Ctry bleibt erhalten).

    Heuristik für 2 Zeilen:
      Zeile 1: "Strassenname Hausnummer" → StrtNm + BldgNb
      Zeile 2: "PLZ Ort" → PstCd + TwnNm

    Returns:
        Tuple aus (konvertierter Adresse, True wenn Konversion erfolgreich)
    """
    adr_line = address.get("AdrLine", "")
    if not adr_line:
        return address, False

    lines = [line.strip() for line in adr_line.split("|") if line.strip()]
    if not lines:
        return address, False

    result = {k: v for k, v in address.items() if k != "AdrLine"}

    ctry = result.get("Ctry", "")
    fmt = COUNTRY_FORMATS.get(ctry) if ctry else None

    if len(lines) == 2:
        # Zeile 1: Strasse + Hausnummer
        street_line = lines[0]
        # Hausnummer am Ende extrahieren (z.B. "Bahnhofstr. 12" oder "123 Main St")
        street_match = re.match(r'^(.+?)\s+(\d+[a-zA-Z]?)$', street_line)
        if street_match:
            result.setdefault("StrtNm", street_match.group(1))
            result.setdefault("BldgNb", street_match.group(2))
        else:
            result.setdefault("StrtNm", street_line)

        # Zeile 2: PLZ + Ort
        city_line = lines[1]
        if fmt and fmt.postal_code_regex:
            plz_match = re.match(r'^(' + fmt.postal_code_regex.lstrip('^').rstrip('$') + r')\s+(.+)$', city_line)
            if plz_match:
                result.setdefault("PstCd", plz_match.group(1))
                result.setdefault("TwnNm", plz_match.group(plz_match.lastindex))
            else:
                # Fallback: generischer PLZ-Muster
                generic_match = re.match(r'^([A-Z\d][\w\s-]{1,15}?)\s+(.+)$', city_line)
                if generic_match:
                    result.setdefault("PstCd", generic_match.group(1).strip())
                    result.setdefault("TwnNm", generic_match.group(2).strip())
                else:
                    result.setdefault("TwnNm", city_line)
        else:
            # Ohne Länderformat: generisch aufteilen
            generic_match = re.match(r'^(\S+)\s+(.+)$', city_line)
            if generic_match:
                result.setdefault("PstCd", generic_match.group(1))
                result.setdefault("TwnNm", generic_match.group(2))
            else:
                result.setdefault("TwnNm", city_line)

    elif len(lines) == 1:
        # Einzelne Zeile: als StrtNm verwenden
        result.setdefault("StrtNm", lines[0])
    else:
        # 3+ Zeilen: Zeile 1 = Strasse, letzte = PLZ+Ort, Rest ignorieren
        result.setdefault("StrtNm", lines[0])
        city_line = lines[-1]
        generic_match = re.match(r'^(\S+)\s+(.+)$', city_line)
        if generic_match:
            result.setdefault("PstCd", generic_match.group(1))
            result.setdefault("TwnNm", generic_match.group(2))
        else:
            result.setdefault("TwnNm", city_line)

    # Erfolgreich wenn mindestens StrtNm und TwnNm vorhanden
    converted = bool(result.get("StrtNm") and result.get("TwnNm"))
    return result, converted


def _normalize_postal_code(postal_code: str, country_code: str) -> str:
    """Normalisiert PLZ-Formate (z.B. Leerzeichen hinzufügen/entfernen)."""
    pc = postal_code.strip()

    if country_code == "GB":
        # UK Postcode: Leerzeichen vor den letzten 3 Zeichen sicherstellen
        pc_clean = pc.replace(" ", "")
        if len(pc_clean) >= 5:
            return pc_clean[:-3] + " " + pc_clean[-3:]
    elif country_code in ("SE", "CZ", "SK", "GR"):
        # Skandinavien/Osteuropa: Leerzeichen in der Mitte
        pc_clean = pc.replace(" ", "")
        if len(pc_clean) == 5:
            return pc_clean[:3] + " " + pc_clean[3:]
    elif country_code == "NL":
        # NL: 4 Ziffern + Leerzeichen + 2 Buchstaben
        pc_clean = pc.replace(" ", "")
        if len(pc_clean) == 6 and pc_clean[:4].isdigit():
            return pc_clean[:4] + " " + pc_clean[4:].upper()
    elif country_code == "CA":
        # Kanada: A1A 1A1
        pc_clean = pc.replace(" ", "").upper()
        if len(pc_clean) == 6:
            return pc_clean[:3] + " " + pc_clean[3:]
    elif country_code == "LV":
        # Lettland: LV-xxxx
        if pc.isdigit() and len(pc) == 4:
            return "LV-" + pc
    elif country_code == "LT":
        # Litauen: LT-xxxxx
        if pc.isdigit() and len(pc) == 5:
            return "LT-" + pc

    return pc
