"""Business-Rule-Engine: Übergreifende Regeln und Orchestrierung.

Alle Rule-Metadaten kommen aus dem zentralen `rule_catalog`.
Diese Datei enthält nur die Validierungs- und Violation-Logik.
"""

import random
import re
from typing import List

from src.data_factory.generator import validate_sps_charset
from src.data_factory.iban import validate_iban, validate_iban_length
from src.models.testcase import (
    PaymentInstruction,
    PaymentType,
    Standard,
    TestCase,
    ValidationResult,
)
from src.payment_types import get_handler
from src.validation.address_validator import validate_address
from src.validation.bic_directory import get_bic_directory
from src.validation.rule_catalog import check_rule as _check


# ---------------------------------------------------------------------------
# Referenzfeld-Zeichensatz
# ---------------------------------------------------------------------------

def _validate_ref_charset(value: str) -> bool:
    """Prüft Referenzfeld-Zeichensatz (BR-GEN-009)."""
    if not value:
        return True
    if value.startswith("/") or value.endswith("/"):
        return False
    if "//" in value:
        return False
    return True




# ---------------------------------------------------------------------------
# Validierung: Übergreifende Regeln
# ---------------------------------------------------------------------------

def validate_general_rules(
    instruction: PaymentInstruction,
    testcase: TestCase,
) -> List[ValidationResult]:
    """Validiert zahlungstyp-übergreifende Business Rules."""
    results = []
    txs = instruction.transactions

    # BR-HDR-002: NbOfTxs Konsistenz (vom Builder sichergestellt)
    results.append(_check("BR-HDR-002", True))

    # BR-HDR-003: CtrlSum Konsistenz (vom Builder sichergestellt)
    results.append(_check("BR-HDR-003", True))

    # BR-HDR-004: InitgPty vorhanden
    has_name = bool(instruction.debtor.name)
    results.append(_check(
        "BR-HDR-004", has_name,
        "InitgPty/Nm fehlt" if not has_name else None,
    ))

    # BR-GEN-005: ReqdExctnDt Bankarbeitstag
    results.append(_check("BR-GEN-005", bool(instruction.reqd_exctn_dt)))

    # BR-GEN-009: Referenzfeld-Zeichensatz
    ref_fields = [
        ("PmtInfId", instruction.pmt_inf_id),
        ("MsgId", instruction.msg_id),
    ]
    for tx in txs:
        ref_fields.append(("EndToEndId", tx.end_to_end_id))

    for field_name, value in ref_fields:
        if value:
            valid = _validate_ref_charset(value)
            results.append(_check(
                "BR-GEN-009", valid,
                f"{field_name}='{value}' verletzt Zeichensatz-Regeln" if not valid else None,
            ))

    # BR-GEN-001: Betrag max 2 Dezimalstellen
    for tx in txs:
        dec_tuple = tx.amount.as_tuple()
        decimal_places = max(0, -dec_tuple.exponent) if dec_tuple.exponent < 0 else 0
        results.append(_check(
            "BR-GEN-001", decimal_places <= 2,
            f"Betrag {tx.amount} hat {decimal_places} Dezimalstellen" if decimal_places > 2 else None,
        ))

    # BR-GEN-010: Betrag > 0
    for tx in txs:
        results.append(_check(
            "BR-GEN-010", tx.amount > 0,
            f"Betrag ist {tx.amount}" if tx.amount <= 0 else None,
        ))

    # BR-GEN-012: SPS-Zeichensatz (alle Textfelder)
    text_fields = [("Debtor Name", instruction.debtor.name)]
    if instruction.debtor.street:
        text_fields.append(("Debtor Strasse", instruction.debtor.street))
    if instruction.debtor.town:
        text_fields.append(("Debtor Ort", instruction.debtor.town))
    for tx in txs:
        text_fields.append(("Creditor Name", tx.creditor_name))
        if tx.creditor_address:
            for key, val in tx.creditor_address.items():
                if key != "Ctry":
                    text_fields.append((f"Creditor {key}", val))
        if tx.remittance_info:
            rmt_val = tx.remittance_info.get("value", "")
            rmt_type = tx.remittance_info.get("type", "")
            if rmt_type == "USTRD" and rmt_val:
                text_fields.append(("Verwendungszweck", rmt_val))

    for field_name, value in text_fields:
        if value and not validate_sps_charset(value):
            results.append(_check(
                "BR-GEN-012", False,
                f"{field_name}: '{value[:50]}...' enthält ungültige Zeichen" if len(value) > 50
                else f"{field_name}: '{value}' enthält ungültige Zeichen",
            ))

    # BR-IBAN-V01 / V02: IBAN-Validierung (nur für IBAN-basierte Konten)
    iban_fields = [("Debtor IBAN", instruction.debtor.iban)]
    for tx in txs:
        # Non-IBAN-Konten (creditor_account_id) überspringen
        if tx.creditor_iban:
            iban_fields.append(("Creditor IBAN", tx.creditor_iban))

    for field_name, iban in iban_fields:
        results.append(_check(
            "BR-IBAN-V01", validate_iban(iban),
            f"IBAN '{iban}' ist ungültig" if not validate_iban(iban) else None,
        ))
        results.append(_check(
            "BR-IBAN-V02", validate_iban_length(iban),
            f"IBAN '{iban}' hat falsche Länge" if not validate_iban_length(iban) else None,
        ))

    # BR-GEN-002: BIC-Format (8 oder 11 alphanumerische Zeichen)
    bic_pattern = re.compile(r'^[A-Z0-9]{8}$|^[A-Z0-9]{11}$')
    bic_fields = []
    if instruction.debtor.bic:
        bic_fields.append(("Debtor BIC", instruction.debtor.bic))
    for tx in txs:
        if tx.creditor_bic:
            bic_fields.append(("Creditor BIC", tx.creditor_bic))

    for field_name, bic in bic_fields:
        valid = bool(bic_pattern.match(bic))
        results.append(_check(
            "BR-GEN-002", valid,
            f"{field_name} '{bic}' hat ungültiges Format" if not valid else None,
        ))

    # BR-BIC-001: BIC-Verzeichnis-Validierung (optional, nur wenn konfiguriert)
    bic_dir = get_bic_directory()
    if bic_dir is not None:
        for field_name, bic in bic_fields:
            bic_valid, bic_error = bic_dir.validate_bic(bic)
            results.append(_check(
                "BR-BIC-001", bic_valid,
                f"{field_name}: {bic_error}" if bic_error else None,
            ))

    # BR-GEN-013: LEI-Format (ISO 17442: 18 alphanumerisch + 2 Prüfziffern)
    lei_pattern = re.compile(r'^[A-Z0-9]{18}[0-9]{2}$')
    lei_fields = []
    if instruction.debtor.lei:
        lei_fields.append(("Debtor LEI", instruction.debtor.lei))
    for tx in txs:
        if tx.creditor_lei:
            lei_fields.append(("Creditor LEI", tx.creditor_lei))

    for field_name, lei in lei_fields:
        valid = bool(lei_pattern.match(lei))
        results.append(_check(
            "BR-GEN-013", valid,
            f"{field_name} '{lei}' hat ungültiges LEI-Format" if not valid else None,
        ))

    # BR-GEN-007: Country-Code 2 Großbuchstaben
    country_pattern = re.compile(r'^[A-Z]{2}$')
    country_fields = []
    if instruction.debtor.country:
        country_fields.append(("Debtor Country", instruction.debtor.country))
    for tx in txs:
        if tx.creditor_address and "Ctry" in tx.creditor_address:
            country_fields.append(("Creditor Country", tx.creditor_address["Ctry"]))

    for field_name, ctry in country_fields:
        valid = bool(country_pattern.match(ctry))
        results.append(_check(
            "BR-GEN-007", valid,
            f"{field_name} '{ctry}' ist kein gültiger ISO 3166-1 Code" if not valid else None,
        ))

    # BR-ADDR-001: Strukturierte Adresse — TwnNm und Ctry Pflicht
    for tx in txs:
        if tx.creditor_address:
            has_town = bool(tx.creditor_address.get("TwnNm"))
            has_ctry = bool(tx.creditor_address.get("Ctry"))
            if not has_town or not has_ctry:
                missing = []
                if not has_town:
                    missing.append("TwnNm")
                if not has_ctry:
                    missing.append("Ctry")
                results.append(_check(
                    "BR-ADDR-001", False,
                    f"Creditor-Adresse: {', '.join(missing)} fehlt",
                ))

    # BR-ADDR-002: Creditor muss strukturierte Adresse haben (StrtNm+TwnNm+Ctry)
    for tx in txs:
        if tx.creditor_address:
            has_strt = bool(tx.creditor_address.get("StrtNm"))
            has_town = bool(tx.creditor_address.get("TwnNm"))
            has_ctry = bool(tx.creditor_address.get("Ctry"))
            structured = has_strt and has_town and has_ctry
            results.append(_check(
                "BR-ADDR-002", structured,
                f"Creditor-Adresse nicht vollständig strukturiert" if not structured else None,
            ))
        else:
            results.append(_check(
                "BR-ADDR-002", False,
                "Creditor-Adresse fehlt (strukturiert erforderlich)",
            ))

    # BR-ADDR-003: Debtor-Adresse — wenn Felder vorhanden, TwnNm+Ctry Pflicht
    dbtr = instruction.debtor
    has_any_addr = dbtr.street or dbtr.town or dbtr.postal_code
    if has_any_addr:
        has_town = bool(dbtr.town)
        has_ctry = bool(dbtr.country)
        results.append(_check(
            "BR-ADDR-003", has_town and has_ctry,
            "Debtor-Adresse: TwnNm oder Ctry fehlt" if not (has_town and has_ctry) else None,
        ))

    # BR-ADDR-010/011/012: Länderspezifische Adress-Validierung
    for tx in txs:
        if tx.creditor_address:
            addr_result = validate_address(tx.creditor_address, role="Creditor")
            for issue in addr_result.issues:
                if issue.issue_type == "format":
                    detail = issue.message
                    if issue.suggestion:
                        detail += f" ({issue.suggestion})"
                    results.append(_check("BR-ADDR-010", False, detail))
                elif issue.issue_type == "length":
                    results.append(_check("BR-ADDR-011", False, issue.message))
                elif issue.issue_type == "missing" and issue.field == "PstCd":
                    detail = issue.message
                    if issue.suggestion:
                        detail += f" ({issue.suggestion})"
                    results.append(_check("BR-ADDR-012", False, detail))

    # Debtor-Adresse: länderspezifische Validierung
    if has_any_addr and dbtr.country:
        dbtr_addr = {}
        if dbtr.street:
            dbtr_addr["StrtNm"] = dbtr.street
        if dbtr.building:
            dbtr_addr["BldgNb"] = dbtr.building
        if dbtr.postal_code:
            dbtr_addr["PstCd"] = dbtr.postal_code
        if dbtr.town:
            dbtr_addr["TwnNm"] = dbtr.town
        dbtr_addr["Ctry"] = dbtr.country

        dbtr_addr_result = validate_address(dbtr_addr, role="Debtor")
        for issue in dbtr_addr_result.issues:
            if issue.issue_type == "format":
                detail = issue.message
                if issue.suggestion:
                    detail += f" ({issue.suggestion})"
                results.append(_check("BR-ADDR-010", False, detail))
            elif issue.issue_type == "length":
                results.append(_check("BR-ADDR-011", False, issue.message))
            elif issue.issue_type == "missing" and issue.field == "PstCd":
                detail = issue.message
                if issue.suggestion:
                    detail += f" ({issue.suggestion})"
                results.append(_check("BR-ADDR-012", False, detail))

    # BR-GEN-006: Creditor-Name max 140 Zeichen (non-SEPA)
    if testcase.payment_type != PaymentType.SEPA:
        for tx in txs:
            if len(tx.creditor_name) > 140:
                results.append(_check(
                    "BR-GEN-006", False,
                    f"Name hat {len(tx.creditor_name)} Zeichen (max 140)",
                ))

    # BR-PURP-001: Purpose/Cd muss gültiger ExternalPurpose1Code sein (1–4 Zeichen)
    purpose_pattern = re.compile(r'^[A-Z]{4}$')
    for tx in txs:
        if tx.purpose_code:
            valid = bool(purpose_pattern.match(tx.purpose_code))
            results.append(_check(
                "BR-PURP-001", valid,
                f"Purpose Code '{tx.purpose_code}' ist ungültig (erwartet: 4 Grossbuchstaben)"
                if not valid else None,
            ))

    # BR-CTGP-001: Category Purpose Code (1–4 Grossbuchstaben)
    ctgp_pattern = re.compile(r'^[A-Z]{4}$')
    if instruction.category_purpose:
        valid = bool(ctgp_pattern.match(instruction.category_purpose))
        results.append(_check(
            "BR-CTGP-001", valid,
            f"CtgyPurp/Cd '{instruction.category_purpose}' ist ungültig (erwartet: 4 Grossbuchstaben)"
            if not valid else None,
        ))

    # BR-REF-V01: SCOR-Format (RF + 2 Prüfziffern, max 25 Zeichen)
    scor_pattern = re.compile(r'^RF[0-9]{2}[A-Za-z0-9]{1,21}$')
    for tx in txs:
        if tx.remittance_info and tx.remittance_info.get("type") == "SCOR":
            ref = tx.remittance_info.get("value", "")
            valid = bool(scor_pattern.match(ref)) and len(ref) <= 25
            results.append(_check(
                "BR-REF-V01", valid,
                f"SCOR '{ref}' hat ungültiges Format" if not valid else None,
            ))

    # BR-BTCH-001: BtchBookg=true bei nur einer Transaktion ist fragwürdig
    if instruction.batch_booking is True:
        nb_txs = len(txs)
        valid = nb_txs > 1
        results.append(_check(
            "BR-BTCH-001", valid,
            f"BtchBookg=true bei NbOfTxs={nb_txs} (Sammelauftrag mit nur einer Transaktion)"
            if not valid else None,
        ))

    return results


