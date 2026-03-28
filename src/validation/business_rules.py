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
    TestCase,
    ValidationResult,
)
from src.payment_types import get_handler
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

    # BR-IBAN-V01 / V02: IBAN-Validierung
    iban_fields = [("Debtor IBAN", instruction.debtor.iban)]
    for tx in txs:
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

    # BR-GEN-006: Creditor-Name max 140 Zeichen (non-SEPA)
    if testcase.payment_type != PaymentType.SEPA:
        for tx in txs:
            if len(tx.creditor_name) > 140:
                results.append(_check(
                    "BR-GEN-006", False,
                    f"Name hat {len(tx.creditor_name)} Zeichen (max 140)",
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

    handler = get_handler(testcase.payment_type)
    results.extend(handler.validate(testcase, instruction.transactions))

    return results


# ---------------------------------------------------------------------------
# Violation-Funktionen (Negative Testing)
# ---------------------------------------------------------------------------

def apply_rule_violation(
    testcase: TestCase,
    instruction: PaymentInstruction,
) -> PaymentInstruction:
    """Wendet eine gezielte Regelverletzung an (Negative Testing).

    Modifiziert die PaymentInstruction so, dass die angegebene Business Rule
    verletzt wird, ohne die XSD-Validität zu brechen.
    """
    rule_id = testcase.violate_rule
    if not rule_id:
        return instruction

    violations = {
        "BR-SEPA-001": _violate_sepa_currency,
        "BR-SEPA-003": _violate_sepa_charge_bearer,
        "BR-SEPA-004": _violate_sepa_name_length,
        "BR-QR-002": _violate_qr_reference,
        "BR-QR-003": _violate_qr_scor,
        "BR-QR-004": _violate_qr_currency,
        "BR-IBAN-001": _violate_iban_qr,
        "BR-IBAN-002": _violate_iban_qrr,
        "BR-IBAN-004": _violate_iban_currency,
        "BR-CBPR-001": _violate_cbpr_currency,
        "BR-CBPR-003": _violate_cbpr_charge_bearer,
        "BR-CBPR-005": _violate_cbpr_agent,
        "BR-ADDR-002": _violate_unstructured_address,
        # BR-REM-002 ist XSD-geschuetzt (maxLength=140 auf Ustrd), keine Violation moeglich
        # BR-CCY-001 ist XSD-geschuetzt ([A-Z]{3}), keine Violation moeglich
    }

    violation_fn = violations.get(rule_id)
    if violation_fn:
        return violation_fn(instruction)

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


def _violate_unstructured_address(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-ADDR-002: Entfernt StrtNm aus Creditor-Adresse (unvollständig strukturiert)."""
    updated_txs = []
    for tx in instr.transactions:
        addr = dict(tx.creditor_address or {})
        addr.pop("StrtNm", None)
        updated_txs.append(tx.model_copy(update={"creditor_address": addr}))
    return instr.model_copy(update={"transactions": updated_txs})