# ---------------------------------------------------------------------------
# Orchestrierung
# ---------------------------------------------------------------------------

def validate_all_business_rules(
    instruction: PaymentInstruction,
    testcase: TestCase,
) -> List[ValidationResult]:
    """Führt alle Business-Rule-Validierungen durch."""
    results = []
    results.extend(validate_general_rules(instruction, testcase))

    # BR-SEPA-003: ChrgBr muss SLEV sein (braucht instruction.charge_bearer)
    if testcase.payment_type == PaymentType.SEPA:
        cb = instruction.charge_bearer or ""
        results.append(_check(
            "BR-SEPA-003", cb == "SLEV",
            f"ChrgBr ist '{cb}'" if cb != "SLEV" else None,
        ))

    # BR-DOM-001: ChrgBr darf bei Domestic-Zahlungen nicht gesetzt sein
    if testcase.payment_type in (PaymentType.DOMESTIC_QR, PaymentType.DOMESTIC_IBAN):
        cb = instruction.charge_bearer or ""
        results.append(_check(
            "BR-DOM-001", cb == "",
            f"ChrgBr ist '{cb}' (bei Domestic-Zahlungen nicht erlaubt)" if cb else None,
        ))

    # BR-CBPR-003: ChrgBr darf nicht SLEV sein (CBPR+ erlaubt nur DEBT/CRED/SHAR)
    if testcase.payment_type == PaymentType.CBPR_PLUS:
        cb = instruction.charge_bearer or ""
        valid_cb = cb in ("DEBT", "CRED", "SHAR")
        results.append(_check(
            "BR-CBPR-003", valid_cb,
            f"ChrgBr '{cb}' ist ungültig für CBPR+ (SLEV nicht erlaubt)" if not valid_cb else None,
        ))

    # BR-REM-002: USTRD max 140 Zeichen
    for tx in instruction.transactions:
        if tx.remittance_info and tx.remittance_info.get("type") == "USTRD":
            val = tx.remittance_info.get("value", "")
            results.append(_check(
                "BR-REM-002", len(val) <= 140,
                f"Ustrd hat {len(val)} Zeichen (max 140)" if len(val) > 140 else None,
            ))

    # BR-CCY-001: Währungscode 3 Großbuchstaben
    ccy_pattern = re.compile(r'^[A-Z]{3}$')
    for tx in instruction.transactions:
        valid_ccy = bool(ccy_pattern.match(tx.currency))
        results.append(_check(
            "BR-CCY-001", valid_ccy,
            f"Währung '{tx.currency}' ist kein gültiger ISO 4217 Code" if not valid_ccy else None,
        ))

    # --- SIC5 Instant Rules (wenn testcase.instant=True und Domestic-IBAN) ---
    if testcase.instant and testcase.payment_type == PaymentType.DOMESTIC_IBAN:
        # BR-SIC5-001: Währung muss CHF sein
        for tx in instruction.transactions:
            results.append(_check(
                "BR-SIC5-001", tx.currency == "CHF",
                f"Instant: Währung ist '{tx.currency}' (muss CHF sein)" if tx.currency != "CHF" else None,
            ))

        # BR-SIC5-002: Creditor-IBAN muss CH oder LI sein
        for tx in instruction.transactions:
            iban_country = tx.creditor_iban[:2].upper() if tx.creditor_iban and len(tx.creditor_iban) >= 2 else ""
            results.append(_check(
                "BR-SIC5-002", iban_country in ("CH", "LI"),
                f"Instant: Creditor-IBAN Länderkennzeichen '{iban_country}' ist nicht CH/LI"
                if iban_country not in ("CH", "LI") else None,
            ))

        # BR-SIC5-003: ServiceLevel muss INST sein
        svc = instruction.service_level or ""
        results.append(_check(
            "BR-SIC5-003", svc == "INST",
            f"Instant: ServiceLevel ist '{svc}' (muss INST sein)" if svc != "INST" else None,
        ))

        # BR-SIC5-004: LocalInstrument muss INST sein
        lcl = instruction.local_instrument or ""
        results.append(_check(
            "BR-SIC5-004", lcl == "INST",
            f"Instant: LocalInstrument ist '{lcl}' (muss INST sein)" if lcl != "INST" else None,
        ))

    # --- SCT Inst Rules (wenn testcase.instant=True und SEPA) ---
    if testcase.instant and testcase.payment_type == PaymentType.SEPA:
        # BR-SCT-INST-001: Währung muss EUR sein
        for tx in instruction.transactions:
            results.append(_check(
                "BR-SCT-INST-001", tx.currency == "EUR",
                f"SCT Inst: Währung ist '{tx.currency}' (muss EUR sein)" if tx.currency != "EUR" else None,
            ))

        # BR-SCT-INST-002: Betrag max 100'000 EUR
        from decimal import Decimal
        sct_inst_max = Decimal("100000")
        for tx in instruction.transactions:
            results.append(_check(
                "BR-SCT-INST-002", tx.amount <= sct_inst_max,
                f"SCT Inst: Betrag {tx.amount} EUR übersteigt Limit von 100'000 EUR"
                if tx.amount > sct_inst_max else None,
            ))

        # BR-SCT-INST-003: ServiceLevel muss INST sein
        svc = instruction.service_level or ""
        results.append(_check(
            "BR-SCT-INST-003", svc == "INST",
            f"SCT Inst: ServiceLevel ist '{svc}' (muss INST sein)" if svc != "INST" else None,
        ))

        # BR-SCT-INST-004: LocalInstrument muss INST sein
        lcl = instruction.local_instrument or ""
        results.append(_check(
            "BR-SCT-INST-004", lcl == "INST",
            f"SCT Inst: LocalInstrument ist '{lcl}' (muss INST sein)" if lcl != "INST" else None,
        ))

        # BR-SCT-INST-005: ChrgBr muss SLEV sein
        cb = instruction.charge_bearer or ""
        results.append(_check(
            "BR-SCT-INST-005", cb == "SLEV",
            f"SCT Inst: ChrgBr ist '{cb}' (muss SLEV sein)" if cb != "SLEV" else None,
        ))

    # --- RgltryRptg-Regeln (CGI-MP / CBPR+) ---
    for tx in instruction.transactions:
        if tx.regulatory_reporting:
            reg = tx.regulatory_reporting

            # BR-CGI-PURP-02: DbtCdtRptgInd (DEBT/CRED/BOTH) Pflicht
            ind = reg.get("DbtCdtRptgInd", "")
            results.append(_check(
                "BR-CGI-PURP-02", ind in ("DEBT", "CRED", "BOTH"),
                f"RgltryRptg: DbtCdtRptgInd ist '{ind}' (DEBT/CRED/BOTH erwartet)"
                if ind not in ("DEBT", "CRED", "BOTH") else None,
            ))

            # BR-CGI-RGRP-01: Wenn Dtls vorhanden, Tp Pflicht
            has_dtls = any(k.startswith("Dtls.") for k in reg)
            has_tp = bool(reg.get("Dtls.Tp"))
            if has_dtls:
                results.append(_check(
                    "BR-CGI-RGRP-01", has_tp,
                    "RgltryRptg: Details vorhanden aber Tp fehlt" if not has_tp else None,
                ))

            # BR-CGI-RGRP-02: Code max 10 Zeichen
            cd = reg.get("Dtls.Cd", "")
            if cd:
                results.append(_check(
                    "BR-CGI-RGRP-02", len(cd) <= 10,
                    f"RgltryRptg: Code '{cd}' hat {len(cd)} Zeichen (max 10)"
                    if len(cd) > 10 else None,
                ))

    # --- CGI-MP Tax Remittance Validation (BR-CGI-TAX-*) ---
    if testcase.standard == Standard.CGI_MP:
        for tx in instruction.transactions:
            cat_purp = instruction.category_purpose or ""
            has_tax = bool(tx.tax_remittance)

            # BR-CGI-TAX-01: Wenn CtgyPurp=WHLD, Tax-Element erwartet
            if cat_purp == "WHLD":
                results.append(_check(
                    "BR-CGI-TAX-01", has_tax,
                    "CtgyPurp ist 'WHLD' aber kein TaxRmt vorhanden"
                    if not has_tax else None,
                ))

            if has_tax:
                tax = tx.tax_remittance
                # BR-CGI-TAX-02: Cdtr.TaxId und Dbtr.TaxId Pflicht
                cdtr_tax_id = bool(tax.get("Cdtr.TaxId"))
                dbtr_tax_id = bool(tax.get("Dbtr.TaxId"))
                both_ids = cdtr_tax_id and dbtr_tax_id
                detail = None
                if not both_ids:
                    missing = []
                    if not cdtr_tax_id:
                        missing.append("Cdtr.TaxId")
                    if not dbtr_tax_id:
                        missing.append("Dbtr.TaxId")
                    detail = f"TaxRmt: fehlende Pflichtfelder: {', '.join(missing)}"
                results.append(_check("BR-CGI-TAX-02", both_ids, detail))

                # BR-CGI-TAX-03: Mtd Pflicht
                has_mtd = bool(tax.get("Mtd"))
                results.append(_check(
                    "BR-CGI-TAX-03", has_mtd,
                    "TaxRmt: Mtd (Berechnungsmethode) fehlt" if not has_mtd else None,
                ))

    # --- CGI-MP Structured Address Enforcement (BR-CGI-ADDR-03) ---
    if testcase.standard == Standard.CGI_MP:
        _STRUCTURED_FIELDS = ("StrtNm", "PstCd", "TwnNm", "Ctry")
        for tx in instruction.transactions:
            if tx.creditor_address:
                has_adr_line = bool(tx.creditor_address.get("AdrLine"))
                missing = [f for f in _STRUCTURED_FIELDS if not tx.creditor_address.get(f)]
                structured_ok = not has_adr_line and not missing
                detail = None
                if not structured_ok:
                    parts = []
                    if has_adr_line:
                        parts.append("AdrLine ist bei CGI-MP nicht erlaubt")
                    if missing:
                        parts.append(f"fehlende Felder: {', '.join(missing)}")
                    detail = "Creditor-Adresse: " + "; ".join(parts)
                results.append(_check("BR-CGI-ADDR-03", structured_ok, detail))
            else:
                results.append(_check(
                    "BR-CGI-ADDR-03", False,
                    "Creditor-Adresse fehlt (CGI-MP erfordert strukturierte Adresse)",
                ))

            # Debtor address check for CGI-MP
            dbtr = instruction.debtor
            if dbtr.street or dbtr.town or dbtr.postal_code or dbtr.country:
                dbtr_missing = []
                if not dbtr.street:
                    dbtr_missing.append("StrtNm")
                if not dbtr.postal_code:
                    dbtr_missing.append("PstCd")
                if not dbtr.town:
                    dbtr_missing.append("TwnNm")
                if not dbtr.country:
                    dbtr_missing.append("Ctry")
                if dbtr_missing:
                    results.append(_check(
                        "BR-CGI-ADDR-03", False,
                        f"Debtor-Adresse: fehlende Felder: {', '.join(dbtr_missing)}",
                    ))

    handler = get_handler(testcase.payment_type)
    results.extend(handler.validate(testcase, instruction.transactions))

    return results


# ---------------------------------------------------------------------------
# Violation-Funktionen (Negative Testing)
# ---------------------------------------------------------------------------

def _get_violations_registry():
    """Liefert das Violations-Registry (Rule-ID -> Funktion)."""
    return {
        "BR-SEPA-001": _violate_sepa_currency,
        "BR-SEPA-003": _violate_sepa_charge_bearer,
        "BR-SEPA-004": _violate_sepa_name_length,
        "BR-QR-002": _violate_qr_reference,
        "BR-QR-003": _violate_qr_scor,
        "BR-QR-004": _violate_qr_currency,
        "BR-IBAN-001": _violate_iban_qr,
        "BR-IBAN-002": _violate_iban_qrr,
        "BR-IBAN-004": _violate_iban_currency,
        "BR-DOM-001": _violate_dom_charge_bearer,
        "BR-CBPR-001": _violate_cbpr_currency,
        "BR-CBPR-003": _violate_cbpr_charge_bearer,
        "BR-CBPR-005": _violate_cbpr_agent,
        "BR-ADDR-002": _violate_unstructured_address,
        "BR-CGI-ADDR-03": _violate_cgi_addr_unstructured,
        "BR-SIC5-001": _violate_sic5_currency,
        "BR-SIC5-002": _violate_sic5_creditor_iban,
        "BR-SCT-INST-001": _violate_sct_inst_currency,
        "BR-SCT-INST-002": _violate_sct_inst_amount,
        # BR-REM-002 ist XSD-geschuetzt (maxLength=140 auf Ustrd), keine Violation moeglich
        # BR-CCY-001 ist XSD-geschuetzt ([A-Z]{3}), keine Violation moeglich
    }


# Feld-Gruppen fuer Konflikt-Erkennung bei Violation-Chaining
_VIOLATION_FIELD_MAP = {
    "BR-SEPA-001": "currency",
    "BR-QR-004": "currency",
    "BR-IBAN-004": "currency",
    "BR-CBPR-001": "currency",
    "BR-SIC5-001": "currency",
    "BR-SCT-INST-001": "currency",
    "BR-SEPA-003": "charge_bearer",
    "BR-DOM-001": "charge_bearer",
    "BR-CBPR-003": "charge_bearer",
    "BR-SEPA-004": "creditor_name",
    "BR-QR-002": "remittance_info",
    "BR-QR-003": "remittance_info",
    "BR-IBAN-002": "remittance_info",
    "BR-IBAN-001": "creditor_iban",
    "BR-SIC5-002": "creditor_iban",
    "BR-CBPR-005": "creditor_bic",
    "BR-ADDR-002": "creditor_address",
    "BR-CGI-ADDR-03": "creditor_address",
    "BR-SCT-INST-002": "amount",
}


def parse_violate_rules(violate_rule: str) -> list[str]:
    """Parst kommaseparierte Rule-IDs und gibt eine bereinigte Liste zurueck."""
    return [r.strip() for r in violate_rule.split(",") if r.strip()]


def check_violation_conflicts(rule_ids: list[str]) -> list[str]:
    """Prueft auf Konflikte zwischen Violation-Rules.

    Zwei Rules konfligieren, wenn sie dasselbe Feld modifizieren
    (z.B. zwei verschiedene Currency-Violations).

    Returns:
        Liste von Fehlermeldungen (leer = keine Konflikte).
    """
    field_to_rules: dict[str, list[str]] = {}
    for rule_id in rule_ids:
        field = _VIOLATION_FIELD_MAP.get(rule_id)
        if field:
            field_to_rules.setdefault(field, []).append(rule_id)

    errors = []
    for field, rules in field_to_rules.items():
        if len(rules) > 1:
            errors.append(
                f"Konflikt: Rules {', '.join(rules)} modifizieren dasselbe Feld '{field}'"
            )
    return errors


def apply_rule_violation(
    testcase: TestCase,
    instruction: PaymentInstruction,
) -> PaymentInstruction:
    """Wendet gezielte Regelverletzungen an (Negative Testing).

    Unterstuetzt kommaseparierte Rule-IDs (z.B. "BR-SEPA-001,BR-SEPA-003").
    Modifiziert die PaymentInstruction so, dass die angegebenen Business Rules
    verletzt werden, ohne die XSD-Validitaet zu brechen.

    Raises:
        ValueError: Bei konfligierenden Violations (gleiches Feld).
    """
    if not testcase.violate_rule:
        return instruction

    rule_ids = parse_violate_rules(testcase.violate_rule)
    if not rule_ids:
        return instruction

    # Konflikt-Pruefung
    conflicts = check_violation_conflicts(rule_ids)
    if conflicts:
        raise ValueError(
            f"Testfall '{testcase.testcase_id}': "
            + "; ".join(conflicts)
        )

    violations = _get_violations_registry()

    for rule_id in rule_ids:
        violation_fn = violations.get(rule_id)
        if violation_fn:
            instruction = violation_fn(instruction)

    return instruction


def _update_all_transactions(instr, **updates):
    """Hilfsfunktion: Aktualisiert alle Transaktionen in einer Instruction."""
    txs = [tx.model_copy(update=updates) for tx in instr.transactions]
    return instr.model_copy(update={"transactions": txs})


def _violate_sepa_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SEPA-001: Setzt Währung auf CHF statt EUR."""
    return _update_all_transactions(instr, currency="CHF")


def _violate_sepa_charge_bearer(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SEPA-003: Setzt ChrgBr auf DEBT statt SLEV."""
    return instr.model_copy(update={"charge_bearer": "DEBT"})


def _violate_sepa_name_length(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SEPA-004: Setzt einen zu langen Creditor-Namen."""
    return _update_all_transactions(instr, creditor_name="A" * 71)


def _violate_qr_reference(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-QR-002: Entfernt die QRR-Referenz."""
    return _update_all_transactions(instr, remittance_info=None)


def _violate_qr_scor(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-QR-003: Setzt SCOR-Referenz bei QR-IBAN."""
    return _update_all_transactions(
        instr, remittance_info={"type": "SCOR", "value": "RF18539007547034"},
    )


def _violate_qr_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-QR-004: Setzt Währung auf USD."""
    return _update_all_transactions(instr, currency="USD")


def _violate_iban_qr(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-IBAN-001: Setzt eine QR-IBAN als Creditor."""
    from src.data_factory.iban import generate_ch_iban
    rng = random.Random(42)
    qr_iban = generate_ch_iban(rng, qr=True)
    return _update_all_transactions(instr, creditor_iban=qr_iban)


def _violate_iban_qrr(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-IBAN-002: Setzt QRR-Referenz bei regulärer IBAN."""
    from src.data_factory.reference import generate_qrr
    rng = random.Random(42)
    qrr = generate_qrr(rng)
    return _update_all_transactions(
        instr, remittance_info={"type": "QRR", "value": qrr},
    )


def _violate_iban_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-IBAN-004: Setzt Währung auf EUR statt CHF."""
    return _update_all_transactions(instr, currency="EUR")


def _violate_dom_charge_bearer(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-DOM-001: Setzt ChrgBr auf SHAR (bei Domestic nicht erlaubt)."""
    return instr.model_copy(update={"charge_bearer": "SHAR"})


def _violate_cbpr_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-CBPR-001: Entfernt die Währung (leerer String)."""
    return _update_all_transactions(instr, currency="")


def _violate_cbpr_agent(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-CBPR-005: Entfernt den Creditor-Agent BIC."""
    return _update_all_transactions(instr, creditor_bic=None)


def _violate_cbpr_charge_bearer(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-CBPR-003: Entfernt ChrgBr (leerer String wird als ungültig erkannt)."""
    return instr.model_copy(update={"charge_bearer": ""})


def _violate_ustrd_length(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-REM-002: Setzt zu langen unstrukturierten Verwendungszweck."""
    return _update_all_transactions(
        instr, remittance_info={"type": "USTRD", "value": "X" * 141},
    )


def _violate_currency_code(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-CCY-001: Setzt ungültigen Währungscode (kleinbuchstaben - Pattern-Fehler)."""
    return _update_all_transactions(instr, currency="usd")


def _violate_cgi_addr_unstructured(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-CGI-ADDR-03: Ersetzt strukturierte Adresse durch AdrLine (bei CGI-MP verboten)."""
    updated_txs = []
    for tx in instr.transactions:
        addr = tx.creditor_address or {}
        # Strukturierte Felder in AdrLine umwandeln
        street = addr.get("StrtNm", "Hauptstrasse")
        bldg = addr.get("BldgNb", "1")
        pstcd = addr.get("PstCd", "8001")
        town = addr.get("TwnNm", "Zuerich")
        ctry = addr.get("Ctry", "CH")
        new_addr = {
            "AdrLine": f"{street} {bldg}|{pstcd} {town}",
            "Ctry": ctry,
        }
        updated_txs.append(tx.model_copy(update={"creditor_address": new_addr}))
    return instr.model_copy(update={"transactions": updated_txs})


def _violate_unstructured_address(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-ADDR-002: Entfernt StrtNm aus Creditor-Adresse (unvollständig strukturiert)."""
    updated_txs = []
    for tx in instr.transactions:
        addr = dict(tx.creditor_address or {})
        addr.pop("StrtNm", None)
        updated_txs.append(tx.model_copy(update={"creditor_address": addr}))
    return instr.model_copy(update={"transactions": updated_txs})


def _violate_sic5_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SIC5-001: Setzt Währung auf EUR statt CHF bei Instant-Zahlung."""
    return _update_all_transactions(instr, currency="EUR")


def _violate_sic5_creditor_iban(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SIC5-002: Setzt eine nicht-CH/LI Creditor-IBAN bei Instant-Zahlung."""
    return _update_all_transactions(instr, creditor_iban="DE89370400440532013000")


def _violate_sct_inst_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SCT-INST-001: Setzt Währung auf CHF statt EUR bei SCT Inst."""
    return _update_all_transactions(instr, currency="CHF")


def _violate_sct_inst_amount(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SCT-INST-002: Setzt Betrag auf über 100'000 EUR."""
    from decimal import Decimal
    return _update_all_transactions(instr, amount=Decimal("100000.01"))
